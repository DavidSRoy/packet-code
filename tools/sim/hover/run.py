#!/usr/bin/env python3
"""One simulated box-camera hover test: ArduCopter 4.7.2 SITL + physics.py, flown like
ground_control/hop.py "Run test", then scored on the TRUE trajectory.

  python tools/sim/hover/run.py --name base --height 0.02 --hold 30 --seed 1 \
      [--parm extra.parm ...] [--set camera.rate_hz=20 ...] [--instance 0] [--speedup 4]

Sequence (as hop.py): EKF source set 2 (camera), EKF origin, wait until the FC position is
still, home here, GUIDED, arm with HOP_CH high (RC override from sysid 255), wait for
lua/hop_takeoff.lua to hand over (HOPT 4), climb a position target over the start point at
CLIMB_MPS to the height, hold, descend to LAND_BELOW_M under the start, wait for the disarm.

Score (true state from physics.py, hold window = from 2 s after the height is reached to the
start of the descent): horizontal distance from the true start point (RMS, max, 95 %), height
error, roll/pitch angle RMS and the angular rate RMS above 0.5 Hz (wobble), and the strongest
roll/pitch frequency. Result: runs/<name>/result.json.
"""
import argparse
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("MAVLINK20", "1")
from pymavlink import mavutil  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
ARDU = Path(os.environ.get("ARDUPILOT", "~/ardupilot-x650/ardupilot")).expanduser()
MAV = mavutil.mavlink
HOP_CH = 12
CLIMB_MPS = 0.05
LAND_BELOW_M = 0.02
POS_YAW_MASK = 0b0000_1001_1111_1000
SOURCE_SET_CMD = 42007
HOME = (47.6625, -122.2985, 20.0)
DROP_PREFIX = ("BATT_",)


def write_params(work, extra_parms, extra_lines, flown_file):
    flown = [l for l in Path(flown_file).read_text().splitlines()
             if l and not l.startswith("#") and not l.startswith(DROP_PREFIX)]
    (work / "flown.parm").write_text("\n".join(l.replace(",", " ") for l in flown) + "\n")
    files = [ARDU / "Tools/autotest/default_params/copter.parm", work / "flown.parm", HERE / "sim_base.parm"]   # sim-only settings last
    for i, p in enumerate(extra_parms):
        dst = work / f"extra{i}.parm"
        dst.write_text("\n".join(l.replace(",", " ") for l in Path(p).read_text().splitlines()
                                 if l.strip() and not l.strip().startswith("#")) + "\n")
        files.append(dst)
    if extra_lines:
        (work / "cli.parm").write_text("\n".join(extra_lines) + "\n")
        files.append(work / "cli.parm")
    return ",".join(str(f) for f in files)


