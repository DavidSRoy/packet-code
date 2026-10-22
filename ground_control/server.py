"""Packet V0 laptop flight control.

Owns the telemetry radio, serves the control page on http://localhost:8650 and
forwards all MAVLink traffic to QGroundControl on UDP 14550, so QGC can stay open.

Keys (earth frame, not drone frame):
  W/S = north/south, A/D = west/east, Q/E = yaw left/right, Z/X = up/down.
Movement is sent as velocity setpoints in GUIDED mode only, and only while armed
and in the air. Releasing every key brakes to a hover.
"""
import argparse
import asyncio
import json
import csv
import math
import os
import struct
import threading
import time
import urllib.request
from pathlib import Path

from aiohttp import web, WSMsgType
from pymavlink import mavutil

HERE = Path(__file__).parent
LOGS = HERE.parent / "logs"

# Hard limits. The page can lower the speeds, never raise them past these.
MAX_H = 3.0      # m/s horizontal
MAX_V = 1.0      # m/s vertical
MAX_YAW = 45.0   # deg/s
TAKEOFF_MIN, TAKEOFF_MAX = 0.5, 10.0  # m
INPUT_STALE_S = 0.4   # page input older than this counts as "no keys"
BRAKE_S = 1.5         # keep sending zero velocity this long after release

COPTER_MODES = {"STABILIZE": 0, "ALT_HOLD": 2, "GUIDED": 4, "LOITER": 5, "RTL": 6, "LAND": 9, "BRAKE": 17}
VEL_YAWRATE_MASK = 0b0000_0101_1100_0111  # use vx,vy,vz + yaw_rate; ignore pos, accel, yaw


