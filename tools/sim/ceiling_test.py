"""End-to-end test of the automatic legal ceiling in ArduPilot SITL.

It starts ArduCopter SITL (4.7.2) with lua/ceil_guard.lua at QFC University
Village and the ground control server (ceiling map from airspace/cache), then:
  1. the fence follows the ceiling from ground control (FENCE_ALT_MAX = ceiling - home - margin),
  2. a stadium event at Husky Stadium makes QFC NO-FLY: the fence goes to 10 m on
     the ground and the laptop refuses a takeoff,
  3. in the air at 40 m, the same event: the fence stays 3 m over the drone
     (no breach, no RTL), the FC says "descend", and the fence follows the
     drone down,
  4. the event is removed: the fence goes back up,
  5. the ground control server stops (link lost): the FC changes to the
     fallback ceiling within CEIL_TOUT_S,
  6. the server starts again: the FC follows ground control again,
  7. horizontal NO-FLY guard: a 50 m keep-out zone 150 m west of QFC:
     a. a GUIDED goto through the zone: the FC stops the drone before the edge,
     b. a goto away from the zone: no stop,
     c. LOITER with the roll stick toward the zone: the FC changes to BRAKE
        before the edge; the drone never enters the zone.

Run (the map cache must exist: start the server once, or run airspace/test_ceiling.py):
  python tools/sim/ceiling_test.py --ardupilot ~/ardupilot-x650/ardupilot
"""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import math

import aiohttp
os.environ.setdefault("MAVLINK20", "1")
from pymavlink import mavutil   # noqa: E402

REPO = Path(__file__).resolve().parents[2]
QFC = (47.6625238, -122.2950755)
HTTP = 8652
results = []


def check(name, ok, extra=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name} {extra}", flush=True)


def ws_state():
    async def go():
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"http://127.0.0.1:{HTTP}/ws") as ws:
                m = await ws.receive(timeout=5)
                return json.loads(m.data)
    try:
        return asyncio.run(go())
    except Exception:
        return {}


def ws_send(msg):
    async def go():
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"http://127.0.0.1:{HTTP}/ws") as ws:
                await ws.send_str(json.dumps(msg))
                await asyncio.sleep(0.3)
    asyncio.run(go())


def air_edit(body):
    req = urllib.request.Request(f"http://127.0.0.1:{HTTP}/airspace/edit", data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


class Pilot:
    """Second MAVLink link to SITL: plays the pilot and reads what the FC reports."""

    def __init__(self):
        self.m = mavutil.mavlink_connection("tcp:127.0.0.1:5762", source_system=250, source_component=190)
        self.m.wait_heartbeat(timeout=60)
        self.pos, self.mode, self.armed = None, None, False
        self.nvf, self.params, self.texts = {}, {}, []
        self.lock = threading.Lock()
        self.running = True
        self.roll = 65535                 # RC override for CH1; 65535 = no override
        self.pitch = 65535                # CH2; low = nose down = forward
        self.thr = 1000                   # CH3: low to arm, mid (1500) to hold height in LOITER
        threading.Thread(target=self._rx, daemon=True).start()
        threading.Thread(target=self._rc, daemon=True).start()
        for mid, hz in ((33, 5), (0, 2)):
            self.cmd(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, mid, int(1e6 / hz))

    def cmd(self, c, *p):
        p = list(p) + [0] * (7 - len(p))
        with self.lock:
            self.m.mav.command_long_send(1, 1, c, 0, *p)

    def _rx(self):
        while self.running:
            msg = self.m.recv_match(blocking=True, timeout=0.5)
            if not msg:
                continue
            t = msg.get_type()
            if t == "GLOBAL_POSITION_INT":
                self.pos = (msg.lat / 1e7, msg.lon / 1e7, msg.relative_alt / 1000)
            elif t == "HEARTBEAT" and msg.get_srcComponent() == 1 and msg.type != mavutil.mavlink.MAV_TYPE_GCS:
                self.mode = mavutil.mode_string_v10(msg)
                self.armed = bool(msg.base_mode & 128)
            elif t == "NAMED_VALUE_FLOAT" and msg.get_srcSystem() == 1:
                self.nvf[msg.name] = (msg.value, time.time())
            elif t == "PARAM_VALUE":
                self.params[msg.param_id] = msg.param_value
            elif t == "STATUSTEXT":
                self.texts.append(msg.text)
                print("   drone:", msg.text, flush=True)

    def _rc(self):
        while self.running:
            with self.lock:   # SA off, SD run
                self.m.mav.rc_channels_override_send(1, 1, self.roll, self.pitch, self.thr, 65535, 1000, 65535, 65535, 1000, *([0] * 10))
            time.sleep(0.1)

    def param(self, name, value):
        with self.lock:
            self.m.mav.param_set_send(1, 1, name.encode(), float(value), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)

    def read(self, name, timeout=5):
        self.params.pop(name, None)
        with self.lock:
            self.m.mav.param_request_read_send(1, 1, name.encode(), -1)
        end = time.time() + timeout
        while time.time() < end:
            if name in self.params:
                return self.params[name]
            time.sleep(0.1)
        return None

    def fc(self, name):
        v = self.nvf.get(name)
        return v[0] if v and time.time() - v[1] < 3 else None

    def set_mode(self, name):
        with self.lock:
            self.m.mav.set_mode_send(1, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                                     {"GUIDED": 4, "LAND": 9, "LOITER": 5, "BRAKE": 17}[name])

    def goto_alt(self, alt, lat=QFC[0], lon=QFC[1]):
        with self.lock:
            self.m.mav.set_position_target_global_int_send(
                0, 1, 1, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 0b0000_1111_1111_1000,
                int(lat * 1e7), int(lon * 1e7), alt, 0, 0, 0, 0, 0, 0, 0, 0)

    def wait(self, cond, timeout, what):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.2)
        print(f"   timeout waiting for {what}", flush=True)
        return False


