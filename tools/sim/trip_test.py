"""End-to-end test of backend pad-to-pad trips in ArduPilot SITL.

It starts: the cloud API (wrangler dev), ArduCopter SITL with sa_guard.lua,
and the ground control server. Then it:
  1. teaches the route QFC -> UPLACE with a "pilot" that flies by GUIDED commands,
  2. approves both built routes,
  3. checks that a goto is refused while SA is off,
  4. flies UPLACE -> QFC from a cloud command, with a 9 s laptop link loss
     in the middle (the trip must continue),
  5. flies QFC -> UPLACE with hold and resume from the cloud,
  6. starts UPLACE -> QFC again and turns SA off in the air: the drone must
     stop in BRAKE and hold height with the throttle stick at the bottom,
     then change to LOITER when the pilot centers the throttle.

Run (the ArduPilot tree must have build/sitl/bin/arducopter):
  python tools/sim/trip_test.py --ardupilot ~/ardupilot
"""
import argparse
import asyncio
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import aiohttp
from pymavlink import mavutil

REPO = Path(__file__).resolve().parents[2]
QFC = (47.6625238, -122.2950755)      # pad A: home of the simulation
UPLACE = (47.6640000, -122.2990000)   # pad B: about 360 m north-west (simulation only)
API = "http://127.0.0.1:8787"
HTTP = 8651
ING, CMD, READ = "dev-ingest-token", "dev-command-token", "dev-read-token"

results = []


def check(name, ok, extra=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name} {extra}", flush=True)


def dist(a, b):
    k = 111_320.0
    return math.hypot((a[0] - b[0]) * k, (a[1] - b[1]) * k * math.cos(math.radians(a[0])))


def http(method, path, token, body=None):
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def ws_send(msg):
    async def go():
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"http://127.0.0.1:{HTTP}/ws") as ws:
                await ws.send_str(json.dumps(msg))
                await asyncio.sleep(0.3)
    asyncio.run(go())


def ws_state():
    async def go():
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"http://127.0.0.1:{HTTP}/ws") as ws:
                m = await ws.receive(timeout=5)
                return json.loads(m.data)
    return asyncio.run(go())


class Pilot:
    """Second MAVLink link: plays the human pilot and the RC radio (SA on ch9)."""

    def __init__(self):
        self.m = mavutil.mavlink_connection("tcp:127.0.0.1:5762", source_system=255, source_component=190)
        self.m.wait_heartbeat(timeout=60)
        self.sa = 1000
        self.thr = 1000          # throttle stick: bottom, as a pilot leaves it during AUTO
        self.pos = None
        self.mode = None
        self.armed = False
        self.texts = []
        self.running = True
        self.lock = threading.Lock()
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
            elif t == "STATUSTEXT":
                self.texts.append(msg.text)
                print("   drone:", msg.text, flush=True)

    def _rc(self):
        while self.running:
            with self.lock:
                # ch8 = SD kill switch at "run" (1000), ch9 = SA
                self.m.mav.rc_channels_override_send(1, 1, 65535, 65535, self.thr, *([65535] * 4), 1000, self.sa, *([0] * 9))
            time.sleep(0.1)

    def param(self, name, value):
        with self.lock:
            self.m.mav.param_set_send(1, 1, name.encode(), float(value), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)

    def set_mode(self, name):
        modes = {"GUIDED": 4, "LAND": 9, "LOITER": 5}
        with self.lock:
            self.m.mav.set_mode_send(1, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, modes[name])

    def goto(self, lat, lon, alt):
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

    def fly_to(self, lat, lon, alt, tol=3.0):
        self.goto(lat, lon, alt)
        return self.wait(lambda: self.pos and dist(self.pos, (lat, lon)) < tol and abs(self.pos[2] - alt) < 1.5,
                         180, f"reach {lat},{lon},{alt}")