class Driver:
    def __init__(self, url, log):
        self.m = mavutil.mavlink_connection(url, source_system=255, source_component=190)
        self.log = log
        self.t = 0.0                  # FC time, s (time_boot_ms)
        self.local = None             # (x, y, z, vx, vy, vz, t)
        self.att = None
        self.armed = False
        self.mode = None
        self.hopt = 0
        self.acks = {}
        self.origin = False
        self.texts = []
        self.events = {}
        self.last_hb = 0.0
        self.params = {}

    def ev(self, name):
        self.events[name] = {"fc_t": self.t, "wall": time.time()}
        self.log(f"[{self.t:7.2f}] {name}")

    def pump(self, block=0.0):
        end = time.time() + block
        while True:
            msg = self.m.recv_match(blocking=block > 0, timeout=max(0.0, end - time.time()) if block else None)
            if msg is None:
                break
            k = msg.get_type()
            if hasattr(msg, "time_boot_ms"):
                self.t = max(self.t, msg.time_boot_ms / 1000.0)
            if k == "HEARTBEAT" and msg.get_srcComponent() == 1 and msg.type != MAV.MAV_TYPE_GCS:
                self.armed = bool(msg.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED)
                self.mode = msg.custom_mode
            elif k == "LOCAL_POSITION_NED":
                self.local = (msg.x, msg.y, msg.z, msg.vx, msg.vy, msg.vz, self.t)
            elif k == "ATTITUDE":
                self.att = (msg.roll, msg.pitch, msg.yaw)
            elif k == "NAMED_VALUE_FLOAT" and msg.name.rstrip("\x00") == "HOPT":
                self.hopt = int(msg.value)
            elif k == "COMMAND_ACK":
                self.acks[msg.command] = (msg.result, self.t)
            elif k == "GPS_GLOBAL_ORIGIN":
                self.origin = True
            elif k == "PARAM_VALUE":
                self.params[msg.param_id.rstrip("\x00")] = msg.param_value
            elif k == "STATUSTEXT":
                txt = msg.text.rstrip("\x00")
                self.texts.append((self.t, txt))
                self.log(f"[{self.t:7.2f}] FC: {txt}")
            if block:
                break
        if time.time() - self.last_hb > 0.5:
            self.last_hb = time.time()
            self.m.mav.heartbeat_send(MAV.MAV_TYPE_GCS, MAV.MAV_AUTOPILOT_INVALID, 0, 0, 0)

    def cmd(self, c, *p):
        p = list(p) + [0] * (7 - len(p))
        self.m.mav.command_long_send(1, 1, c, 0, *p)

    def override(self, pwm):
        ch = [0] * 18
        ch[HOP_CH - 1] = pwm
        self.m.mav.rc_channels_override_send(1, 1, *ch)

    def target(self, x, y, z, yaw):
        self.m.mav.set_position_target_local_ned_send(int(self.t * 1000), 1, 1, MAV.MAV_FRAME_LOCAL_NED, POS_YAW_MASK,
                                                       x, y, z, 0, 0, 0, 0, 0, 0, yaw, 0)

    def wait(self, cond, timeout_s, tick=None, every=0.1):
        """Wait in FC time for cond(); call tick() every `every` s of FC time."""
        t0, last = self.t, -1e9
        while self.t - t0 < timeout_s:
            self.pump(block=0.02)
            if self.t - last >= every and tick:
                last = self.t
                tick()
            if cond():
                return True
        return False


