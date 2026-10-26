"""Packet V0 laptop flight control.

Owns the telemetry radio, serves the control page on http://localhost:8650 and
forwards all MAVLink traffic to QGroundControl on UDP 14550, so QGC can stay open.

Keys (earth frame, not drone frame):
  W/S = north/south, A/D = west/east, Q/E = yaw left/right, Z/X = up/down.
Movement is sent as velocity setpoints in GUIDED mode only, and only while armed
and in the air. Releasing every key brakes to a hover.
"""
import os
os.environ.setdefault("MAVLINK20", "1")   # MAVLink2 message set: GPS h_acc, TUNNEL, other extension fields
import argparse
import asyncio
import json
import csv
import math
import os
import struct
import sys
import threading
import time
import urllib.request
from pathlib import Path

from aiohttp import web, WSMsgType
from pymavlink import mavutil

import autonomy
import ceiling
from gps_guard import GpsGuard
from radio_snap import RadioSnap

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from airspace.service import AirspaceService  # noqa: E402
LOGS = Path(os.environ["PACKET_LOG_DIR"]) if os.environ.get("PACKET_LOG_DIR") else HERE.parent / "logs"  # tests: own folder

# Hard limits. The page can lower the speeds, never raise them past these.
MAX_H = 3.0      # m/s horizontal
MAX_V = 1.0      # m/s vertical
MAX_YAW = 45.0   # deg/s
TAKEOFF_MIN, TAKEOFF_MAX = 0.5, 10.0  # m
INPUT_STALE_S = 0.4   # page input older than this counts as "no keys"
BRAKE_S = 1.5         # keep sending zero velocity this long after release

COPTER_MODES = {"STABILIZE": 0, "ALT_HOLD": 2, "AUTO": 3, "GUIDED": 4, "LOITER": 5, "RTL": 6, "LAND": 9, "BRAKE": 17}
VEL_YAWRATE_MASK = 0b0000_0101_1100_0111  # use vx,vy,vz + yaw_rate; ignore pos, accel, yaw


HOVER_AMPS = 25.0        # X650 hover current from the 2026-10-22 flight log, one 6S 6500 mAh pack
BATT_RESERVE_PCT = 20    # time left counts down to this charge, the landing reserve