def wait_cmd(cid, statuses, timeout):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        _, c = http("GET", f"/v1/drones/packet-v0/commands/{cid}", READ)
        if c.get("status") != last:
            last = c.get("status")
            print(f"   command {cid}: {last} {c.get('reason') or ''}", flush=True)
        if last in statuses:
            return c
        time.sleep(1)
    return {"status": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ardupilot", required=True)
    ap.add_argument("--python", default=sys.executable, help="python with pymavlink + aiohttp for the server")
    ap.add_argument("--speedup", type=int, default=3)
    args = ap.parse_args()
    ardu = Path(args.ardupilot).expanduser()
    work = Path(tempfile.mkdtemp(prefix="packet_sim_"))
    (work / "scripts").mkdir()
    shutil.copy(REPO / "lua" / "sa_guard.lua", work / "scripts")
    routes = work / "routes"
    procs = []
    logs = {n: open(work / f"{n}.log", "w") for n in ("wrangler", "sitl", "server")}
    print("work dir:", work, flush=True)
    try:
        procs.append(subprocess.Popen(["npx", "wrangler", "dev", "--port", "8787"], cwd=REPO / "cloud" / "telemetry-api",
                                      stdout=logs["wrangler"], stderr=subprocess.STDOUT, start_new_session=True))
        defaults = f"{ardu}/Tools/autotest/default_params/copter.parm,{REPO}/tools/sim/sim_params.parm"
        procs.append(subprocess.Popen([str(ardu / "build/sitl/bin/arducopter"), "-w", "--model", "quad",
                                       "--speedup", str(args.speedup), "--home", f"{QFC[0]},{QFC[1]},20,0",
                                       "--defaults", defaults, "-I0"],
                                      cwd=work, stdout=logs["sitl"], stderr=subprocess.STDOUT, start_new_session=True))
        for _ in range(60):
            try:
                urllib.request.urlopen(API + "/v1/health", timeout=1)
                break
            except Exception:
                time.sleep(1)
        time.sleep(2)
        env = dict(os.environ, PACKET_INGEST_TOKEN=ING)
        server = subprocess.Popen([args.python, "-u", str(REPO / "ground_control/server.py"), "--port", "tcp:127.0.0.1:5760",
                                   "--qgc", "none", "--http", str(HTTP), "--sa-ch", "9", "--routes", str(routes),
                                   "--cloud-url", API], env=env, stdout=logs["server"], stderr=subprocess.STDOUT,
                                  start_new_session=True)
        procs.append(server)
        pilot = Pilot()
        pilot.param("SAG_CH", 9)
        print("waiting for GPS and EKF ...", flush=True)
        ok = pilot.wait(lambda: ws_state().get("gps_fix", 0) >= 3 and ws_state().get("batt_pct") is not None, 120, "GPS")
        time.sleep(15)  # EKF settles
        check("simulator, server and cloud are up", ok)

        # 1. teach QFC -> UPLACE
        ws_send({"type": "rec_start", "from": "qfc", "to": "uplace"})
        time.sleep(4)
        pilot.set_mode("GUIDED")
        pilot.wait(lambda: pilot.mode == "GUIDED", 10, "GUIDED")
        for _ in range(10):
            pilot.cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
            if pilot.wait(lambda: pilot.armed, 3, "arm"):
                break
        pilot.cmd(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 12)
        pilot.wait(lambda: pilot.pos and pilot.pos[2] > 11, 60, "takeoff")
        pilot.fly_to(QFC[0], UPLACE[1], 20)           # west first
        pilot.fly_to(UPLACE[0], UPLACE[1], 20)        # then north to the pad
        pilot.fly_to(UPLACE[0], UPLACE[1], 4)
        pilot.set_mode("LAND")
        pilot.wait(lambda: not pilot.armed, 120, "landed + disarmed")
        time.sleep(8)
        st = ws_state()["auto"]
        names = {(r["from"], r["to"]): r for r in st["routes"]}
        check("teach flight built both routes", ("qfc", "uplace") in names and ("uplace", "qfc") in names,
              str([(k, v["length_m"], v["problems"]) for k, v in names.items()]))
        check("pads recorded", set(st["pads"]) == {"qfc", "uplace"} and dist((st["pads"]["qfc"]["lat"], st["pads"]["qfc"]["lon"]), QFC) < 2,
              json.dumps(st["pads"]))
        check("drone is on pad uplace", st["pad"] == "uplace", str(st["pad"]))

        # 2. not approved yet -> refused, then approve
        pilot.sa = 2000
        time.sleep(2)
        code, r = http("POST", "/v1/drones/packet-v0/commands", CMD, {"action": "goto", "pad": "qfc"})
        c = wait_cmd(r["command"]["id"], ("rejected", "in_progress"), 20)
        check("unapproved route is refused", c["status"] == "rejected" and "not approved" in (c.get("reason") or ""))
        ws_send({"type": "approve", "from": "qfc", "to": "uplace", "ok": True})
        ws_send({"type": "approve", "from": "uplace", "to": "qfc", "ok": True})

        # 3. SA off -> refused
        pilot.sa = 1000
        time.sleep(2)
        code, r = http("POST", "/v1/drones/packet-v0/commands", CMD, {"action": "goto", "pad": "qfc"})
        c = wait_cmd(r["command"]["id"], ("rejected", "in_progress"), 20)
        check("SA off: goto refused", c["status"] == "rejected" and "SA" in (c.get("reason") or ""))
        code, _ = http("POST", "/v1/drones/packet-v0/commands", READ, {"action": "goto", "pad": "qfc"})
        check("read token cannot send commands", code == 401)

        # 4. UPLACE -> QFC with a laptop link loss on the way
        pilot.sa = 2000
        time.sleep(2)
        code, r = http("POST", "/v1/drones/packet-v0/commands", CMD, {"action": "goto", "pad": "qfc"})
        check("goto accepted by the API", code == 202)
        cid = r["command"]["id"]
        c = wait_cmd(cid, ("in_progress", "rejected", "failed"), 30)
        check("trip uplace -> qfc started", c["status"] == "in_progress")
        pilot.wait(lambda: pilot.pos and pilot.pos[2] > 15 and pilot.mode == "AUTO", 90, "cruise")
        print("   pausing the laptop server for 9 s (radio link lost) ...", flush=True)
        os.killpg(server.pid, signal.SIGSTOP)
        time.sleep(9)
        mode_during = pilot.mode
        os.killpg(server.pid, signal.SIGCONT)
        check("laptop link lost: trip continues in AUTO", mode_during == "AUTO", f"mode {mode_during}")
        c = wait_cmd(cid, ("done", "failed", "stopped_by_pilot"), 300)
        pilot.wait(lambda: not pilot.armed, 60, "disarm")
        err = dist(pilot.pos, QFC)
        check("arrived at qfc", c["status"] == "done", c["status"])
        check("landed within 2 m of the qfc pad", err < 2.0, f"{err:.2f} m")

        # 5. QFC -> UPLACE with hold and resume
        time.sleep(3)
        code, r = http("POST", "/v1/drones/packet-v0/commands", CMD, {"action": "goto", "pad": "uplace"})
        cid = r["command"]["id"]
        wait_cmd(cid, ("in_progress",), 30)
        pilot.wait(lambda: pilot.pos and pilot.pos[2] > 15 and dist(pilot.pos, QFC) > 60, 120, "cruise")
        http("POST", "/v1/drones/packet-v0/commands", CMD, {"action": "hold"})
        pilot.wait(lambda: pilot.mode == "BRAKE", 10, "BRAKE")
        time.sleep(5)  # braking from cruise speed takes a few metres
        p1 = pilot.pos
        time.sleep(6)
        moved = dist(pilot.pos, p1)
        alt_hold = pilot.pos[2]
        check("hold: drone stops in BRAKE (throttle stick at bottom)", pilot.mode == "BRAKE" and moved < 1.0
              and abs(alt_hold - p1[2]) < 1.0, f"moved {moved:.1f} m, height {p1[2]:.1f} -> {alt_hold:.1f} m in 6 s")
        http("POST", "/v1/drones/packet-v0/commands", CMD, {"action": "resume"})
        pilot.wait(lambda: pilot.mode == "AUTO", 10, "AUTO")
        check("resume: back in AUTO", pilot.mode == "AUTO")
        pilot.wait(lambda: not pilot.armed, 300, "landed at uplace")
        time.sleep(3)
        err = dist(pilot.pos, UPLACE)
        check("landed within 2 m of the uplace pad", err < 2.0, f"{err:.2f} m")
        st = ws_state()["auto"]
        check("drone is on pad uplace again", st["pad"] == "uplace", str(st["pad"]))

        # 6. SA off in the air: the Lua guard must stop the trip
        time.sleep(3)
        code, r = http("POST", "/v1/drones/packet-v0/commands", CMD, {"action": "goto", "pad": "qfc"})
        cid = r["command"]["id"]
        wait_cmd(cid, ("in_progress",), 30)
        pilot.wait(lambda: pilot.pos and pilot.pos[2] > 12 and pilot.mode == "AUTO", 90, "climb")
        t0 = time.time()
        pilot.sa = 1000
        pilot.wait(lambda: pilot.mode == "BRAKE", 5, "BRAKE after SA off")
        dt = time.time() - t0
        check("SA off in flight: BRAKE", pilot.mode == "BRAKE", f"after {dt:.1f} s")
        check("sa_guard sent its message", any("SA off: backend control stopped" in t for t in pilot.texts))
        time.sleep(4)  # BRAKE first stops the climb (about 3 m at 2.5 m/s)
        h0 = pilot.pos[2]
        time.sleep(5)
        check("BRAKE holds height with the throttle stick at the bottom", pilot.mode == "BRAKE" and abs(pilot.pos[2] - h0) < 1.0,
              f"{h0:.1f} -> {pilot.pos[2]:.1f} m")
        pilot.thr = 1500
        pilot.wait(lambda: pilot.mode == "LOITER", 5, "LOITER after throttle centered")
        check("throttle centered: LOITER, pilot has control", pilot.mode == "LOITER")
        c = wait_cmd(cid, ("stopped_by_pilot",), 15)
        check("command shows stopped_by_pilot", c["status"] == "stopped_by_pilot")
        code, r = http("POST", "/v1/drones/packet-v0/commands", CMD, {"action": "resume"})
        c = wait_cmd(r["command"]["id"], ("rejected", "accepted"), 15)
        check("resume refused while SA is off", c["status"] == "rejected")
        code, st = http("GET", "/v1/drones/packet-v0/state", READ)
        check("API state has the autonomy block", st.get("autonomy", {}).get("backend_control_allowed") is False
              and "qfc" in st["autonomy"]["pads"], json.dumps(st.get("autonomy"))[:200])
        pilot.set_mode("LAND")
        pilot.wait(lambda: not pilot.armed, 120, "land")
    finally:
        for p in procs:
            try:
                os.killpg(p.pid, signal.SIGCONT)
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for f in logs.values():
            f.close()
    n_fail = results.count(False)
    print(f"{len(results) - n_fail}/{len(results)} passed" + ("" if not n_fail else f", {n_fail} FAILED"),
          f"(logs in {work})", flush=True)
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