def fly(d, height, hold_s, log, live=None):
    d.wait(lambda: d.t > 2.0, 120)
    # parameters that exist only once a Lua script made them (HTO_*): set over MAVLink and read back
    for name, val in (live or {}).items():
        ok = d.wait(lambda: abs(d.params.get(name, 1e9) - val) < 1e-4, 20, every=1.0,
                    tick=lambda: d.m.mav.param_set_send(1, 1, name.encode(), val, MAV.MAV_PARAM_TYPE_REAL32))
        log(f"param {name} = {val}: {'ok' if ok else 'NOT SET'}")
        if not ok:
            return f"param {name} not set"
    for msg_id, hz in ((MAV.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 25), (MAV.MAVLINK_MSG_ID_ATTITUDE, 25)):
        d.cmd(MAV.MAV_CMD_SET_MESSAGE_INTERVAL, msg_id, 1e6 / hz)
    # 1. camera navigation (source set 2)
    if not d.wait(lambda: d.acks.get(SOURCE_SET_CMD, (None,))[0] == MAV.MAV_RESULT_ACCEPTED, 30,
                  tick=lambda: d.cmd(SOURCE_SET_CMD, 2), every=1.0):
        return "source set not accepted"
    d.ev("source set 2")
    # 2. EKF origin (no GPS indoors)
    lat, lon, alt = HOME

    def set_origin():
        d.m.mav.set_gps_global_origin_send(1, int(lat * 1e7), int(lon * 1e7), int(alt * 1000), int(d.t * 1e6))
        d.cmd(MAV.MAV_CMD_REQUEST_MESSAGE, 49)
    if not d.wait(lambda: d.origin, 30, tick=set_origin, every=1.0):
        return "no EKF origin"
    d.ev("origin")
    # 3. settle: FC position from the camera, still for 1 s
    still = {"t": None, "pos": []}

    def settled():
        L = d.local
        ok = L is not None and math.sqrt(L[3] ** 2 + L[4] ** 2 + L[5] ** 2) < 0.03 and d.t - L[6] < 0.2
        still["t"] = (still["t"] or d.t) if ok else None
        if not ok:
            still["pos"] = []
        elif not still["pos"] or still["pos"][-1][3] != L[6]:
            still["pos"].append((L[0], L[1], L[2], L[6]))
        return ok and d.t - still["t"] >= 1.0 and d.t > 15.0
    if not d.wait(settled, 60):
        return f"FC position did not settle: {d.local}"
    # as hop.py: the start is the mean FC position over the last settled second
    recent = [q for q in still["pos"] if q[3] >= d.t - 1.0] or [tuple(d.local[:3]) + (d.t,)]
    start = tuple(float(np.mean([q[i] for q in recent])) for i in range(3))
    yaw0 = d.att[2]
    d.ev("settled")
    d.events["start_fc"] = list(start)
    # 4. home here, GUIDED, arm with HOP_CH high
    d.cmd(MAV.MAV_CMD_DO_SET_HOME, 1)
    d.wait(lambda: False, 0.5, tick=lambda: d.override(2000), every=0.04)

    def every(period, f):
        """HOP_CH override every 40 ms (as hop.py, RATE_HZ 25), f() every `period` s."""
        last = [-1e9]

        def tick():
            d.override(2000)
            if d.t - last[0] >= period:
                last[0] = d.t
                f()
        return tick
    if not d.wait(lambda: d.mode == 4, 10, tick=every(0.5, lambda: d.m.set_mode(4)), every=0.04):
        return "GUIDED refused"
    if not d.wait(lambda: d.armed, 30, tick=every(0.5, lambda: d.cmd(MAV.MAV_CMD_COMPONENT_ARM_DISARM, 1)), every=0.04):
        return "arming refused: " + "; ".join(t for _, t in d.texts[-5:])
    d.ev("armed")
    # 5. lua/hop_takeoff.lua flies the takeoff and hands over (HOPT 4)
    if not d.wait(lambda: d.hopt == 4 or d.hopt == 9 or not d.armed, 15, tick=lambda: d.override(2000), every=0.04):
        return f"no handover (HOPT {d.hopt})"
    if d.hopt != 4:
        return f"takeoff aborted (HOPT {d.hopt}, armed {d.armed})"
    d.ev("handover")
    z0 = d.local[2]
    goal = start[2] - height
    t_h = d.t

    def climb():
        d.override(2000)
        z = max(goal, z0 - CLIMB_MPS * (d.t - t_h)) if goal < z0 else goal
        d.target(start[0], start[1], z, yaw0)
    d.wait(lambda: not d.armed, max(0.5, (z0 - goal) / CLIMB_MPS) + 0.2, tick=climb, every=0.04)
    d.ev("at height")
    d.wait(lambda: not d.armed, hold_s, tick=lambda: (d.override(2000), d.target(start[0], start[1], goal, yaw0)), every=0.04)
    if not d.armed:
        return "disarmed in the hold"
    d.ev("descend")
    t_d = d.t
    low = start[2] + LAND_BELOW_M

    def down():
        d.override(2000)
        d.target(start[0], start[1], min(low, goal + CLIMB_MPS * (d.t - t_d)), yaw0)
    if not d.wait(lambda: not d.armed, (low - goal) / CLIMB_MPS + 6.0, tick=down, every=0.04):
        d.cmd(MAV.MAV_CMD_COMPONENT_ARM_DISARM, 0, 21196)
        d.wait(lambda: not d.armed, 3)
        d.ev("force disarm")
        return "ok (force disarm after the descent)"
    d.ev("landed")
    return "ok"


def hp_rms_series(x, fs, f0):
    """x with the content below f0 removed (FFT)."""
    F = np.fft.rfft(x - x.mean())
    f = np.fft.rfftfreq(len(x), 1 / fs)
    F[f < f0] = 0
    return np.fft.irfft(F, len(x))


