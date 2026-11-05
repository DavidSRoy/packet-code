"""Hover on the box camera: climb straight up a set distance and hold locked over the exact
spot it started from, on the box camera and the IMU only (no GPS, compass or barometer).

- Run test (the page button now): a timed run with no button held. It holds at the height for
  the set time, descends at CLIMB_MPS to LAND_BELOW_M under the start and stops the motors once
  the tags put it back down. The pilot stays at the Boxer SD kill; the page Stop button, a page
  close, hop_guard.lua (link lost) and every cut below still stop the motors.
- Hold to hover (press without a duration): only while the button is held; release = motors off.

- Camera navigation: the Pi sends every lid pose straight to the FC
  (VISION_POSITION_ESTIMATE, companion/cam_stream.py vision(), 10 Hz). Before arming,
  the laptop switches the FC EKF to source set 2 (EK3_SRC2_POSXY/POSZ/YAW = 6,
  ExternalNav): position, height and heading from the camera, with the IMU between
  frames. It waits for the FC to accept the switch. After the hover it switches back
  to set 1. Indoors with no GPS home, it gives the EKF an origin from the last known
  position: only a map label, the camera position is relative to it.
- Start point: the FC's own camera-based position (LOCAL_POSITION_NED) just before
  arming. Then GUIDED and arm: lua/hop_takeoff.lua on the FC flies the takeoff (holds
  the start point on the skids, lifts off, hands over to position control, HOPT 4).
  Then the laptop locks a position target exactly over the start point
  (SET_POSITION_TARGET_LOCAL_NED, heading held) and climbs it at CLIMB_MPS to the
  button height. The FC holds it against drift and rotation by itself.
- The laptop watches with the tags directly: height = tag height above where it sat
  (zero = on the ground); sideways drift = the tag position against where it started.
- MOTORS OFF when: the button is released (hop_up, or no hop_alive for KEEPALIVE_S, or
  the page closes: force disarm, sent 3 times, and HOP_CH low); the tags are out of view
  or no pose for POSE_LOST_S / POSE_LOST_WIFI_S; tag height over target + CAM_CEILING_M;
  drift over DRIFT_MAX_M; the FC height does not follow the camera (HEIGHT_AGREE_M);
  the mode changes.
- On the drone, lua/hop_guard.lua latches on when HOP_CH goes high while armed and stops
  the motors when HOP_CH is not high (laptop, page or radio gone: RC_OVERRIDE_TIME 0.3 s),
  over HOP_MAX_M, or over HOP_TILT. The laptop refuses unless it hears that script (HOPG)
  and lua/hop_takeoff.lua (HOPT).
"""
import json
import math
import threading
import time
import urllib.request

from pymavlink import mavutil

MAV = mavutil.mavlink
HOP_CH = 12                  # lua/hop_guard.lua HOP_CH
HEIGHT_MIN, HEIGHT_MAX = 0.01, 0.38   # m above where it sat (a 1-3 cm hover: just clear of the skids)
KEEPALIVE_S = 0.15           # page must say "still held" this often (hold to hover)
TEST_MIN_S, TEST_MAX_S = 5.0, 120.0   # test run: time held at the height
LAND_BELOW_M = 0.02          # test run descent: to this far under the start (pressed onto its legs) ...
LAND_DONE_M = 0.005          # ... motors off once the tags put it this close to the start height ...
LAND_HOLD_S = 0.5            # ... for this long
LAND_EXTRA_S = 2.0           # or this long after the descent target reached the bottom
TEST_DONE = "test run done: landed, motors off"
RATE_HZ = 25
GUARD_FRESH_S = 3.0          # HOPG from hop_guard.lua must be newer than this
MAX_OVERRIDE_TIME = 0.5      # RC_OVERRIDE_TIME must be at most this (s)
POS_YAW_MASK = 0b0000_1001_1111_1000    # SET_POSITION_TARGET: use x, y, z and yaw; ignore velocity, acceleration, yaw rate
CLIMB_MPS = 0.05             # climb rate after the handover (a fast climb blurred the tags out of detection, 2026-11-02)
DRIFT_MAX_M = 0.20           # tags say it moved this far sideways from the start = motors off
POSE_START_S = 1.0           # a tag pose this fresh, with the box in view, is needed to start
POSE_LOST_S = 1.2            # radio pose (about 2 Hz): none for this long = motors off
POSE_LOST_WIFI_S = 0.5       # Wi-Fi pose (about 10 Hz)
CAM_CEILING_M = 0.25         # tag height more than this above the target = motors off
ZERO_PAYLOAD_TYPE = 39003    # TUNNEL to the Pi: zero the FC on the box camera (cam_stream.py)
ZERO_ACK_S = 2.0             # the Pi must answer the zero this soon
SETTLE_M = 0.03              # after the zero: FC position within this of the tags' ...
SETTLE_V = 0.03              # ... and FC speed under this, m/s ...
SETTLE_HOLD_S = 1.0          # ... staying there this long (it can pass through on its way) ...
SETTLE_SPREAD_M = 0.004      # ... with the FC x and y each inside this band over the last SETTLE_HOLD_S
                             # (the EKF still walks for a few s after the source switch and the zero) ...
