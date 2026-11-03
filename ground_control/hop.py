"""Hold-to-hop: while the page button is held, lift a few inches and hover WITHOUT GPS;
the moment it is released, stop the motors.

- Mode GUIDED_NOGPS (20): ArduCopter holds the attitude level (IMU) and the climb
  rate (barometer). No GPS position: it can drift sideways with wind and trim.
- The laptop streams SET_ATTITUDE_TARGET (level, nose where it is) at 25 Hz. The
  thrust field is a climb rate (0.5 = hold height).
- HEIGHT FROM THE BOX TAGS, on the FC too: the Pi sends every lid pose straight to
  the FC (VISION_POSITION_ESTIMATE, companion/cam_stream.py vision()). Before
  arming, the laptop switches the FC EKF to source set 2 (EK3_SRC2_POSXY/POSZ = 6,
  ExternalNav), so the FC holds position and height on the camera with the IMU,
  not on GPS or the barometer, and waits for "using external nav". After the hop
  it switches back to set 1. The laptop's own height is the tag height only
  (from the Pi over Wi-Fi /lid.json when it reaches it, else over the radio,
  about 2 Hz): zero = the drone on the ground, the target = that + the button
  height, and over CAM_CEILING_M above the target = motors off.
- TAGS OUT OF VIEW = MOTORS OFF: the hop needs the tags in view to start, and
  stops the motors when the camera says "no box in view", or sends no pose for
  POSE_LOST_S (radio) / POSE_LOST_WIFI_S (Wi-Fi).
- Release (the page sends hop_up, or stops sending hop_alive for KEEPALIVE_S, or
  the page closes): force disarm at once, sent 3 times, and HOP_CH back low.
- On the drone, lua/hop_guard.lua stops the motors when HOP_CH is not held high
  (laptop, page or radio gone: RC_OVERRIDE_TIME 0.3 s), over HOP_MAX_M, or over
  HOP_TILT. The laptop refuses a hop unless it hears that script (HOPG).
"""
import json
import math
import threading
import time
import urllib.request

from pymavlink import mavutil

MAV = mavutil.mavlink
GUIDED_NOGPS = 20
HOP_CH = 12                  # lua/hop_guard.lua HOP_CH
HEIGHT_MIN, HEIGHT_MAX = 0.05, 0.40   # m
KEEPALIVE_S = 0.15           # page must say "still held" this often
RATE_HZ = 25
GUARD_FRESH_S = 3.0          # HOPG from hop_guard.lua must be newer than this
MAX_OVERRIDE_TIME = 0.5      # RC_OVERRIDE_TIME must be at most this (s)
SPEED_UP, SPEED_DN = 2.5, 1.5        # m/s, ArduCopter default climb/descent for the thrust -> climb-rate mapping
CLIMB_MAX, DESCENT_MAX = 0.35, 0.25  # m/s the hop asks for at most
KP = 1.5                     # climb rate (m/s) per m of height error
ATT_MASK = 0b0000_0111       # ignore body rates: use the attitude quaternion and thrust
POSE_START_S = 1.0           # a tag pose this fresh, with the box in view, is needed to start
POSE_LOST_S = 1.2            # radio pose (about 2 Hz): none for this long = motors off
POSE_LOST_WIFI_S = 0.5       # Wi-Fi pose (about 10 Hz)
CAM_CEILING_M = 0.25         # tag height more than this above the target = motors off
SOURCE_ACK_S = 3.0           # the FC must accept the source switch this soon
HEIGHT_AGREE_M = 0.15        # FC height change vs camera height change: more than this ...
HEIGHT_AGREE_S = 1.0         # ... for this long = the FC is not on the camera = motors off
SOURCE_SET_CMD = 42007       # MAV_CMD_SET_EKF_SOURCE_SET


