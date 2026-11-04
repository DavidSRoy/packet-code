#!/usr/bin/env python3
"""End-to-end test of the REAL ground_control code (server.Link, server.Pilot, hop.Hop) on SITL.

  python tools/sim/hover/e2e/run_e2e.py --name e2e1 --height 0.02 --hold 30 \
      --parm tools/tune_v6.parm --set camera.tilt_attitude_lag_s=0.06 --set 'camera.pi_cam_pos_err=[0,0,0]'

SITL (speedup 1: hop.py runs on wall time) + e2e/fake_pi.py (physics.py and the Pi: VISION_*,
zero answer, PIIP, /lid.json) on instance --instance. The laptop side is ground_control
imported as is (aiohttp is stubbed: the web page is not under test) and connected to SITL
SERIAL0 over TCP. Then hop.Hop.press(height, hold) is called as the page "Run test" does.
Scored with run.score() on the true trajectory. Writes <out>/<name>/result.json.
"""
import argparse
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HOVER = HERE.parent
REPO = HOVER.parent.parent.parent
sys.path.insert(0, str(HOVER))
sys.path.insert(0, str(REPO / "ground_control"))
os.environ.setdefault("MAVLINK20", "1")
import run as simrun  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--height", type=float, default=0.02)
    ap.add_argument("--hold", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--flown", default=str(HOVER / "flown_log45.parm"))
    ap.add_argument("--parm", action="append", default=[])
    ap.add_argument("--p", action="append", default=[], help="param NAME=VALUE (after --parm)")
    ap.add_argument("--set", action="append", default=[], help="physics model override")
    ap.add_argument("--instance", type=int, default=20)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pre-source", action="store_true",
                    help="diagnostic: switch the EKF to source set 2 before the origin (not what the drone does)")
    ap.add_argument("--settle-wait", type=float, default=20.0, help="wall s after SITL start before press")
    a = ap.parse_args()
    assert 20 <= a.instance <= 25, "instances 20-25 only"
    I = a.instance
    work = Path(a.out) / a.name
    (work / "scripts").mkdir(parents=True, exist_ok=True)
    for s in ("hop_takeoff.lua", "hop_guard.lua"):
        (work / "scripts" / s).write_bytes((REPO / "lua" / s).read_bytes())
    # the real RC_OVERRIDE_TIME (hop.py refuses > 0.5); sim sensor noise as configs/r2.json
    lines = [kv.replace("=", " ") for kv in a.p] + ["RC_OVERRIDE_TIME 0.3"]
    defaults = simrun.write_params(work, a.parm, lines, a.flown)
    want = {}                                   # Lua-made params (HTO_*): set live like run.py
    for f in a.parm:
        for l in Path(f).read_text().splitlines():
            if l.startswith("HTO_"):
                k, v = l.split(",")[:2]
                want[k] = float(v)
    for kv in a.p:
        if kv.startswith("HTO_"):
            want[kv.split("=")[0]] = float(kv.split("=")[1])

    logf = open(work / "e2e.log", "w")

    def log(s):
        line = f"{time.time():.3f} {s}"
        logf.write(line + "\n")
        logf.flush()
        print(line, flush=True)
    py = sys.executable
    procs = []
    res = {"name": a.name, "height": a.height, "hold": a.hold, "parm": a.parm, "p": a.p, "set": a.set,
           "hto_wanted": want}
    rec = {"local": [], "hopt": [], "status": [], "targets": [], "texts": [], "armed": []}
    try:
        procs.append(subprocess.Popen(
            [py, str(HERE / "fake_pi.py"), "--http-port", str(28600 + I), "--out", str(work / "truth.npz"),
             "--seed", str(a.seed), "--port", str(9002 + 10 * I), "--cam-url", f"tcp:127.0.0.1:{5762 + 10 * I}",
             "--wallmap", str(work / "wallmap.txt")] + sum((["--set", s] for s in a.set), []),
            stdout=open(work / "physics.log", "w"), stderr=subprocess.STDOUT))
        time.sleep(0.5)
        procs.append(subprocess.Popen(
            [str(simrun.ARDU / "build/sitl/bin/arducopter"), "-w", "--model", "JSON:127.0.0.1", "--speedup", "1",
             "--home", ",".join(map(str, simrun.HOME)) + ",0", "--defaults", defaults, f"-I{I}"],
            cwd=work, stdout=open(work / "sitl.log", "w"), stderr=subprocess.STDOUT, start_new_session=True))
        t_sitl = time.time()
        time.sleep(1.0)

        # ---- the laptop: ground_control as is ----
        stub = types.ModuleType("aiohttp")
        stub.web, stub.WSMsgType = types.SimpleNamespace(), None
        sys.modules["aiohttp"] = stub
        os.environ["PACKET_LOG_DIR"] = str(work / "gc_logs")
        import server
        import hop
        link = server.Link(f"tcp:127.0.0.1:{5760 + 10 * I}", 57600, None, None)
        params = {}

        def hook(msg):
            k, now = msg.get_type(), time.time()
            if k == "LOCAL_POSITION_NED":
                rec["local"].append((now, msg.x, msg.y, msg.z, msg.vx, msg.vy, msg.vz))
            elif k == "NAMED_VALUE_FLOAT" and msg.name == "HOPT":
                if not rec["hopt"] or rec["hopt"][-1][1] != int(round(msg.value)):
                    rec["hopt"].append((now, int(round(msg.value))))
            elif k == "STATUSTEXT":
                rec["texts"].append((now, msg.text))
                log(f"FC: {msg.text}")
            elif k == "PARAM_VALUE":
                params[msg.param_id] = msg.param_value
        link.hooks.append(hook)
        threading.Thread(target=link.run, daemon=True).start()
        pilot = server.Pilot(link)
        threading.Thread(target=pilot.loop, daemon=True).start()
        h = hop.Hop(link, pilot)
        pilot.hop = h
        orig = h._hold_target

        def hold_target(start, yaw, height=None):
            rec["targets"].append((time.time(), list(start), yaw, height))
            return orig(start, yaw, height)
        h._hold_target = hold_target

        # ---- setup that the real drone already has ----
        end = time.time() + 60
        while time.time() < end and link.sysid is None:
            time.sleep(0.2)
        assert link.sysid is not None, "no heartbeat from SITL"
        for k, v in want.items():                 # HTO_* exist only once hop_takeoff.lua has run
            for _ in range(40):
                if abs(params.get(k, 1e9) - v) < 1e-4:
                    break
                link.send(link.m.mav.param_set_send, link.sysid, link.compid, k.encode(), v,
                          server.mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
                time.sleep(0.5)
            log(f"param {k} = {params.get(k)} (want {v})")
        res["hto_read_back"] = {k: params.get(k) for k in want}
        # SITL's default RC has CH8 at 1800 = the Boxer SD kill on stop (server.py sd_stop): put it
        # low, as the pilot does (SITL keeps the last UDP RC packet; 0 = leave that channel)
        import socket
        import struct
        rc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for _ in range(5):
            rc.sendto(struct.pack("<8H", 0, 0, 0, 0, 0, 0, 0, 1000), ("127.0.0.1", 5501 + 10 * I))
            time.sleep(0.05)
        # Indoors on the drone the FC/laptop has a last known position; SITL has GPS off and no
        # origin, so GLOBAL_POSITION_INT lat/lon are 0 and hop.py would refuse. Give the origin
        # first (then hop.py's own REQUEST_MESSAGE 49 finds it).
        lat, lon, alt = simrun.HOME
        if a.pre_source:
            for _ in range(3):
                link.command(42007, 2)
                time.sleep(0.3)
            log("diagnostic: source set 2 before the press")
        while time.time() - t_sitl < a.settle_wait:
            time.sleep(0.2)
        t_org = time.time()
        while time.time() - t_org < 15 and (link.state.get("origin_t") or 0) < t_org:
            link.send(link.m.mav.set_gps_global_origin_send, link.sysid, int(lat * 1e7), int(lon * 1e7),
                      int(alt * 1000), int(time.time() * 1e6))
            link.command(server.mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 49)
            time.sleep(1.0)
        log(f"EKF origin before press: {(link.state.get('origin_t') or 0) >= t_org}")
        time.sleep(3.0)                           # GLOBAL_POSITION_INT with the origin
        st = link.state
        res["pre_press"] = {k: st.get(k) for k in ("link", "mode", "armed", "pi_url", "rc_override_time",
                                                   "fc_params", "sd_stop", "alt", "lat_fc", "lon_fc")}
        res["pre_press"]["check"] = h.check()
        log(f"pre-press: {res['pre_press']}")

        # ---- Run test, as the page does (server.py: run_in_executor(pilot.hop.press, height, duration)) ----
        t_press = time.time()
        threading.Thread(target=h.press, args=(a.height, a.hold), daemon=True).start()
        last, end = None, time.time() + a.hold + 90
        while time.time() < end:
            s = dict(h.status)
            arm = link.state["armed"]
            if not rec["armed"] or rec["armed"][-1][1] != arm:
                rec["armed"].append((time.time(), arm))
            key = (s.get("state"), s.get("reason"), s.get("test_left") is not None)
            if key != last:
                rec["status"].append((time.time(), s))
                log(f"hop status: {s}")
                last = key
            if s.get("state") in ("done", "killed", "refused") and not arm:
                break
            time.sleep(0.05)
        time.sleep(1.0)
        res["final_status"] = dict(h.status)
        res["laptop_notes"] = [(round(t - t_press, 2), sev, txt) for t, sev, txt in link.messages]
        link.running = False
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
        for p in reversed(procs):
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()

    # ---- analysis ----
    def first(lst, pred):
        for t, s in lst:
            if pred(s):
                return t
        return None
    ev = {"press": t_press,
          "armed": first(rec["armed"], lambda v: v),
          "handover": first(rec["status"], lambda s: s.get("state") == "locked"),
          "at height": first(rec["status"], lambda s: s.get("test_left") is not None),
          "descend": first(rec["status"], lambda s: s.get("state") == "landing"),
          "disarmed": first([r for r in rec["armed"] if r[0] > t_press + 1], lambda v: not v)}
    res["events_rel_s"] = {k: (None if v is None else round(v - t_press, 2)) for k, v in ev.items()}
    events = {k: {"wall": v} for k, v in ev.items() if v is not None}
    z = np.load(work / "truth.npz")
    T, wm = z["truth"], np.loadtxt(work / "wallmap.txt")
    res["sim_over_wall"] = float((wm[-1, 1] - wm[0, 1]) / (wm[-1, 0] - wm[0, 0]))
    if rec["targets"] and ev["armed"]:
        start = rec["targets"][0][1]
        res["start_fc"] = start
        L = np.array(rec["local"])
        pre = L[(L[:, 0] < ev["armed"]) & (L[:, 0] > ev["press"])]
        # find the samples hop.py averaged: a contiguous run whose mean is the start
        best = None
        for j in range(len(pre)):
            for i in range(j + 1):
                m = pre[i:j + 1, 1:4].mean(0)
                d = float(np.abs(m - start).max())
                if best is None or d < best[0]:
                    best = (d, i, j)
        d, i, j = best
        res["start_window"] = {"n_samples": j - i + 1, "span_s": round(float(pre[j, 0] - pre[i, 0]), 3),
                               "match_err": d, "single_last_sample": pre[j, 1:4].tolist(),
                               "window_spread_mm": (np.ptp(pre[i:j + 1, 1:4], 0) * 1000).round(2).tolist()}
        tw = np.interp(ev["armed"], wm[:, 0], wm[:, 1])
        sel = (T[:, 0] > tw - 1.5) & (T[:, 0] < tw - 0.2)
        true0 = T[sel, 1:4].mean(0)
        res["true_start"] = true0.tolist()
        res["start_minus_true_mm"] = ((np.array(start) - true0) * 1000).round(2).tolist()
        res["last_sample_minus_true_mm"] = ((pre[j, 1:4] - true0) * 1000).round(2).tolist()
    if ev["armed"] and ev["at height"]:
        try:
            res["score"] = simrun.score(T, events, wm, a.height)
        except Exception as e:
            res["score_error"] = f"{type(e).__name__}: {e}"
    res["hopt"] = [(round(t - t_press, 2), v) for t, v in rec["hopt"]]
    res["status_log"] = [(round(t - t_press, 2), s) for t, s in rec["status"]]
    res["n_targets"] = len(rec["targets"])
    res["targets_first_last"] = [rec["targets"][0], rec["targets"][-1]] if rec["targets"] else None
    (work / "result.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res.get(k) for k in ("final_status", "events_rel_s", "start_fc", "true_start",
                                              "start_minus_true_mm", "last_sample_minus_true_mm", "start_window",
                                              "score", "sim_over_wall")}, indent=1, default=str))


if __name__ == "__main__":
    main()