def dist_m(a, b):
    return math.hypot((b[0] - a[0]) * 111320.0, (b[1] - a[1]) * 111320.0 * math.cos(math.radians(a[0])))


def west(p, m):
    return p[0], p[1] - m / (111320.0 * math.cos(math.radians(p[0])))


def watch_zone(pilot, centre, radius, secs):
    """Fly for secs; return (closest distance to the zone edge, modes seen)."""
    closest, modes = 1e9, set()
    end = time.time() + secs
    while time.time() < end:
        closest = min(closest, dist_m(pilot.pos, centre) - radius)
        modes.add(pilot.mode)
        time.sleep(0.1)
    return closest, modes


def start_server(py, logf):
    return subprocess.Popen([py, "-u", str(REPO / "ground_control/server.py"), "--port", "tcp:127.0.0.1:5760",
                             "--qgc", "none", "--tunnel", "none", "--http", str(HTTP), "--sa-ch", "0",
                             "--pi-url", "none"],
                            stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ardupilot", required=True)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--speedup", type=int, default=1)
    args = ap.parse_args()
    ardu = Path(args.ardupilot).expanduser()
    work = Path(tempfile.mkdtemp(prefix="packet_ceil_"))
    (work / "scripts").mkdir()
    os.environ["PACKET_AIR_OPERATOR"] = str(work / "operator.json")   # the server is a child: it gets this
    shutil.copy(REPO / "lua" / "ceil_guard.lua", work / "scripts")
    shutil.copy(REPO / "tools/sim/x650.json", work)          # SITL loads the model by a path relative to work/
    (work / "extra.parm").write_text("FENCE_ENABLE 1\nFENCE_TYPE 1\nFENCE_ALT_MAX 30\nFENCE_ALT_MAX_TP 1\nFENCE_ACTION 1\n"
                                     "FS_GCS_ENABLE 0\n"
                                     # RC overrides count only from GCS ids: test pilot 250, ground control 254
                                     "MAV_GCS_SYSID 250\nMAV_GCS_SYSID_HI 255\n"
                                     # match the real drone (x650.json is the airframe model)
                                     "SIM_BATT_VOLTAGE 25.2\nFRAME_TYPE 1\nMOT_THST_HOVER 0.26\n"
                                     "MOT_BAT_VOLT_MAX 25.2\nMOT_BAT_VOLT_MIN 19.8\n")
    logs = {n: open(work / f"{n}.log", "w") for n in ("sitl", "server")}
    procs = []
    print("work dir:", work, flush=True)
    try:
        defaults = f"{ardu}/Tools/autotest/default_params/copter.parm,{REPO}/tools/sim/sim_params.parm,{work}/extra.parm"
        procs.append(subprocess.Popen([str(ardu / "build/sitl/bin/arducopter"), "-w", "--model",
                                       "x:x650.json",                         # SITL runs in work/: a relative path
                                       "--speedup", str(args.speedup), "--home", f"{QFC[0]},{QFC[1]},20,0",
                                       "--defaults", defaults, "-I0"],
                                      cwd=work, stdout=logs["sitl"], stderr=subprocess.STDOUT, start_new_session=True))
        time.sleep(3)
        server = start_server(args.python, logs["server"])
        procs.append(server)
        pilot = Pilot()
        ok = pilot.wait(lambda: (ws_state().get("ceil") or {}).get("status") == "active", 180, "ceiling active")
        check("server, map and ceil_guard.lua are up", ok, json.dumps((ws_state().get("ceil") or {}).get("status")))

        # 1. fence follows ground control
        c = ws_state()["ceil"]
        target = c["target_m"]
        ok = pilot.wait(lambda: pilot.fc("CEIL_FC") is not None and abs(pilot.fc("CEIL_FC") - target) < 0.6, 20, "fence")
        fence = pilot.read("FENCE_ALT_MAX")
        check("1. FENCE_ALT_MAX = ceiling - home - margin", ok and fence is not None and abs(fence - target) < 0.6,
              f"target {target} m, FC {fence} m, here {c['here']['ceiling_agl']} m AGL ({c['here']['reason']}), home {c['home_amsl']} m")
        check("1. FC state: following ground control", pilot.fc("CEIL_ST") == 0, str(pilot.fc("CEIL_ST")))

        # 2. NO-FLY on the ground
        now = time.time()
        air_edit({"kind": "event", "stadium": "husky", "start": now + 600, "end": now + 3 * 3600})
        ok = pilot.wait(lambda: pilot.fc("CEIL_FC") is not None and pilot.fc("CEIL_FC") <= 10.5, 20, "fence 10 m")
        st = ws_state()["ceil"]
        check("2. stadium event: NO-FLY at QFC, fence 10 m", ok and st.get("nofly"), st.get("status"))
        pilot.wait(lambda: (ws_state().get("gps_fix") or 0) >= 3, 120, "GPS")
        time.sleep(10)
        ws_send({"type": "takeoff", "alt": 3})
        time.sleep(3)
        msgs = [m["text"] for m in ws_state().get("messages", [])]
        check("2. laptop takeoff refused in NO-FLY", any("takeoff refused" in t and "NO-FLY" in t for t in msgs) and not pilot.armed,
              str(msgs[-3:]))
        d = air_edit({"kind": "remove", "list": "events", "index": 0})
        check("2. event removed", not d["events"])
        ok = pilot.wait(lambda: pilot.fc("CEIL_FC") is not None and abs(pilot.fc("CEIL_FC") - target) < 0.6, 20, "fence back")
        check("2. fence back to the ceiling", ok, str(pilot.fc("CEIL_FC")))

        # 3. in the air at 40 m in LOITER, the area becomes NO-FLY (ceiling 10 m)
        pilot.set_mode("GUIDED")
        pilot.wait(lambda: pilot.mode == "GUIDED", 10, "GUIDED")
        for _ in range(15):
            pilot.cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
            if pilot.wait(lambda: pilot.armed, 3, "arm"):
                break
        pilot.cmd(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 40)
        ok = pilot.wait(lambda: pilot.pos and pilot.pos[2] > 39, 120, "40 m")
        check("3. took off to 40 m", ok, str(pilot.pos))
        pilot.thr = 1500                                     # mid stick: LOITER holds the height
        pilot.set_mode("LOITER")
        pilot.wait(lambda: pilot.mode == "LOITER", 10, "LOITER")
        n_txt = len(pilot.texts)
        now = time.time()
        air_edit({"kind": "event", "stadium": "husky", "start": now + 600, "end": now + 3 * 3600})
        ok = pilot.wait(lambda: pilot.mode == "GUIDED" and any("too high, descend to" in t for t in pilot.texts[n_txt:]), 20,
                        "GUIDED descent")
        check("3. above the ceiling: FC changes LOITER -> GUIDED and descends", ok, f"{pilot.mode} {pilot.texts[n_txt:]}")
        modes, fence_under = set(), []
        end = time.time() + 120
        while time.time() < end and not (pilot.pos[2] < 9.0):
            modes.add(pilot.mode)
            f = pilot.fc("CEIL_FC")
            if f is not None and f < pilot.pos[2]:
                fence_under.append((round(f, 1), round(pilot.pos[2], 1)))
            time.sleep(0.3)
        check("3. descended to 2 m under the ceiling (8 m)", 7.0 < pilot.pos[2] < 9.0, f"{pilot.pos[2]:.1f} m")
        check("3. no RTL and no breach in the descent", modes == {"GUIDED"} and not any("breach" in t for t in pilot.texts[n_txt:]),
              f"{modes} {[t for t in pilot.texts[n_txt:] if 'breach' in t]}")
        check("3. fence never under the drone", not fence_under, str(fence_under[:3]))
        time.sleep(5)
        check("3. holds at the legal height in GUIDED", pilot.mode == "GUIDED" and 7.0 < pilot.pos[2] < 9.5
              and any("at the legal height" in t for t in pilot.texts[n_txt:]), f"{pilot.mode} {pilot.pos[2]:.1f} m")

        # 3b. the pilot takes over during a descent: the script stops for 30 s
        air_edit({"kind": "remove", "list": "events", "index": 0})
        pilot.wait(lambda: pilot.fc("CEIL_ST") == 0, 20, "ceiling back")
        pilot.goto_alt(40)
        pilot.wait(lambda: pilot.pos[2] > 39, 90, "40 m again")
        n_txt = len(pilot.texts)
        now = time.time()
        air_edit({"kind": "event", "stadium": "husky", "start": now + 600, "end": now + 3 * 3600})
        pilot.wait(lambda: any("too high, descend to" in t for t in pilot.texts[n_txt:]), 20, "descent start")
        time.sleep(2)
        pilot.set_mode("LOITER")
        pilot.wait(lambda: pilot.mode == "LOITER", 10, "pilot LOITER")
        modes = set()
        end = time.time() + 8
        while time.time() < end:
            modes.add(pilot.mode)
            time.sleep(0.2)
        check("3b. pilot mode change: script pauses, pilot keeps LOITER", modes == {"LOITER"}
              and any("paused" in t for t in pilot.texts[n_txt:]), f"{modes} {pilot.texts[n_txt:]}")
        check("3b. no breach while the pilot flies", not any("breach" in t for t in pilot.texts[n_txt:]))

        # 4. event removed in the air
        air_edit({"kind": "remove", "list": "events", "index": 0})
        ok = pilot.wait(lambda: pilot.fc("CEIL_FC") is not None and abs(pilot.fc("CEIL_FC") - target) < 1.0, 20, "fence up")
        check("4. fence back to the ceiling in the air", ok and pilot.fc("CEIL_ST") == 0, str(pilot.fc("CEIL_FC")))

        # 7. horizontal NO-FLY guard
        ZR = 50.0
        zc = west(QFC, 150)
        air_edit({"kind": "zone", "name": "sitl test", "lat": zc[0], "lon": zc[1], "radius_m": ZR})
        ok = pilot.wait(lambda: ((ws_state().get("ceil") or {}).get("edge") or {}).get("name", "").startswith("keep-out"),
                        20, "zone edge")
        e = (ws_state().get("ceil") or {}).get("edge") or {}
        check("7. ground control sends the zone edge", ok and abs(e.get("dist_m", 0) - (dist_m(pilot.pos, zc) - ZR)) < 3,
              f"edge {e.get('dist_m')} m, drone {dist_m(pilot.pos, zc) - ZR:.0f} m from the zone")
        pilot.wait(lambda: (pilot.fc("CEIL_NFL") or -1) > 0, 10, "CEIL_NFL")
        check("7. FC reports the distance lower bound", pilot.fc("CEIL_NFL") is not None
              and pilot.fc("CEIL_NFL") <= e.get("dist_m", 0) + 0.5, str(pilot.fc("CEIL_NFL")))
        # 7a. GUIDED goto through the zone
        pilot.set_mode("GUIDED")
        pilot.wait(lambda: pilot.mode == "GUIDED", 10, "GUIDED")
        pilot.goto_alt(30)
        pilot.wait(lambda: abs(pilot.pos[2] - 30) < 1 and dist_m(pilot.pos, QFC) < 3, 60, "QFC at 30 m")
        n_txt = len(pilot.texts)
        far = west(QFC, 320)
        pilot.goto_alt(30, *far)
        closest, modes = watch_zone(pilot, zc, ZR, 30)
        stops = [t for t in pilot.texts[n_txt:] if "NO-FLY edge" in t]
        check("7a. GUIDED goto through the zone: FC stops it, never inside", stops and closest > 0 and dist_m(pilot.pos, far) > 150,
              f"closest {closest:.1f} m from the edge, now {dist_m(pilot.pos, zc) - ZR:.1f} m, {stops[:2]}")
        check("7a. stays GUIDED (hold) after the stop", modes == {"GUIDED"}, str(modes))
        # 7b. away from the zone
        n_txt = len(pilot.texts)
        pilot.goto_alt(30)
        ok = pilot.wait(lambda: dist_m(pilot.pos, QFC) < 3, 60, "back at QFC")
        check("7b. flying away from the zone is free", ok and not any("NO-FLY edge" in t for t in pilot.texts[n_txt:]),
              str(pilot.texts[n_txt:]))
        # 7c. face west, LOITER, full pitch forward toward the zone
        pilot.cmd(mavutil.mavlink.MAV_CMD_CONDITION_YAW, 270, 45, 0, 0)
        time.sleep(8)
        pilot.set_mode("LOITER")
        pilot.wait(lambda: pilot.mode == "LOITER", 10, "LOITER")
        n_txt = len(pilot.texts)
        pilot.pitch = 1100
        closest, modes = watch_zone(pilot, zc, ZR, 30)
        pilot.pitch = 65535
        check("7c. LOITER toward the zone: FC changes to BRAKE before the edge", "BRAKE" in modes and closest > 0
              and any("NO-FLY edge" in t for t in pilot.texts[n_txt:]),
              f"closest {closest:.1f} m from the edge, modes {modes}")
        pilot.set_mode("LOITER")
        pilot.wait(lambda: pilot.mode == "LOITER", 10, "LOITER")
        d = air_edit({"kind": "remove", "list": "zones", "index": 0})
        check("7. zone removed", not d.get("zones"))
        pilot.set_mode("GUIDED")
        pilot.wait(lambda: pilot.mode == "GUIDED", 10, "GUIDED")
        pilot.goto_alt(30)
        pilot.wait(lambda: dist_m(pilot.pos, QFC) < 5, 60, "back at QFC")

        # 5. link lost: stop the server
        fb = ws_state()["ceil"]["fallback_m"]
        os.killpg(server.pid, 15)
        server.wait(10)
        t_lost = time.time()
        ok = pilot.wait(lambda: pilot.fc("CEIL_ST") == 1, 15, "fallback")
        f = pilot.read("FENCE_ALT_MAX")
        expect = min(fb, target)
        check("5. link lost: FC uses the fallback ceiling", ok and f is not None and abs(f - expect) < 0.6,
              f"after {time.time() - t_lost:.1f} s: fence {f} m, fallback {fb} m, last target {target} m")
        check("5. the drone keeps its mode (no RTL)", pilot.mode in ("GUIDED", "LOITER"), pilot.mode)

        # 6. server back
        server = start_server(args.python, logs["server"])
        procs.append(server)
        ok = pilot.wait(lambda: pilot.fc("CEIL_ST") == 0, 120, "following again")
        check("6. server back: FC follows ground control again", ok, str(pilot.fc("CEIL_FC")))
        pilot.set_mode("LAND")
        pilot.wait(lambda: not pilot.armed, 120, "landed")
        pilot.running = False
    finally:
        for p in procs:
            try:
                os.killpg(p.pid, 15)
            except Exception:
                pass
        for f in logs.values():
            f.close()
    n_ok = sum(results)
    print(f"\n{n_ok}/{len(results)} checks passed. Logs: {work}", flush=True)
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