class Hop:
    def __init__(self, link, pilot):
        self.link, self.pilot = link, pilot
        self.lock = threading.Lock()
        self.active = False
        self.gen = 0                 # one id per hop: an old hop's loop never acts on a new one
        self.last_alive = 0.0
        self.height = 0.127
        self.yaw = 0.0
        self.h0 = None               # tag height of the drone on the ground (= 0 for the hover height)
        self.wifi = None             # (rx time, box in view, drone height above the sticker m), from /lid.json
        self.status = {"state": "idle", "height": None, "reason": None}
        threading.Thread(target=self._wifi_loop, daemon=True).start()

    # ---- tag height ------------------------------------------------------------
    def _wifi_loop(self):
        """Pose from the Pi over Wi-Fi (/lid.json, about 10 Hz) while the laptop reaches it."""
        while self.link.running:
            pi = self.link.state.get("pi_url")
            try:
                if not pi:
                    raise OSError("no Pi address")
                with urllib.request.urlopen(f"{pi}/lid.json", timeout=0.5) as r:
                    d = json.loads(r.read())
                age = d.get("now", 0) - d.get("t", 0)     # detection age on the Pi
                if age < 1.0:
                    b = d["boxes"][0] if d.get("boxes") else None
                    self.wifi = (time.time() - age, b is not None, b["drone_m"][2] if b else None)
                time.sleep(0.1)
            except Exception:
                time.sleep(1.0)

    def pose(self):
        """(rx time, box in view, drone height above the sticker m, source) of the newest tag pose, or None."""
        w = self.wifi
        r = self.link.state.get("lid")
        rr = None
        if r:
            rr = (r["rx"], r.get("box") is not None, r["drone_m"][2] if r.get("box") is not None else None, "radio")
        ww = (w[0], w[1], w[2], "wifi") if w else None
        cands = [c for c in (ww, rr) if c]
        return max(cands, key=lambda c: c[0]) if cands else None

    # ---- override and kill ----------------------------------------------------
    def _override(self, pwm):
        """HOP_CH override from MAV_GCS_SYSID 255 (the FC takes RC overrides only from it)."""
        L = self.link
        if L.sysid is None:
            return
        ch = [65535] * 18
        ch[HOP_CH - 1] = pwm
        enc = mavutil.mavlink.MAVLink(None, srcSystem=255, srcComponent=190)
        buf = enc.rc_channels_override_encode(L.sysid, L.compid, *ch).pack(enc)
        L.send(L.m.write, buf)

    def kill(self, why):
        """Motors off now: force disarm (3 times, no delay between), HOP_CH low."""
        was = self.active
        self.active = False
        for _ in range(3):
            self.link.command(MAV.MAV_CMD_COMPONENT_ARM_DISARM, 0, 21196)
        try:
            self._override(1000)
        except Exception:
            pass   # the disarm went out first; hop_guard.lua also stops the motors when HOP_CH times out
        self.link.command(SOURCE_SET_CMD, 1)   # back to the normal sources (GPS, barometer)
        if was:
            self.status = {"state": "killed", "height": self.height, "reason": why}
            self.link.note(f"Laptop: HOP MOTORS OFF ({why})", 2)

    # ---- page events ----------------------------------------------------------
    def check(self):
        s, L = self.link.state, self.link
        if not s["link"]:
            return "no link to the drone"
        if s["armed"]:
            return "already armed: the hop starts from the ground, disarmed"
        if s["sd_stop"]:
            return "SD kill switch is on stop"
        if time.time() - s.get("hop_guard_t", 0.0) > GUARD_FRESH_S:
            return "hop_guard.lua is not running on the drone (no HOPG): install it first"
        rot = s.get("rc_override_time")
        if rot is None or rot < 0 or rot > MAX_OVERRIDE_TIME:
            return f"RC_OVERRIDE_TIME is {rot}: set it to 0.3 so a lost link stops the motors fast"
        if self.pilot.busy or (self.pilot.flyto and self.pilot.flyto.active()):
            return "a takeoff or fly-to is running"
        fp = s.get("fc_params") or {}
        if fp.get("VISO_TYPE") != 1 or fp.get("EK3_SRC2_POSXY") != 6 or fp.get("EK3_SRC2_POSZ") != 6:
            return (f"the FC is not set up for camera position (VISO_TYPE {fp.get('VISO_TYPE')}, EK3_SRC2_POSXY "
                    f"{fp.get('EK3_SRC2_POSXY')}, EK3_SRC2_POSZ {fp.get('EK3_SRC2_POSZ')}; need 1, 6, 6)")
        p = self.pose()
        if p is None or time.time() - p[0] > POSE_START_S:
            return "no box camera pose (Pi camera off, or no pose over the radio or Wi-Fi)"
        if not p[1]:
            return "box tags not in view: the hover needs them for its height"
        return None

    def press(self, height):
        try:
            h = float(height)
        except (TypeError, ValueError):
            return self.link.note("Laptop: hop refused, bad height", 4)
        with self.lock:
            if self.active:
                self.last_alive = time.time()
                return
            why = self.check()
            if why:
                self.status = {"state": "refused", "height": None, "reason": why}
                return self.link.note(f"Laptop: hop refused: {why}", 4)
            self.height = max(HEIGHT_MIN, min(HEIGHT_MAX, h))
            self.h0 = self.pose()[2]          # tag height on the ground: the hover height counts from here
            self.yaw = self.link.state.get("yaw") or 0.0
            self.gen += 1
            self.active = True
            self.last_alive = time.time()
            self.status = {"state": "arming", "height": self.height, "reason": None}
            self.link.note(f"Laptop: hop to {self.height * 100:.0f} cm (GUIDED_NOGPS, no GPS). Release = motors off.", 4)
            threading.Thread(target=self._run, args=(self.gen,), daemon=True).start()

    def alive(self):
        if self.active:
            self.last_alive = time.time()

    def release(self, why="button released"):
        if self.active:
            self.kill(why)

    # ---- the hop ---------------------------------------------------------------
    def _attitude(self, climb):
        L = self.link
        thrust = 0.5 + (climb / (2 * SPEED_UP) if climb >= 0 else climb / (2 * SPEED_DN))
        y = math.radians(self.yaw) / 2                       # level, nose where it was
        q = [math.cos(y), 0.0, 0.0, math.sin(y)]
        L.send(L.m.mav.set_attitude_target_send, int(time.monotonic() * 1000) & 0xFFFFFFFF,
               L.sysid, L.compid, ATT_MASK, q, 0.0, 0.0, 0.0, max(0.0, min(1.0, thrust)))

    def _run(self, gen):
        L, s = self.link, self.link.state
        period = 1.0 / RATE_HZ

        def held():
            if not self.active or gen != self.gen:
                return False
            if time.time() - self.last_alive > KEEPALIVE_S:
                self.kill("button signal lost")
                return False
            return True

        try:
            # HOP_CH high first: hop_guard.lua would stop the motors the moment it is armed otherwise
            for _ in range(3):
                self._override(2000)
                time.sleep(0.02)
            L.set_mode("GUIDED_NOGPS")
            end = time.time() + 2.0
            while held() and s["mode"] != "GUIDED_NOGPS" and time.time() < end:
                self._override(2000)
                time.sleep(period)
            if not held():
                return
            if s["mode"] != "GUIDED_NOGPS":
                return self.kill("drone did not enter GUIDED_NOGPS")
            # FC position and height from the camera (ExternalNav, source set 2). The EKF says
            # "using external nav" only when it starts aiding from nothing; when it already has a
            # position it switches quietly, so wait for the FC to accept the command instead, and
            # check in the air that its height follows the camera (HEIGHT_AGREE_M below).
            t_switch = time.time()
            L.command(SOURCE_SET_CMD, 2)
            self.status = {"state": "camera source", "height": self.height, "reason": None}

            def ack():
                a = s.get("acks", {}).get(SOURCE_SET_CMD)
                return a if a and a[1] >= t_switch else None
            while held() and ack() is None and time.time() - t_switch < SOURCE_ACK_S:
                self._override(2000)
                time.sleep(period)
            if not held():
                return
            a = ack()
            if a is None:
                return self.kill("the FC did not answer the switch to the camera position source")
            if a[0] != MAV.MAV_RESULT_ACCEPTED:
                return self.kill(f"the FC refused the switch to the camera position source (result {a[0]})")
            # Indoors there is no GPS home, and ArduCopter will not arm without one ("AHRS: waiting for
            # home"). Give the EKF an origin from the last position the laptop knows; the camera position
            # is relative to it, so it only has to be roughly right.
            if s.get("home_lat") is None:
                lat, lon = s.get("lat_fc") or s.get("lat"), s.get("lon_fc") or s.get("lon")
                if lat is None or lon is None:
                    return self.kill("no home and no last known position to set the EKF origin from")
                L.send(L.m.mav.set_gps_global_origin_send, L.sysid, int(lat * 1e7), int(lon * 1e7),
                       int((s.get("alt_msl") or 0.0) * 1000), int(time.time() * 1e6))
                L.note(f"Laptop: EKF origin set to {lat:.6f}, {lon:.6f} (no GPS home indoors)", 4)
                end = time.time() + 3.0
                while held() and s.get("home_lat") is None and time.time() < end:
                    self._override(2000)
                    time.sleep(period)
                if not held():
                    return
            L.command(MAV.MAV_CMD_COMPONENT_ARM_DISARM, 1)
            end = time.time() + 3.0
            while held() and not s["armed"] and time.time() < end:
                self._override(2000)
                self._attitude(0.0)
                time.sleep(period)
            if not held():
                return
            if not s["armed"]:
                return self.kill("drone refused to arm (see its PreArm message)")
            self.status = {"state": "hovering", "height": self.height, "reason": None}
            cam_t, cam_h = None, None
            fc0, disagree_t = s["alt"], None                   # FC height at arming: its change must follow the camera
            while held():
                p = self.pose()
                now = time.time()
                if p is not None and p[0] != cam_t:            # a new camera pose
                    if not p[1]:
                        return self.kill("box tags out of view")
                    cam_t, cam_h = p[0], p[2]
                lost = POSE_LOST_WIFI_S if p and p[3] == "wifi" else POSE_LOST_S
                if cam_t is None or now - cam_t > lost:
                    return self.kill(f"no box camera pose for {lost:g} s")
                if not s["armed"]:
                    self.active = False
                    L.command(SOURCE_SET_CMD, 1)               # back to the normal sources
                    self.status = {"state": "killed", "height": self.height, "reason": "disarmed by the drone"}
                    return L.note("Laptop: hop ended, the drone disarmed (hop_guard.lua or the FC)", 3)
                if s["mode"] != "GUIDED_NOGPS":
                    return self.kill(f"mode changed to {s['mode']}")
                est = cam_h - self.h0                          # tag height above where it sat: camera only
                if s["alt"] is not None and fc0 is not None:
                    gap = abs((s["alt"] - fc0) - est)
                    if gap > HEIGHT_AGREE_M:
                        disagree_t = disagree_t or now
                        if now - disagree_t > HEIGHT_AGREE_S:
                            return self.kill(f"FC height does not follow the camera ({gap * 100:.0f} cm apart)")
                    else:
                        disagree_t = None
                if est > self.height + CAM_CEILING_M:
                    return self.kill(f"tag height {est * 100:.0f} cm, over {(self.height + CAM_CEILING_M) * 100:.0f} cm")
                err = self.height - est
                climb = max(-DESCENT_MAX, min(CLIMB_MAX, KP * err))
                self.status = {"state": "hovering", "height": self.height, "reason": None,
                               "height_now": round(est, 3), "pose": p[3], "pose_age": round(now - cam_t, 2)}
                self._override(2000)
                self._attitude(climb)
                time.sleep(period)
        except Exception as exc:   # never leave the motors running on an error
            if gen == self.gen:
                self.kill(f"error: {exc}")