class Link:
    """Serial link to the drone plus the shared telemetry state."""

    def __init__(self, port, baud, qgc):
        self.m = mavutil.mavlink_connection(port, baud=baud, source_system=254, source_component=190)
        self.qgc = mavutil.mavlink_connection(qgc, source_system=254) if qgc else None
        self.lock = threading.Lock()
        self.sysid = None
        self.compid = 1
        self.state = {
            "link": False, "last_hb": 0.0, "mode": "?", "armed": False,
            "alt": None, "vn": 0.0, "ve": 0.0, "vz": 0.0, "hdg": None,
            "roll": 0.0, "pitch": 0.0,
            "batt_v": None, "batt_a": None, "gps_fix": 0, "sats": 0,
            "rc_ok": False, "rssi": 0, "sd_stop": False,
            "lat": None, "lon": None, "log_file": None,
            "home_lat": None, "home_lon": None, "fence_on": None, "fence_r": None,
            "alt_msl": None, "cloud": "off",
        }
        self.messages = []          # (time, severity, text)
        stamp = time.strftime("%Y-%m-%d_%H%M%S")
        (LOGS / "tlog").mkdir(parents=True, exist_ok=True)
        (LOGS / "track").mkdir(parents=True, exist_ok=True)
        self.tlog_path = LOGS / "tlog" / f"{stamp}.tlog"
        self.tlog = open(self.tlog_path, "ab")
        self.track = open(LOGS / "track" / f"{stamp}.csv", "a", newline="")
        self.track_csv = csv.writer(self.track)
        self.track_csv.writerow(["time", "lat", "lon", "alt_msl_m", "height_m", "vn", "ve", "vd",
                                 "hdg", "mode", "armed", "batt_v", "sats"])
        self.state["log_file"] = str(self.tlog_path)
        self.last_flush = time.time()
        self.next_stream_req = 0.0
        self.running = True

    # ---- sending -------------------------------------------------------
    def send(self, fn, *args):
        with self.lock:
            fn(*args)

    def command(self, cmd, p1=0, p2=0, p3=0, p4=0, p5=0, p6=0, p7=0):
        if self.sysid is None:
            return
        self.send(self.m.mav.command_long_send, self.sysid, self.compid, cmd, 0, p1, p2, p3, p4, p5, p6, p7)

    def set_mode(self, name):
        if self.sysid is None:
            return
        self.send(self.m.mav.set_mode_send, self.sysid,
                  mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, COPTER_MODES[name])

    def velocity(self, vn, ve, vd, yaw_rate_rad):
        if self.sysid is None:
            return
        self.send(self.m.mav.set_position_target_local_ned_send, 0, self.sysid, self.compid,
                  mavutil.mavlink.MAV_FRAME_LOCAL_NED, VEL_YAWRATE_MASK,
                  0, 0, 0, vn, ve, vd, 0, 0, 0, 0, yaw_rate_rad)

    def note(self, text, sev=6):
        self.messages.append((time.time(), sev, text))
        del self.messages[:-40]

    # ---- receiving -----------------------------------------------------
    def request_streams(self):
        rates = {30: 10, 33: 5, 74: 5, 1: 2, 24: 2, 65: 2, 242: 0.2}  # ..., RC_CHANNELS, HOME_POSITION
        for msg_id, hz in rates.items():
            self.command(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, msg_id, int(1e6 / hz))
        for name in (b"FENCE_ENABLE", b"FENCE_RADIUS"):
            self.send(self.m.mav.param_request_read_send, self.sysid, self.compid, name, -1)

    def handle(self, msg):
        t = msg.get_type()
        s = self.state
        if t == "HEARTBEAT":
            if msg.type == mavutil.mavlink.MAV_TYPE_GCS or msg.autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                return
            if self.sysid is None:
                self.sysid, self.compid = msg.get_srcSystem(), msg.get_srcComponent()
                self.next_stream_req = 0
            s["last_hb"] = time.time()
            s["mode"] = mavutil.mode_string_v10(msg)
            s["armed"] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        elif t == "GLOBAL_POSITION_INT":
            s["alt"] = msg.relative_alt / 1000
            s["lat"], s["lon"] = msg.lat / 1e7, msg.lon / 1e7
            s["alt_msl"] = msg.alt / 1000
            s["vn"], s["ve"], s["vz"] = msg.vx / 100, msg.vy / 100, msg.vz / 100
            if msg.hdg != 65535:
                s["hdg"] = msg.hdg / 100
            self.track_csv.writerow([f"{time.time():.2f}", s["lat"], s["lon"], msg.alt / 1000, s["alt"],
                                     s["vn"], s["ve"], s["vz"], s["hdg"], s["mode"], int(s["armed"]),
                                     s["batt_v"], s["sats"]])
        elif t == "ATTITUDE":
            s["roll"], s["pitch"] = math.degrees(msg.roll), math.degrees(msg.pitch)
        elif t == "SYS_STATUS":
            s["batt_v"] = msg.voltage_battery / 1000 if msg.voltage_battery != 65535 else None
            s["batt_a"] = msg.current_battery / 100 if msg.current_battery != -1 else None
        elif t == "GPS_RAW_INT":
            s["gps_fix"], s["sats"] = msg.fix_type, msg.satellites_visible
        elif t == "RC_CHANNELS":
            s["rc_ok"] = msg.chancount > 0
            s["rssi"] = msg.rssi
            s["sd_stop"] = msg.chan8_raw > 1700  # SD on CH8 = motor emergency stop
        elif t == "STATUSTEXT":
            self.note(msg.text, msg.severity)
        elif t == "HOME_POSITION":
            s["home_lat"], s["home_lon"] = msg.latitude / 1e7, msg.longitude / 1e7
        elif t == "PARAM_VALUE":
            if msg.param_id == "FENCE_ENABLE":
                s["fence_on"] = msg.param_value > 0
            elif msg.param_id == "FENCE_RADIUS":
                s["fence_r"] = msg.param_value

    def run(self):
        """IO loop: drone -> state + QGC, QGC -> drone."""
        while self.running:
            busy = False
            msg = self.m.recv_msg()
            if msg is not None and msg.get_type() != "BAD_DATA":
                busy = True
                self.handle(msg)
                # .tlog format: 8-byte big-endian microsecond time, then the raw MAVLink packet
                self.tlog.write(struct.pack(">Q", int(time.time() * 1e6)) + msg.get_msgbuf())
                if self.qgc:
                    try:
                        self.qgc.write(msg.get_msgbuf())
                    except OSError:
                        pass
            if self.qgc:
                q = self.qgc.recv_msg()
                if q is not None and q.get_type() != "BAD_DATA":
                    busy = True
                    with self.lock:
                        self.m.write(q.get_msgbuf())
            now = time.time()
            if now - self.last_flush > 1:
                self.tlog.flush()
                self.track.flush()
                self.last_flush = now
            self.state["link"] = now - self.state["last_hb"] < 3
            if self.sysid is not None and now > self.next_stream_req:
                self.request_streams()
                self.next_stream_req = now + 10
            if not busy:
                time.sleep(0.003)