SETTLE_S = 10.0              # ... within this long, before the start point is taken and it arms
TAKEOFF_S = 10.0             # no handover from lua/hop_takeoff.lua this long after arming = motors off (it takes about 3 s)
RESEND_S = 0.5               # setup commands are sent again this often until the FC confirms
ORIGIN_ASK_S = 1.5           # the FC must answer the EKF origin request this soon (or it has none)
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
        self.test_s = None           # a timed test run (Run test button): hold this long, land, motors off
        self.height = 0.127
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
                    self.wifi = (time.time() - age, b is not None, b["drone_m"][2] if b else None,
                                 b["drone_m"][0] if b else None, b["drone_m"][1] if b else None)
                time.sleep(0.1)
            except Exception:
                time.sleep(1.0)

    def pose(self):
        """(rx time, box in view, height above the sticker m, source, along m, across m) of the newest tag pose, or None."""
        w = self.wifi
        r = self.link.state.get("lid")
        rr = None
        if r:
            seen = r.get("box") is not None
            d = r["drone_m"] if seen else (None, None, None)
            rr = (r["rx"], seen, d[2], "radio", d[0], d[1])
        ww = (w[0], w[1], w[2], "wifi", w[3], w[4]) if w else None
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
        if was and why == TEST_DONE:
            self.status = {"state": "done", "height": self.height, "reason": why}
            self.link.note(f"Laptop: {why}", 5)
        elif was:
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
        if time.time() - (s.get("hopt") or (None, 0.0))[1] > GUARD_FRESH_S:
            return "hop_takeoff.lua is not running on the drone (no HOPT): install it first"
        rot = s.get("rc_override_time")
        if rot is None or rot < 0 or rot > MAX_OVERRIDE_TIME:
            return f"RC_OVERRIDE_TIME is {rot}: set it to 0.3 so a lost link stops the motors fast"
        if self.pilot.busy or (self.pilot.flyto and self.pilot.flyto.active()):
            return "a takeoff or fly-to is running"
        fp = s.get("fc_params") or {}
        need = {"VISO_TYPE": 1, "EK3_SRC2_POSXY": 6, "EK3_SRC2_POSZ": 6, "EK3_SRC2_YAW": 6}
        if any(fp.get(k) != v for k, v in need.items()):
            have = ", ".join(f"{k} {fp.get(k)}" for k in need)
            return f"the FC is not set up for camera navigation ({have}; need 1, 6, 6, 6)"
        p = self.pose()
        if p is None or time.time() - p[0] > POSE_START_S:
            return "no box camera pose (Pi camera off, or no pose over the radio or Wi-Fi)"
        if not p[1]:
            return "box tags not in view: the hover needs them for its height"
        return None

    def press(self, height, duration=None):
        """Start a hover. With duration (s): a timed test run that holds at the height that long,
        descends and stops the motors itself, with no button held (the Boxer SD kill, the Stop
        button, hop_guard.lua and the safety cuts stay). Without: hold to hover."""
        try:
            h = float(height)
            test_s = None if duration is None else max(TEST_MIN_S, min(TEST_MAX_S, float(duration)))
        except (TypeError, ValueError):
            return self.link.note("Laptop: hop refused, bad height or duration", 4)
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
            self.test_s = test_s
            self.gen += 1
            self.active = True
            self.last_alive = time.time()
            self.status = {"state": "arming", "height": self.height, "reason": None}
            if test_s is None:
                self.link.note(f"Laptop: hover {self.height * 100:.0f} cm over the start (camera + IMU, GUIDED). "
                               "Release = motors off.", 4)
            else:
                self.link.note(f"Laptop: test run, {self.height * 100:.0f} cm for {test_s:.0f} s, then it lands. "
                               "Stop button or SD = motors off.", 4)
            threading.Thread(target=self._run, args=(self.gen,), daemon=True).start()

    def alive(self):
        if self.active:
            self.last_alive = time.time()

    def release(self, why="button released"):
        if self.active:
            self.kill(why)

    # ---- the hover --------------------------------------------------------------
    def _hold_target(self, start, yaw, height=None):
        """Position target exactly over the start point, at the button height (local NED, z down),
        nose on the start heading (rad)."""
        L = self.link
        L.send(L.m.mav.set_position_target_local_ned_send, 0, L.sysid, L.compid,
               MAV.MAV_FRAME_LOCAL_NED, POS_YAW_MASK, start[0], start[1],
               start[2] - (self.height if height is None else height),
               0, 0, 0, 0, 0, 0, yaw, 0)

    def _run(self, gen):
        L, s = self.link, self.link.state
        period = 1.0 / RATE_HZ

        def held():
            if not self.active or gen != self.gen:
                return False
            if self.test_s is None and time.time() - self.last_alive > KEEPALIVE_S:
                self.kill("button signal lost")
                return False
            return True

        def wait(cond, timeout):
            end = time.time() + timeout
            while held() and not cond() and time.time() < end:
                self._override(2000)
                time.sleep(period)
            return held()

        def keep(cond, send, timeout):
            """Send, and send again every RESEND_S until cond() or timeout: the radio loses
            single messages (a command or its answer), which stopped hovers at setup."""
            end, last = time.time() + timeout, 0.0
            while held() and not cond() and time.time() < end:
                if time.time() - last >= RESEND_S:
                    send()
                    last = time.time()
                self._override(2000)
                time.sleep(period)
            return held()

        try:
            # HOP_CH high first: hop_guard.lua latches on with it, and the laptop's checks need it
            for _ in range(3):
                self._override(2000)
                time.sleep(0.02)
            # 1. Navigation from the camera and the IMU only (source set 2: position, height, heading)
            t_switch = time.time()
            self.status = {"state": "camera source", "height": self.height, "reason": None}

            def ack():
                a = s.get("acks", {}).get(SOURCE_SET_CMD)
                return a if a and a[1] >= t_switch else None
            if not keep(lambda: ack() is not None, lambda: L.command(SOURCE_SET_CMD, 2), SOURCE_ACK_S):
                return
            a = ack()
            if a is None:
                return self.kill("the FC did not answer the switch to camera navigation")
            if a[0] != MAV.MAV_RESULT_ACCEPTED:
                return self.kill(f"the FC refused the switch to camera navigation (result {a[0]})")
            # 2. An EKF origin (indoors there is no GPS to set one): only a map label for the camera
            # position, but GUIDED needs it to turn the takeoff height into a target. Ask the FC
            # itself: the laptop's home can be from before an FC reboot, and then the takeoff fails
            t_org = time.time()
            has_origin = lambda: (s.get("origin_t") or 0) >= t_org
            if not keep(has_origin, lambda: L.command(MAV.MAV_CMD_REQUEST_MESSAGE, 49), ORIGIN_ASK_S):   # GPS_GLOBAL_ORIGIN
                return
            if not has_origin():
                lat, lon = s.get("lat_fc") or s.get("lat"), s.get("lon_fc") or s.get("lon")
                if not lat or not lon:
                    return self.kill("the FC has no EKF origin and there is no last known position to give it one")
                L.note(f"Laptop: EKF origin set at {lat:.6f}, {lon:.6f} (a label only, no GPS home indoors)", 4)
                t_org = time.time()

                def set_origin():
                    L.send(L.m.mav.set_gps_global_origin_send, L.sysid, int(lat * 1e7), int(lon * 1e7),
                           int((s.get("alt_msl") or 0.0) * 1000), int(time.time() * 1e6))
                    L.command(MAV.MAV_CMD_REQUEST_MESSAGE, 49)
                if not keep(has_origin, set_origin, 4.0):
                    return
                if not has_origin():
                    return self.kill("the FC did not take the EKF origin")
            # 3. Zero on the box: the box is the origin. The Pi sends its next camera pose with a
            # new reset counter, so the EKF jumps to it instead of walking over from where it was
            t_zero = time.time()
            if not keep(lambda: (s.get("vision_zero") or (0, 0))[1] >= t_zero,
                        lambda: L.send(L.m.mav.tunnel_send, 1, 191, ZERO_PAYLOAD_TYPE, 0, [0] * 128), ZERO_ACK_S):
                return
            if (s.get("vision_zero") or (0, 0))[1] < t_zero:
                return self.kill("the Pi did not answer the zero on the box (camera server down?)")
            # 4. The start point: wait until the FC position agrees with the tags (NED x, y = lid x,
            # -y) and it is not moving, held for SETTLE_HOLD_S, before arming. The FC height may sit a
            # constant amount off the tag height (an EKF height datum, e.g. after an arming without a
            # home): it must only hold steady; the hover height is taken relative to it
            agree_t, off0 = [None], [None]
            held_pos = []          # FC positions (x, y, z, t) while it agrees and is still
            held_tag = []          # tag positions (NED x, y, rx t) over the same window: the start x, y

            def settled():
                loc, p = s.get("local"), self.pose()
                ok = (loc and loc[3] > t_zero + 0.3 and p and p[1] and p[2] is not None
                      and math.hypot(loc[0] - p[4], loc[1] + p[5]) < SETTLE_M
                      and math.sqrt(loc[4] ** 2 + loc[5] ** 2 + loc[6] ** 2) < SETTLE_V)
                if ok:
                    off = loc[2] + p[2]                         # FC z minus (-tag height)
                    off0[0] = off if agree_t[0] is None else off0[0]
                    ok = abs(off - off0[0]) < SETTLE_M
                if not ok:
                    agree_t[0] = None
                    held_pos.clear()
                    held_tag.clear()
                    return False
                if not held_pos or held_pos[-1][3] != loc[3]:
                    held_pos.append(tuple(loc[:4]))
                if not held_tag or held_tag[-1][2] != p[0]:
                    held_tag.append((p[4], -p[5], p[0]))
                while held_pos[-1][3] - held_pos[0][3] > SETTLE_HOLD_S:   # keep the last SETTLE_HOLD_S only
                    held_pos.pop(0)
                while held_tag[-1][2] - held_tag[0][2] > SETTLE_HOLD_S:
                    held_tag.pop(0)
                agree_t[0] = agree_t[0] or time.time()
                return (time.time() - agree_t[0] >= SETTLE_HOLD_S
                        and held_pos[-1][3] - held_pos[0][3] >= 0.75 * SETTLE_HOLD_S
                        and spread() < SETTLE_SPREAD_M)

            def spread():
                if not held_pos:
                    return float("nan")
                return max(max(q[i] for q in held_pos) - min(q[i] for q in held_pos) for i in (0, 1))
            if not wait(settled, SETTLE_S):
                return
            if not settled():
                loc, p = s.get("local"), self.pose()
                if not loc or loc[3] <= t_zero + 0.3:
                    return self.kill("no FC position from the camera (LOCAL_POSITION_NED)")
                if not p or not p[1] or p[2] is None:
                    return self.kill("the FC did not settle on the camera (box tags out of view)")
                return self.kill(f"the FC did not settle on the camera in {SETTLE_S:g} s: FC "
                                 f"{loc[0] * 100:.0f}, {loc[1] * 100:.0f} cm moving "
                                 f"{math.sqrt(loc[4] ** 2 + loc[5] ** 2 + loc[6] ** 2) * 100:.0f} cm/s, height "
                                 f"offset not steady or still walking ({spread() * 1000:.0f} mm in "
                                 f"{SETTLE_HOLD_S:g} s); tags {p[4] * 100:.0f}, {-p[5] * 100:.0f} cm")
            # x, y: the mean TAG position over the last still second; z: the mean FC height. One FC
            # sample carries 1-2 mm of camera noise, and the EKF can sit still a few mm off the tags
            # while it converges after the zero (6 mm in the e2e sim); the hover holds the start the
            # whole time while the EKF walks onto the tags (sim, 2026-11-03)
            start = ([sum(q[i] for q in held_pos) / len(held_pos) for i in range(3)] if held_pos
                     else list(s["local"][:3]))
            if len(held_tag) >= 2:
                start[0] = sum(q[0] for q in held_tag) / len(held_tag)
                start[1] = sum(q[1] for q in held_tag) / len(held_tag)
            # Home here, before arming: ArduCopter resets its height datum when it arms without a
            # home (indoors there is no GPS to set one), which moves the FC height under the hover
            t_home = time.time()
            home_ack = lambda: (s.get("acks", {}).get(MAV.MAV_CMD_DO_SET_HOME) or (None, 0))
            has_home = lambda: ((s.get("home_t") or 0) >= t_home
                                or (home_ack()[1] >= t_home and home_ack()[0] == MAV.MAV_RESULT_ACCEPTED))

            def set_home():
                L.command(MAV.MAV_CMD_DO_SET_HOME, 1)             # 1 = at the current position
                L.command(MAV.MAV_CMD_REQUEST_MESSAGE, 242)       # HOME_POSITION
            if not keep(has_home, set_home, 4.0):
                return
            if not has_home():
                return self.kill("the FC did not set its home (needed before arming without GPS)")
            yaw0 = math.radians(s["yaw"])                   # start heading (EKF: the box camera)
            cam0 = self.pose()
            # 5. GUIDED (needs a position: the camera), arm, take off straight up
            if not keep(lambda: s["mode"] == "GUIDED", lambda: L.set_mode("GUIDED"), 3.0):
                return
            if s["mode"] != "GUIDED":
                return self.kill("the drone did not enter GUIDED (no position from the camera?)")
            if not keep(lambda: s["armed"], lambda: L.command(MAV.MAV_CMD_COMPONENT_ARM_DISARM, 1), 3.0):
                return
            if not s["armed"]:
                return self.kill("drone refused to arm (see its PreArm message)")
            t_to = time.time()
            if not wait(lambda: False, 0.4):                   # a datum reset at arming shows within this
                return
            loc, p = s.get("local"), self.pose()
            if loc and p and p[2] is not None and abs((loc[2] + p[2]) - off0[0]) > SETTLE_M:
                return self.kill(f"the FC height moved {abs((loc[2] + p[2]) - off0[0]) * 100:.0f} cm when it armed")
            # The takeoff itself is flown by lua/hop_takeoff.lua on the FC (armed in GUIDED with the
            # button channel high): it holds the start point on the skids, lifts off and hands
            # over to position control (HOPT 4). Only then does the laptop send position targets
            t_to = time.time()
            hopt = lambda: (s.get("hopt") or (0, 0.0))
            self.status = {"state": "takeoff", "height": self.height, "reason": None}
            locked, last_lock = False, 0.0
            t_level = t_down = t_ground = None                 # test run: at the height, descending, on the ground
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
                    if t_down:                                 # the FC's own land detector in the test descent
                        self.status = {"state": "done", "height": self.height, "reason": TEST_DONE}
                        return L.note(f"Laptop: {TEST_DONE} (the FC disarmed on landing)", 5)
                    self.status = {"state": "killed", "height": self.height, "reason": "disarmed by the drone"}
                    return L.note("Laptop: hover ended, the drone disarmed (hop_guard.lua or the FC)", 3)
                if s["mode"] != "GUIDED":
                    return self.kill(f"mode changed to {s['mode']}")
                est = cam_h - self.h0                          # tag height above where it sat
                code, code_t = hopt()
                if code == 9 and code_t >= t_to:
                    return self.kill("the FC takeoff script stopped the motors (see its HTO message)")
                if not locked and now - t_to > TAKEOFF_S:
                    return self.kill(f"no handover from the FC takeoff script in {TAKEOFF_S:g} s")
                if est > self.height + CAM_CEILING_M:
                    return self.kill(f"tag height {est * 100:.0f} cm, over {(self.height + CAM_CEILING_M) * 100:.0f} cm")
                drift = math.hypot(p[4] - cam0[4], p[5] - cam0[5]) if p and p[1] and cam0 and cam0[4] is not None else None
                if drift is not None and drift > DRIFT_MAX_M:
                    return self.kill(f"drifted {drift * 100:.0f} cm from the start (tags)")
                if s["alt"] is not None and fc0 is not None:
                    gap = abs((s["alt"] - fc0) - est)
                    if gap > HEIGHT_AGREE_M:
                        disagree_t = disagree_t or now
                        if now - disagree_t > HEIGHT_AGREE_S:
                            return self.kill(f"FC height does not follow the camera ({gap * 100:.0f} cm apart)")
                    else:
                        disagree_t = None
                # 6. handed over (HOPT 4): lock over the start point and heading, and keep it locked; the
                # height target climbs from where it is at CLIMB_MPS. No target before: it would take
                # GUIDED out of the script's angle control on the skids
                if not locked and code == 4 and code_t >= t_to:
                    locked, t_lock, h_lock = True, now, max(0.0, est)
                    L.note(f"Laptop: hover locked over the start point at {h_lock * 100:.0f} cm", 6)
                if locked:
                    h_tgt = min(self.height, h_lock + CLIMB_MPS * (now - t_lock))
                    climbing = h_tgt < self.height
                    # test run: hold at the height for test_s, then descend at CLIMB_MPS to LAND_BELOW_M under
                    # the start (pressed onto its legs) and stop once the tags say it is down
                    if self.test_s is not None:
                        if not climbing and t_level is None:
                            t_level = now
                        if t_level is not None and now - t_level >= self.test_s:
                            t_down = t_down or now
                            h_tgt = max(-LAND_BELOW_M, self.height - CLIMB_MPS * (now - t_down))
                            climbing = True                    # moving target: resend at 5 Hz
                            if est <= LAND_DONE_M:
                                t_ground = t_ground or now
                                if now - t_ground >= LAND_HOLD_S:
                                    return self.kill(TEST_DONE)
                            else:
                                t_ground = None
                            if now - t_down > (self.height + LAND_BELOW_M) / CLIMB_MPS + LAND_EXTRA_S:
                                return self.kill(TEST_DONE)
                    if now - last_lock >= (0.2 if climbing else 1.0):   # resent: a lost message cannot unlock it
                        self._hold_target(start, yaw0, h_tgt)
                        last_lock = now
                self.status = {"state": ("landing" if t_down else "locked") if locked else "climbing",
                               "height": self.height, "reason": None,
                               "test_left": None if self.test_s is None or t_level is None
                               else round(max(0.0, self.test_s - (now - t_level)), 1),
                               "height_now": round(est, 3), "drift_m": None if drift is None else round(drift, 3),
                               "pose": p[3], "pose_age": round(now - cam_t, 2)}
                self._override(2000)
                time.sleep(period)
        except Exception as exc:   # never leave the motors running on an error
            if gen == self.gen:
                self.kill(f"error: {exc}")