def score(truth, events, wall_map, height):
    """Scores on the true state in the hold window."""
    cols = "t px py pz vx vy vz roll pitch yaw wx wy wz".split()
    T = {c: truth[:, i] for i, c in enumerate(cols)}

    def phys_t(ev):
        w = events[ev]["wall"]
        return float(np.interp(w, wall_map[:, 0], wall_map[:, 1]))
    t_arm = phys_t("armed")
    pre = (T["t"] > t_arm - 1.5) & (T["t"] < t_arm - 0.2)
    x0, y0, z0 = T["px"][pre].mean(), T["py"][pre].mean(), T["pz"][pre].mean()
    t_a = phys_t("at height") + 2.0
    t_b = phys_t("descend") if "descend" in events else T["t"][-1]
    w = (T["t"] >= t_a) & (T["t"] <= t_b)
    if w.sum() < 100:
        return {"error": "hold window too short"}
    dx, dy = T["px"][w] - x0, T["py"][w] - y0
    r = np.hypot(dx, dy)
    dz = -(T["pz"][w] - z0) - height
    fs = 1 / np.median(np.diff(T["t"]))

    def hp_rms(x, f0=0.5):
        F = np.fft.rfft(x - x.mean())
        f = np.fft.rfftfreq(len(x), 1 / fs)
        F[f < f0] = 0
        return float(np.sqrt(np.mean(np.fft.irfft(F, len(x)) ** 2)))

    def peak(x):
        F = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(len(x))))
        f = np.fft.rfftfreq(len(x), 1 / fs)
        s = (f > 0.1) & (f < 30)
        return float(f[s][np.argmax(F[s])])
    rp = np.degrees(np.c_[T["roll"][w], T["pitch"][w]])
    # settle: from the hand-over, the first time after which the drone stays within 10 mm to the descent
    settle = None
    if "handover" in events:
        t_h = phys_t("handover")
        sw = (T["t"] >= t_h) & (T["t"] <= t_b)
        rr = np.hypot(T["px"][sw] - x0, T["py"][sw] - y0)
        out = np.where(rr >= 0.010)[0]
        settle = float(T["t"][sw][out[-1] + 1] - t_h) if len(out) and out[-1] + 1 < sw.sum() else (0.0 if not len(out) else None)
    # wobble a person sees: tilt above 1 Hz
    tilt_hp = np.hypot(*(np.array([hp_rms_series(np.radians(rp[:, i]), fs, 1.0) for i in (0, 1)])))
    return {
        "settle10_s": settle,
        "tilt_hp_rms_deg": float(np.degrees(np.sqrt(np.mean(tilt_hp ** 2)))),
        "tilt_hp_p99_deg": float(np.degrees(np.percentile(tilt_hp, 99))),
        "hold_s": float(t_b - t_a),
        "xy_rms_mm": float(np.sqrt(np.mean(r ** 2)) * 1000), "xy_max_mm": float(r.max() * 1000),
        "xy_p95_mm": float(np.percentile(r, 95) * 1000),
        "x_mean_mm": float(dx.mean() * 1000), "y_mean_mm": float(dy.mean() * 1000),
        "z_rms_mm": float(np.sqrt(np.mean(dz ** 2)) * 1000), "z_max_mm": float(np.abs(dz).max() * 1000),
        "tilt_rms_deg": float(np.sqrt(np.mean((rp - rp.mean(0)) ** 2))),
        "rate_hp_rms_dps": float(np.degrees(np.hypot(hp_rms(T["wx"][w]), hp_rms(T["wy"][w])))),
        "tilt_peak_hz": peak(T["roll"][w] + T["pitch"][w]),
        "xy_peak_hz": peak(dx + dy),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--height", type=float, default=0.02)
    ap.add_argument("--hold", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--flown", default=str(HERE / "flown_log45.parm"), help="flown parameter set (extract_parm.py)")
    ap.add_argument("--parm", action="append", default=[])
    ap.add_argument("--p", action="append", default=[], help="param override NAME=VALUE")
    ap.add_argument("--set", action="append", default=[], help="model override for physics.py")
    ap.add_argument("--instance", type=int, default=0)
    ap.add_argument("--speedup", type=int, default=4)
    ap.add_argument("--runs", default=str(HERE / "runs"))
    ap.add_argument("--rescore", action="store_true", help="only score the existing run --name again")
    a = ap.parse_args()
    if a.rescore:
        work = Path(a.runs) / a.name
        result = json.loads((work / "result.json").read_text())
        if str(result.get("status", "")).startswith("ok"):
            result["score"] = score(np.load(work / "truth.npz")["truth"], result["events"],
                                    np.loadtxt(work / "wallmap.txt"), result["height"])
            (work / "result.json").write_text(json.dumps(result, indent=1))
        print(json.dumps({k: result.get(k) for k in ("name", "status", "score")}, indent=1))
        return

    work = Path(a.runs) / a.name
    if work.exists():
        shutil.rmtree(work)
    (work / "scripts").mkdir(parents=True)
    for s in ("hop_takeoff.lua", "hop_guard.lua"):
        shutil.copy(REPO / "lua" / s, work / "scripts")
    logf = open(work / "run.log", "w")

    def log(s):
        logf.write(s + "\n")
        logf.flush()
    defaults = write_params(work, a.parm, [kv.replace("=", " ") for kv in a.p], a.flown)
    t_wall0 = time.time()
    py = sys.executable
    I = a.instance
    procs = []
    wall_map_file = work / "wallmap.txt"
    result = {"name": a.name, "flown": a.flown, "seed": a.seed, "height": a.height, "hold": a.hold, "parm": a.parm, "p": a.p, "set": a.set}
    try:
        phys = subprocess.Popen([py, str(HERE / "physics.py"), "--out", str(work / "truth.npz"), "--seed", str(a.seed),
                                 "--port", str(9002 + 10 * I), "--cam-url", f"tcp:127.0.0.1:{5762 + 10 * I}",
                                 "--wallmap", str(wall_map_file)] + sum((["--set", s] for s in a.set), []),
                                stdout=open(work / "physics.log", "w"), stderr=subprocess.STDOUT)
        procs.append(phys)
        time.sleep(0.5)
        sitl = subprocess.Popen([str(ARDU / "build/sitl/bin/arducopter"), "-w", "--model", "JSON:127.0.0.1",
                                 "--speedup", str(a.speedup), "--home", f"{HOME[0]},{HOME[1]},{HOME[2]},0",
                                 "--defaults", defaults, f"-I{I}"],
                                cwd=work, stdout=open(work / "sitl.log", "w"), stderr=subprocess.STDOUT,
                                start_new_session=True)
        procs.append(sitl)
        time.sleep(1.0)
        d = Driver(f"tcp:127.0.0.1:{5760 + 10 * I}", log)
        # HTO_* exist only once lua/hop_takeoff.lua made them, and AP_Param::add_param does not read
        # the --defaults files: set them live, from the --parm files and then --p (last wins)
        live = {}
        for pf in a.parm:
            for l in Path(pf).read_text().splitlines():
                f = l.replace(",", " ").split()
                if len(f) >= 2 and f[0].startswith("HTO_"):
                    live[f[0]] = float(f[1])
        live.update({kv.split("=")[0]: float(kv.split("=")[1]) for kv in a.p if kv.startswith("HTO_")})
        status = fly(d, a.height, a.hold, log, live)
        result["status"] = status
        result["events"] = d.events
        log("status: " + status)
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
        for p in reversed(procs):
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
    try:
        z = np.load(work / "truth.npz")
        wm = np.loadtxt(wall_map_file)
        if status.startswith("ok"):
            result["score"] = score(z["truth"], result["events"], wm, a.height)
    except Exception as e:
        result["score_error"] = f"{type(e).__name__}: {e}"
    bins = sorted((work / "logs").glob("*.BIN")) if (work / "logs").exists() else []
    result["dflog"] = str(bins[-1]) if bins else None
    result["wall_s"] = round(time.time() - t_wall0, 1)
    (work / "result.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({k: result.get(k) for k in ("name", "status", "score", "score_error")}, indent=1))


if __name__ == "__main__":
    main()