class Pilot:
    """Turns page input into velocity setpoints, and runs takeoff and land."""

    def __init__(self, link):
        self.link = link
        self.input = {"n": 0.0, "e": 0.0, "u": 0.0, "yaw": 0.0}
        self.input_time = 0.0
        self.speeds = {"h": 1.0, "v": 0.5, "yaw": 30.0}
        self.last_nonzero = 0.0
        self.takeoff_target = None
        self.takeoff_until = 0.0
        self.busy = False

    def set_input(self, d):
        self.input = {k: max(-1.0, min(1.0, float(d.get(k, 0)))) for k in ("n", "e", "u", "yaw")}
        self.input_time = time.time()

    def set_speeds(self, d):
        self.speeds = {
            "h": max(0.1, min(MAX_H, float(d.get("h", self.speeds["h"])))),
            "v": max(0.1, min(MAX_V, float(d.get("v", self.speeds["v"])))),
            "yaw": max(5.0, min(MAX_YAW, float(d.get("yaw", self.speeds["yaw"])))),
        }

    def taking_off(self):
        s = self.link.state
        if self.takeoff_target is None:
            return False
        if time.time() > self.takeoff_until or not s["armed"] or s["mode"] != "GUIDED":
            self.takeoff_target = None
            return False
        if s["alt"] is not None and s["alt"] >= 0.9 * self.takeoff_target:
            self.takeoff_target = None
            self.link.note("Laptop: takeoff height reached, keys active")
            return False
        return True

    def control_step(self):
        s = self.link.state
        if not (s["link"] and s["armed"] and s["mode"] == "GUIDED"):
            return
        if self.taking_off():
            return  # a velocity setpoint now would cancel the takeoff climb
        fresh = time.time() - self.input_time < INPUT_STALE_S
        i = self.input if fresh else {"n": 0, "e": 0, "u": 0, "yaw": 0}
        if any(abs(v) > 1e-3 for v in i.values()):
            self.last_nonzero = time.time()
        elif time.time() - self.last_nonzero > BRAKE_S:
            return  # idle: let GUIDED hold position by itself
        n, e = i["n"], i["e"]
        mag = math.hypot(n, e)
        if mag > 1:
            n, e = n / mag, e / mag
        h = self.speeds["h"]
        self.link.velocity(n * h, e * h, -i["u"] * self.speeds["v"], math.radians(i["yaw"] * self.speeds["yaw"]))

    def loop(self):
        while self.link.running:
            try:
                self.control_step()
            except Exception as exc:  # never let the control thread die silently
                self.link.note(f"Laptop: control error {exc}", 3)
            time.sleep(0.1)

    # ---- actions -------------------------------------------------------
    def _wait(self, cond, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.1)
        return False

    def takeoff(self, alt):
        if self.busy:
            return
        self.busy = True
        try:
            s, L = self.link.state, self.link
            alt = max(TAKEOFF_MIN, min(TAKEOFF_MAX, float(alt)))
            if not s["link"]:
                return L.note("Laptop: takeoff refused, no link to the drone", 3)
            if s["armed"]:
                return L.note("Laptop: takeoff refused, already armed", 3)
            if s["gps_fix"] < 3 or s["sats"] < 8:
                return L.note(f"Laptop: takeoff refused, GPS fix {s['gps_fix']} with {s['sats']} sats (need 3D, 8+)", 3)
            if s["sd_stop"]:
                return L.note("Laptop: takeoff refused, SD kill switch is on stop", 3)
            L.note(f"Laptop: takeoff to {alt:.1f} m")
            L.set_mode("GUIDED")
            if not self._wait(lambda: s["mode"] == "GUIDED", 4):
                return L.note("Laptop: drone did not enter GUIDED", 3)
            L.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
            if not self._wait(lambda: s["armed"], 5):
                return L.note("Laptop: drone refused to arm (see its PreArm message)", 3)
            self.takeoff_target = alt
            self.takeoff_until = time.time() + 20
            L.command(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, p7=alt)
        finally:
            self.busy = False

    def land(self):
        self.takeoff_target = None
        self.link.set_mode("LAND")
        self.link.note("Laptop: LAND")

    def rtl(self):
        self.takeoff_target = None
        self.link.set_mode("RTL")
        self.link.note("Laptop: RTL")

    def hold(self):
        """Stop and hover. Stays in GUIDED if already there; otherwise BRAKE."""
        self.input = {"n": 0, "e": 0, "u": 0, "yaw": 0}
        if self.link.state["mode"] == "GUIDED":
            self.link.velocity(0, 0, 0, 0)
        else:
            self.link.set_mode("BRAKE")
        self.link.note("Laptop: HOLD")

    def kill(self):
        # Force disarm: motors stop at once, even in the air.
        self.link.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 21196)
        self.link.note("Laptop: KILL MOTORS sent", 2)