class Link:
    """Serial link to the drone plus the shared telemetry state."""

    def __init__(self, port, baud, qgc, tunnel=None):
        self.m = mavutil.mavlink_connection(port, baud=baud, source_system=254, source_component=190)
        self.qgc = mavutil.mavlink_connection(qgc, source_system=254) if qgc else None
        # SSH to the Pi over the radio (tools/mav_ssh.py): TUNNEL + HEARTBEAT out, anything back in
        self.tunnel = mavutil.mavlink_connection(tunnel, source_system=254) if tunnel else None
        self.lock = threading.Lock()
        self.sysid = None
        self.compid = 1
        self.state = {
            "link": False, "last_hb": 0.0, "mode": "?", "armed": False,
            "alt": None, "vn": 0.0, "ve": 0.0, "vz": 0.0, "hdg": None,
            "roll": 0.0, "pitch": 0.0, "yaw": None,
            "batt_v": None, "batt_a": None, "gps_fix": 0, "sats": 0,
            "batt_pct": None, "batt_mah": None, "batt_cap": None, "batt_min": None, "batt_min_basis": None,
            "rc_ok": False, "rssi": 0, "sd_stop": False, "lights_raw": None,
            "lat": None, "lon": None, "log_file": None,
            "home_lat": None, "home_lon": None, "fence_on": None, "fence_r": None,
            "alt_msl": None, "cloud": "off", "sa_on": False, "sa_raw": None,
            "lid": None,    # box camera pose from the Pi over the radio (cam_stream.py radio())
            "pi_url": None, # the Pi camera page, from the Pi's IP sent over the radio (PIIP)
            # GPS quality and the jump filter (gps_guard.py). lat/lon above are the
            # filtered position for display; lat_fc/lon_fc are what the FC reports.
            "lat_fc": None, "lon_fc": None, "gps_q": None, "gps_why": [], "gps_hdop": None,
            "gps_hacc": None, "pos_filtered": False, "pos_rejected": 0,
        }
        self.gps = GpsGuard()
        self.lid_parts = {}
        self.sa_ch = 0              # RC channel of the SA switch (0 = not set: backend control off)
        self.hooks = []             # called with every MAVLink message
        self.pos_hooks = []         # called with the state at every GLOBAL_POSITION_INT
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
        self.next_hb = 0.0
        self.running = True
        self.amp_avg = None          # filtered flight current, A
        self.amp_t = 0.0

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

    LIGHTS_PWM = {"status": 1000, "aviation": 1500, "landing": 900, "off": 2000}   # lua/lights.lua: SB top / middle / bottom; landing 900 = laptop only, below the Boxer's 988..2012

    def lights(self, mode, ch=6, gcs_sysid=255):
        """Set the arm lights with an RC override of the SB channel (LIT_CH).

        The FC takes RC overrides only from MAV_GCS_SYSID (255), so this one message
        goes out with that system id. With no receiver input the FC keeps the value;
        when the Boxer is on, its SB switch takes over again after RC_OVERRIDE_TIME (3 s)."""
        pwm = self.LIGHTS_PWM.get(mode)
        if pwm is None or self.sysid is None:
            return
        ch_vals = [65535] * 8                       # 65535 = leave the channel to the receiver
        ch_vals[ch - 1] = pwm
        enc = mavutil.mavlink.MAVLink(None, srcSystem=gcs_sysid, srcComponent=190)
        buf = enc.rc_channels_override_encode(self.sysid, self.compid, *ch_vals, *([0] * 10)).pack(enc)
        with self.lock:
            self.m.write(buf)
        self.note(f"Laptop: lights {mode}")

    def note(self, text, sev=6):
        self.messages.append((time.time(), sev, text))
        del self.messages[:-40]

    # ---- receiving -----------------------------------------------------
    def request_streams(self):
        rates = {30: 10, 33: 5, 74: 5, 1: 2, 24: 2, 65: 2, 147: 1, 42: 2, 242: 0.2, 193: 2}  # ..., MISSION_CURRENT, HOME_POSITION
        for msg_id, hz in rates.items():
            self.command(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, msg_id, int(1e6 / hz))
        for name in (b"FENCE_ENABLE", b"FENCE_RADIUS", b"BATT_CAPACITY"):
            self.send(self.m.mav.param_request_read_send, self.sysid, self.compid, name, -1)

    def handle(self, msg):
        self._handle(msg)
        for hook in self.hooks:
            hook(msg)

    def _handle(self, msg):
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
            s["lat_fc"], s["lon_fc"] = msg.lat / 1e7, msg.lon / 1e7
            shown = self.gps.on_position(s["lat_fc"], s["lon_fc"], math.hypot(msg.vx, msg.vy) / 100, s["armed"])
            s["lat"], s["lon"] = shown if shown else (s["lat_fc"], s["lon_fc"])
            s.update(self.gps.state())
            s["alt_msl"] = msg.alt / 1000
            s["vn"], s["ve"], s["vz"] = msg.vx / 100, msg.vy / 100, msg.vz / 100
            if msg.hdg != 65535:
                s["hdg"] = msg.hdg / 100
            self.track_csv.writerow([f"{time.time():.2f}", s["lat_fc"], s["lon_fc"], msg.alt / 1000, s["alt"],
                                     s["vn"], s["ve"], s["vz"], s["hdg"], s["mode"], int(s["armed"]),
                                     s["batt_v"], s["sats"]])
            for hook in self.pos_hooks:
                hook(s)
        elif t == "ATTITUDE":
            s["roll"], s["pitch"] = math.degrees(msg.roll), math.degrees(msg.pitch)
            s["yaw"] = math.degrees(msg.yaw) % 360
            self.gps.on_attitude(msg)
        elif t == "SYS_STATUS":
            s["batt_v"] = msg.voltage_battery / 1000 if msg.voltage_battery != 65535 else None
            s["batt_a"] = msg.current_battery / 100 if msg.current_battery != -1 else None
            self.filter_current()
        elif t == "BATTERY_STATUS" and msg.id == 0:
            s["batt_pct"] = msg.battery_remaining if msg.battery_remaining >= 0 else None
            s["batt_mah"] = msg.current_consumed if msg.current_consumed >= 0 else None
            self.estimate_time()
        elif t == "GPS_RAW_INT":
            s["gps_fix"], s["sats"] = msg.fix_type, msg.satellites_visible
            self.gps.on_gps_raw(msg)
            s.update(self.gps.state())
        elif t == "EKF_STATUS_REPORT":
            self.gps.on_ekf(msg)
        elif t == "RC_CHANNELS":
            s["rc_ok"] = msg.chancount > 0
            s["rssi"] = msg.rssi
            s["sd_stop"] = msg.chan8_raw > 1700  # SD on CH8 = motor emergency stop
            s["lights_raw"] = msg.chan6_raw        # SB on CH6 = lights (lua/lights.lua, LIT_CH 6)
            if 1 <= self.sa_ch <= 18:
                raw = getattr(msg, f"chan{self.sa_ch}_raw", 0)
                s["sa_raw"] = raw
                s["sa_on"] = 1700 < raw < 2200  # SA down/on = backend may fly
        elif t == "DEBUG_VECT" and msg.name.startswith("LID"):
            self.lid_update(msg)
        elif t == "DEBUG_VECT" and msg.name == "PIIP":
            a, b = divmod(int(msg.x), 256)
            c, d = divmod(int(msg.y), 256)
            s["pi_url"] = f"http://{a}.{b}.{c}.{d}:{int(msg.z)}"
        elif t == "STATUSTEXT":
            self.gps.on_text(msg.text)
            self.note(msg.text, msg.severity)
        elif t == "HOME_POSITION":
            s["home_lat"], s["home_lon"] = msg.latitude / 1e7, msg.longitude / 1e7
        elif t == "PARAM_VALUE":
            if msg.param_id == "FENCE_ENABLE":
                s["fence_on"] = msg.param_value > 0
            elif msg.param_id == "FENCE_RADIUS":
                s["fence_r"] = msg.param_value
            elif msg.param_id == "BATT_CAPACITY":
                s["batt_cap"] = msg.param_value
                self.estimate_time()

    def lid_update(self, msg):
        """Put the LID* DEBUG_VECT parts of one detection together (LIDATT comes last)."""
        p = self.lid_parts
        if p.get("us") != msg.time_usec:
            p.clear()
            p["us"] = msg.time_usec
        p[msg.name] = (msg.x, msg.y, msg.z)
        att = p.get("LIDATT")
        if att is None:
            return
        lid = {"rx": time.time(), "box": None}
        if att[0] >= 0:
            if "LIDPOS" not in p or "LIDCAM" not in p:
                return
            cam = p["LIDCAM"]
            lid.update(box=int(att[0]), yaw_deg=att[1], tilt_deg=att[2], drone_m=list(p["LIDPOS"]),
                       camera_z=cam[0], px_per_cell=cam[1], ntags=int(cam[2]))
            if "LIDRV" in p and "LIDTV" in p:     # full camera pose: the page draws the tags exactly
                lid.update(rvec=list(p["LIDRV"]), tvec=list(p["LIDTV"]))
        self.state["lid"] = lid

    def filter_current(self):
        """Average the current while flying (about 20 s), for the time-left estimate."""
        s, now = self.state, time.time()
        a = s["batt_a"]
        if s["armed"] and a is not None and a > 2.0:
            k = 1.0 if self.amp_avg is None else 1 - math.exp(-(now - self.amp_t) / 20.0)
            self.amp_avg = a if self.amp_avg is None else self.amp_avg + k * (a - self.amp_avg)
        self.amp_t = now

    def estimate_time(self):
        """Minutes of flight left until the battery reaches BATT_RESERVE_PCT.

        In flight it uses the averaged current. On the ground it uses the last
        flight average, or HOVER_AMPS before the first flight."""
        s = self.state
        if s["batt_pct"] is None or not s["batt_cap"]:
            s["batt_min"] = s["batt_min_basis"] = None
            return
        if s["armed"] and self.amp_avg:
            amps, basis = self.amp_avg, "flight"
        elif self.amp_avg:
            amps, basis = self.amp_avg, "last flight"
        else:
            amps, basis = HOVER_AMPS, "hover estimate"
        usable_mah = max(0.0, s["batt_pct"] - BATT_RESERVE_PCT) / 100 * s["batt_cap"]
        s["batt_min"] = round(usable_mah / (amps * 1000) * 60, 1)
        s["batt_min_basis"] = basis

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
            if self.tunnel:
                if msg is not None and msg.get_msgId() in (0, 385):   # HEARTBEAT, TUNNEL (by id: works in either dialect)
                    try:
                        self.tunnel.write(msg.get_msgbuf())
                    except OSError:
                        pass
                try:
                    q = self.tunnel.recv_msg()
                except OSError:
                    q = None
                if q is not None and q.get_type() != "BAD_DATA":
                    busy = True
                    with self.lock:
                        self.m.write(q.get_msgbuf())
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
            if now > self.next_hb:  # GCS heartbeat, so the drone can detect a lost laptop link
                self.send(self.m.mav.heartbeat_send, mavutil.mavlink.MAV_TYPE_GCS,
                          mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
                self.next_hb = now + 1.0
            if self.sysid is not None and now > self.next_stream_req:
                self.request_streams()
                self.next_stream_req = now + 10
            if not busy:
                time.sleep(0.003)


class Pilot:
    """Turns page input into velocity setpoints, and runs takeoff and land."""

    def __init__(self, link):
        self.link = link
        self.ceiling = None         # ceiling.CeilingLink, set by main()
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
            why = self.ceiling.takeoff_block() if self.ceiling else None
            if why:
                return L.note(f"Laptop: takeoff refused, {why}", 3)
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

    def _on_ground(self, what, mode):
        """True (and a note) when the drone is disarmed: LAND, RTL and BRAKE do not
        allow arming in ArduCopter, so on the ground they would only block the next arm."""
        if self.link.state["armed"]:
            return False
        self.link.note(f"Laptop: {what} not sent, the drone is disarmed ({mode} mode would block arming)", 4)
        return True

    def land(self):
        self.takeoff_target = None
        if self._on_ground("LAND", "LAND"):
            return
        self.link.set_mode("LAND")
        self.link.note("Laptop: LAND")

    def rtl(self):
        self.takeoff_target = None
        if self._on_ground("RTL", "RTL"):
            return
        self.link.set_mode("RTL")
        self.link.note("Laptop: RTL")

    def hold(self):
        """Stop and hover. Stays in GUIDED if already there; otherwise BRAKE."""
        self.input = {"n": 0, "e": 0, "u": 0, "yaw": 0}
        if self._on_ground("HOLD", "BRAKE"):
            return
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

    FIELDS = ("lat", "lon", "vn", "ve", "vz", "hdg", "roll", "pitch", "yaw", "mode", "armed",
              "batt_v", "batt_a", "batt_pct", "batt_mah", "batt_cap", "batt_min", "batt_min_basis",
              "gps_fix", "sats", "home_lat", "home_lon",
              "rc_ok", "rssi", "sd_stop", "sa_on", "fence_on", "fence_r",
              "lat_fc", "lon_fc", "gps_q", "gps_why", "gps_hdop", "gps_hacc", "pos_filtered")

    def __init__(self, link, url, drone_id, token, hz, auto=None, pi_url=None, cam=True):
        self.link, self.token, self.period, self.auto = link, token, 1.0 / hz, auto
        self.acks = []
        self.base = f"{url.rstrip('/')}/v1/drones/{drone_id}"
        self.url = f"{self.base}/telemetry"
        self.last_error_note = 0.0
        self.msg_sent_t = time.time() - 60   # FC messages newer than this are not sent yet
        self.pi_url = pi_url.rstrip("/") if pi_url else None    # "auto" = the address the Pi sends over the radio
        self.cam = bool(cam)
        self.wifi_lid = None                 # full box pose from the Pi over Wi-Fi (/lid.json)
        link.state["cloud"] = "starting"
        link.state["cloud_cam"] = "off" if not (self.pi_url and self.cam) else "starting"

    def box_pose(self):
        """Box camera pose: Wi-Fi (/lid.json, full detail) when fresh, else the radio pose."""
        w = self.wifi_lid
        if w and time.time() - w["rx"] < 2.0:
            b = w["boxes"][0] if w["boxes"] else None
            return {"source": "wifi", "age_s": round(time.time() - w["rx"], 1),
                    "box": None if b is None else {
                        "id": b["box"], "tags": b["tags"], "ntags": len(b["tags"]), "px_per_cell": b["px_per_cell"],
                        "drone_m": b["drone_m"], "camera_m": b["camera_m"],
                        "yaw_deg": b["yaw_deg"], "tilt_deg": b["tilt_deg"]}}
        r = self.link.state.get("lid")
        if r and time.time() - r["rx"] < 3.0:
            return {"source": "radio", "age_s": round(time.time() - r["rx"], 1),
                    "box": None if r["box"] is None else {
                        "id": r["box"], "tags": None, "ntags": r["ntags"], "px_per_cell": round(r["px_per_cell"], 1),
                        "drone_m": [round(v, 4) for v in r["drone_m"]], "camera_m": [None, None, round(r["camera_z"], 4)],
                        "yaw_deg": round(r["yaw_deg"], 1), "tilt_deg": round(r["tilt_deg"], 1)}}
        return None

    def payload(self):
        s = self.link.state
        d = {k: s.get(k) for k in self.FIELDS}
        d["vd"] = d.pop("vz")
        d.update(ts=int(time.time() * 1000), link=bool(s["link"]), height=s.get("alt"), alt_msl=s.get("alt_msl"))
        d["box_camera"] = self.box_pose()
        d["camera_live"] = s.get("cloud_cam") == "ok"
        new = [m for m in self.link.messages if m[0] > self.msg_sent_t][-20:]
        d["messages"] = [{"ts": int(t * 1000), "sev": sev, "text": txt[:200]} for t, sev, txt in new]
        if self.auto:
            d["autonomy"] = self.auto.cloud_summary()
            d["acks"], self.acks = self.acks, []
        return json.dumps(d).encode(), (new[-1][0] if new else None)

    def take_command(self, body):
        """The ingest reply can carry one backend command for the drone."""
        try:
            cmd = json.loads(body or b"{}").get("command")
        except ValueError:
            return
        if cmd and self.auto:
            self.acks.append(self.auto.handle_command(cmd, "Backend"))

    def loop(self):
        while self.link.running:
            t0 = time.time()
            try:
                body, last_msg_t = self.payload()
                req = urllib.request.Request(self.url, data=body, method="POST", headers={
                    "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=2) as r:
                    self.take_command(r.read())
                if last_msg_t:
                    self.msg_sent_t = last_msg_t
                self.link.state["cloud"] = "ok"
            except Exception as exc:
                self.link.state["cloud"] = "error"
                if time.time() - self.last_error_note > 30:
                    self.last_error_note = time.time()
                    self.link.note(f"Laptop: cloud push failed ({exc})", 4)
            time.sleep(max(0.0, self.period - (time.time() - t0)))


    def pi(self):
        return self.link.state.get("pi_url") if self.pi_url == "auto" else self.pi_url

    def lid_loop(self):
        """Full box pose from the Pi over Wi-Fi (/lid.json) for box_camera, at 4 Hz."""
        while self.link.running:
            pi = self.pi()
            try:
                if not pi:
                    raise OSError("no Pi address")
                with urllib.request.urlopen(f"{pi}/lid.json", timeout=1) as r:
                    lid = json.loads(r.read())
                if lid.get("now", 0) - lid.get("t", 0) < 1.5:
                    self.wifi_lid = dict(lid, rx=time.time())
                time.sleep(0.25)
            except Exception:
                time.sleep(2.0)

    def camera_loop(self):
        """Forward the Pi's H.264 video to the API while the laptop reaches the Pi over Wi-Fi.

        Reads the Pi's /h264 stream (companion/h264.py: frame records, the first one a
        keyframe) and POSTs the records to {base}/camera about every 0.5 s, unchanged.
        Own thread: a slow Pi or upload never delays the telemetry push or flight control.
        A failed POST drops those frames (best effort); the API keeps the frames from the
        last keyframe, so a viewer starts again at the next keyframe (1 s)."""
        hdr = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/x-packet-h264"}
        REC = struct.Struct(">IBd")
        while self.link.running:
            pi = self.pi()
            if not pi:
                self.link.state["cloud_cam"] = "no camera"
                time.sleep(2.0)
                continue
            try:
                with urllib.request.urlopen(f"{pi}/h264", timeout=3) as r:
                    batch, t_send = [], time.time() + 0.5
                    while self.link.running:
                        head = r.read(REC.size)
                        if len(head) < REC.size:
                            break
                        n = REC.unpack(head)[0]
                        data = r.read(n)
                        if len(data) < n:
                            break
                        batch.append(head + data)
                        if time.time() >= t_send:
                            body, batch, t_send = b"".join(batch), [], time.time() + 0.5
                            try:
                                req = urllib.request.Request(f"{self.base}/camera", data=body, method="POST", headers=hdr)
                                urllib.request.urlopen(req, timeout=3).read()
                                self.link.state["cloud_cam"] = "ok"
                            except Exception:
                                self.link.state["cloud_cam"] = "error"
            except Exception:
                pass
            self.link.state["cloud_cam"] = "no camera"   # the Pi is not reachable over Wi-Fi
            time.sleep(2.0)


def build_app(link, pilot, auto, air, ceil):
    async def index(_):
        return web.FileResponse(HERE / "static" / "index.html")

    async def air_overlay(_):
        png = await asyncio.get_running_loop().run_in_executor(None, air.overlay)
        if png is None:
            return web.Response(status=503, text="ceiling map not loaded yet")
        return web.Response(body=png, content_type="image/png", headers={"Cache-Control": "no-store"})

    async def air_layers(_):
        return web.json_response(air.layers())

    async def air_query(request):
        try:
            lat, lon = float(request.query["lat"]), float(request.query["lon"])
        except (KeyError, ValueError):
            return web.json_response({"error": "lat, lon needed"}, status=400)
        return web.json_response(air.query(lat, lon))

    async def air_edit(request):
        d = await request.json()
        try:
            kind = d.get("kind")
            if kind == "event":
                air.add_event(d["stadium"], float(d["start"]), float(d["end"]))
            elif kind == "auth":
                air.add_auth(d.get("name", "LAANC"), d["lat"], d["lon"], float(d["radius_m"]),
                             float(d["max_ft"]), float(d["start"]), float(d["end"]))
            elif kind == "zone":
                air.add_zone(d.get("name", "zone"), float(d["lat"]), float(d["lon"]), float(d["radius_m"]))
            elif kind == "remove":
                air.remove(d["list"], int(d["index"]))
            else:
                raise ValueError("kind must be event, auth, zone or remove")
        except (KeyError, ValueError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        link.note(f"Laptop: airspace {kind} saved")
        return web.json_response(air.layers())

    async def ws_handler(request):
        ws = web.WebSocketResponse(heartbeat=2)
        await ws.prepare(request)

        async def push():
            while not ws.closed:
                s = dict(link.state)
                s["taking_off"] = pilot.takeoff_target is not None
                s["speeds"] = pilot.speeds
                s["messages"] = [{"t": t, "sev": sev, "text": txt} for t, sev, txt in link.messages[-15:]]
                s["auto"] = auto.summary()
                s["ceil"] = ceil.state
                if s["lid"]:
                    s["lid"] = dict(s["lid"], age=time.time() - s["lid"]["rx"])
                await ws.send_str(json.dumps(s))
                await asyncio.sleep(0.1)  # 10 Hz, same as the ATTITUDE stream

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
                elif kind == "lights":
                    link.lights(d.get("mode"))
                elif kind == "rec_start":
                    why = auto.recorder.start(d.get("from"), d.get("to"))
                    if why:
                        link.note(f"Laptop: recording not started: {why}", 4)
                elif kind == "rec_cancel":
                    auto.recorder.cancel()
                elif kind == "approve":
                    if auto.store.set_approved(d.get("from"), d.get("to"), bool(d.get("ok"))):
                        link.note(f"Laptop: route {d.get('from')} -> {d.get('to')} "
                                  + ("APPROVED" if d.get("ok") else "approval removed"))
                elif kind == "trip":  # same commands as the backend, from this page
                    auto.handle_command({"id": None, "action": d.get("action"), "pad": d.get("pad")}, "Laptop")
        finally:
            pilot.set_input({})  # page gone: treat as all keys released
            pusher.cancel()
        return ws

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/airspace/overlay.png", air_overlay)
    app.router.add_get("/airspace/layers.json", air_layers)
    app.router.add_get("/airspace/query", air_query)
    app.router.add_post("/airspace/edit", air_edit)
    app.router.add_static("/static", HERE / "static")
    return app


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/cu.usbserial-DU0E540E", help="telemetry radio serial port")
    ap.add_argument("--baud", type=int, default=115200, help="radio serial speed; FC SERIAL1_BAUD and both SiK radios SERIAL_SPEED are 115 (2026-10-25)")
    ap.add_argument("--http", type=int, default=8650)
    ap.add_argument("--qgc", default="udpout:127.0.0.1:14550", help="forward to QGC; 'none' to turn off")
    ap.add_argument("--tunnel", default="udpout:127.0.0.1:14560",
                    help="SSH-over-radio link for tools/mav_ssh.py; 'none' to turn off")
    ap.add_argument("--cloud-url", default=os.environ.get("PACKET_API_URL"),
                    help="Packet telemetry API base URL (or env PACKET_API_URL); token in env PACKET_INGEST_TOKEN")
    ap.add_argument("--drone-id", default="packet-v0")
    ap.add_argument("--cloud-hz", type=float, default=1.0)
    ap.add_argument("--pi-url", default="auto",
                    help="the Pi camera (companion/cam_stream.py), sent to the API when reachable. "
                         "'auto' = the IP the Pi sends over the radio; 'none' to turn off")
    ap.add_argument("--radio-snap", type=int, default=1,
                    help="1 = box camera snapshots over the radio when the Pi is not on Wi-Fi (telemetry first); 0 = off")
    ap.add_argument("--cloud-cam", type=int, default=1, help="1 = forward the Pi H.264 video (about 1.5 Mbit/s) to the API when reachable; 0 = off")
    ap.add_argument("--sa-ch", type=int, default=int(os.environ.get("PACKET_SA_CH", 5)),
                    help="RC channel of the SA switch, CH5 on the Boxer (backend control allowed when high). 0 = backend control off")
    ap.add_argument("--routes", default=str(autonomy.ROUTES), help="folder for pads.json and routes")
    ap.add_argument("--ceiling", choices=("auto", "off"), default="auto",
                    help="auto: send the legal ceiling to lua/ceil_guard.lua on the FC (sets FENCE_ALT_MAX)")
    ap.add_argument("--home-offset", type=float, default=0.0,
                    help="m to add to the home height (a pad on a structure the map does not know)")
    ap.add_argument("--region", default=None,
                    help="ceiling map area 'south,west,north,east' (default: greater Seattle)")
    args = ap.parse_args()

    link = Link(args.port, args.baud, None if args.qgc == "none" else args.qgc,
                None if args.tunnel == "none" else args.tunnel)
    pilot = Pilot(link)
    auto = autonomy.Autonomy(link, args.sa_ch, args.routes)
    region = tuple(float(v) for v in args.region.split(",")) if args.region else None
    air = (AirspaceService(region, log=print) if region else AirspaceService(log=print)).start()
    ceil = ceiling.CeilingLink(link, air, enabled=args.ceiling == "auto", home_offset_m=args.home_offset)
    pilot.ceiling = ceil
    auto.runner.route_check = lambda route, pad: ceiling.check_route(air, route, pad)
    ceil.start()
    threading.Thread(target=link.run, daemon=True).start()
    threading.Thread(target=pilot.loop, daemon=True).start()
    snap = None
    if args.radio_snap:
        pi_fn = (lambda: link.state.get("pi_url")) if args.pi_url == "auto" else \
                (lambda: None if args.pi_url == "none" else args.pi_url)
        snap = RadioSnap(link, pi_fn)
        threading.Thread(target=snap.loop, daemon=True).start()
    if args.cloud_url:
        token = os.environ.get("PACKET_INGEST_TOKEN")
        if not token:
            raise SystemExit("--cloud-url needs the env PACKET_INGEST_TOKEN")
        pi_url = None if args.pi_url == "none" else args.pi_url
        push = CloudPush(link, args.cloud_url, args.drone_id, token, max(0.2, min(5.0, args.cloud_hz)), auto,
                         pi_url, args.cloud_cam == 1)
        threading.Thread(target=push.loop, daemon=True).start()
        print(f"Pushing telemetry to {push.url} at {args.cloud_hz:g} Hz")
        if push.pi_url:
            threading.Thread(target=push.lid_loop, daemon=True).start()
        if push.pi_url and push.cam:
            threading.Thread(target=push.camera_loop, daemon=True).start()
            print(f"Forwarding the Pi H.264 video ({push.pi_url}) when reachable")
    print(f"Packet ground control on http://localhost:{args.http}  (radio {args.port} @ {args.baud})")
    if not args.sa_ch:
        print("SA channel not set (--sa-ch): backend trips are refused")
    print(f"Legal ceiling: {args.ceiling} (the map loads in the background)")
    app = build_app(link, pilot, auto, air, ceil)

    async def radio_snap_jpg(_):
        """The last box camera snapshot that came over the radio (radio_snap.py)."""
        if not snap or not snap.jpg:
            return web.Response(status=404, text="no radio snapshot yet")
        kind = "image/webp" if snap.jpg[:4] == b"RIFF" and snap.jpg[8:12] == b"WEBP" else "image/jpeg"
        return web.Response(body=snap.jpg, content_type=kind, headers={"Cache-Control": "no-store"})
    app.router.add_get("/radio_snap.jpg", radio_snap_jpg)
    web.run_app(app, host="127.0.0.1", port=args.http, print=None)


if __name__ == "__main__":
    main()