class CloudPush:
    """Sends the drone state to the Packet telemetry API (Cloudflare Worker).

    Runs in its own thread with short timeouts, so a slow or lost internet link
    never delays flight control. Token: env PACKET_INGEST_TOKEN."""

    FIELDS = ("lat", "lon", "vn", "ve", "vz", "hdg", "roll", "pitch", "mode", "armed",
              "batt_v", "batt_a", "gps_fix", "sats", "home_lat", "home_lon")

    def __init__(self, link, url, drone_id, token, hz):
        self.link, self.token, self.period = link, token, 1.0 / hz
        self.url = f"{url.rstrip('/')}/v1/drones/{drone_id}/telemetry"
        self.last_error_note = 0.0
        link.state["cloud"] = "starting"

    def payload(self):
        s = self.link.state
        d = {k: s.get(k) for k in self.FIELDS}
        d["vd"] = d.pop("vz")
        d.update(ts=int(time.time() * 1000), link=bool(s["link"]), height=s.get("alt"), alt_msl=s.get("alt_msl"))
        return json.dumps(d).encode()

    def loop(self):
        while self.link.running:
            t0 = time.time()
            try:
                req = urllib.request.Request(self.url, data=self.payload(), method="POST", headers={
                    "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=2) as r:
                    r.read()
                self.link.state["cloud"] = "ok"
            except Exception as exc:
                self.link.state["cloud"] = "error"
                if time.time() - self.last_error_note > 30:
                    self.last_error_note = time.time()
                    self.link.note(f"Laptop: cloud push failed ({exc})", 4)
            time.sleep(max(0.0, self.period - (time.time() - t0)))


def build_app(link, pilot):
    async def index(_):
        return web.FileResponse(HERE / "static" / "index.html")

    async def ws_handler(request):
        ws = web.WebSocketResponse(heartbeat=2)
        await ws.prepare(request)

        async def push():
            while not ws.closed:
                s = dict(link.state)
                s["taking_off"] = pilot.takeoff_target is not None
                s["speeds"] = pilot.speeds
                s["messages"] = [{"t": t, "sev": sev, "text": txt} for t, sev, txt in link.messages[-15:]]
                await ws.send_str(json.dumps(s))
                await asyncio.sleep(0.2)

        pusher = asyncio.create_task(push())
        loop = asyncio.get_running_loop()
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                d = json.loads(msg.data)
                kind = d.get("type")
                if kind == "input":
                    pilot.set_input(d)
                elif kind == "speeds":
                    pilot.set_speeds(d)
                elif kind == "takeoff":
                    loop.run_in_executor(None, pilot.takeoff, d.get("alt", 1.0))
                elif kind == "land":
                    pilot.land()
                elif kind == "rtl":
                    pilot.rtl()
                elif kind == "hold":
                    pilot.hold()
                elif kind == "kill":
                    pilot.kill()
        finally:
            pilot.set_input({})  # page gone: treat as all keys released
            pusher.cancel()
        return ws

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_static("/static", HERE / "static")
    return app


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/cu.usbserial-DU0E540E", help="telemetry radio serial port")
    ap.add_argument("--baud", type=int, default=57600)
    ap.add_argument("--http", type=int, default=8650)
    ap.add_argument("--qgc", default="udpout:127.0.0.1:14550", help="forward to QGC; 'none' to turn off")
    ap.add_argument("--cloud-url", default=os.environ.get("PACKET_API_URL"),
                    help="Packet telemetry API base URL (or env PACKET_API_URL); token in env PACKET_INGEST_TOKEN")
    ap.add_argument("--drone-id", default="packet-v0")
    ap.add_argument("--cloud-hz", type=float, default=1.0)
    args = ap.parse_args()

    link = Link(args.port, args.baud, None if args.qgc == "none" else args.qgc)
    pilot = Pilot(link)
    threading.Thread(target=link.run, daemon=True).start()
    threading.Thread(target=pilot.loop, daemon=True).start()
    if args.cloud_url:
        token = os.environ.get("PACKET_INGEST_TOKEN")
        if not token:
            raise SystemExit("--cloud-url needs the env PACKET_INGEST_TOKEN")
        push = CloudPush(link, args.cloud_url, args.drone_id, token, max(0.2, min(5.0, args.cloud_hz)))
        threading.Thread(target=push.loop, daemon=True).start()
        print(f"Pushing telemetry to {push.url} at {args.cloud_hz:g} Hz")
    print(f"Packet ground control on http://localhost:{args.http}  (radio {args.port} @ {args.baud})")
    web.run_app(build_app(link, pilot), host="127.0.0.1", port=args.http, print=None)


if __name__ == "__main__":
    main()
