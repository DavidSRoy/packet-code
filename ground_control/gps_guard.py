"""GPS quality and a jump filter for the ground-control display.

The FC position (GLOBAL_POSITION_INT) follows the GPS. With few satellites
(indoors, near buildings) the GPS can jump tens or hundreds of metres in one
fix. This module:

- rates the GPS: "good", "poor" or "bad", with the reasons;
- filters the shown position:
  * disarmed and the gyros show no motion: the drone cannot move, so it
    glides (0.2 m/s at most) toward the median of the recent fixes; a GPS
    excursion of tens of seconds does not move it;
  * disarmed and moving (carried): follows at walking speed at most; with
    a bad GPS it never jumps to a new place, as a wrong place can be stable;
  * armed: follows the FC, but holds on a single impossible jump (larger
    than the FC speed allows) until several fixes agree on the new place.
  When the GPS is "good", it follows the FC position directly.

Indoor test (2026-10-25_205643.tlog, 27 min disarmed, 7 sats): the raw FC
position wandered up to 521 m and was more than 40 m away for 110 s; the
shown position stays still.

Display only. The FC does its own checks (pre-arm, EKF glitch gates) and
flies on its own estimate; nothing here changes what the FC does.
"""
import math
import time

# Display thresholds (the FC uses its own limits for arming)
HACC_POOR, HACC_BAD = 2.5, 5.0        # m, GPS horizontal accuracy (h_acc)
HDOP_POOR, HDOP_BAD = 1.4, 3.0        # 1.4 = GPS_HDOP_GOOD default on the FC
SATS_POOR, SATS_BAD = 10, 6

STILL_RATE = 0.08      # rad/s; the gyro noise at rest is under 0.05 (indoor log)
STILL_S = 3.0          # no rotation above STILL_RATE for this long = not moving
WALK_SPEED = 4.0       # m/s, top speed while disarmed (carried)
MEDIAN_S = 120.0       # window for the still position
STILL_DRIFT = 0.2      # m/s, top speed of the shown position while still
FILTERED_M = 8.0       # FC position this far from the shown one = "jump filtered"
SPEED_MARGIN = 5.0     # m/s added to the FC speed for the jump gate
GATE_SLACK = 3.0       # m
REANCHOR_N = 6         # agreeing fixes in a row (about 1.2 s at 5 Hz) to take a new position
REANCHOR_S = 4.0       # or held this long with agreeing fixes


def dist_m(lat1, lon1, lat2, lon2):
    dn = (lat2 - lat1) * 111320.0
    de = (lon2 - lon1) * 111320.0 * math.cos(math.radians(lat1))
    return math.hypot(dn, de)


class GpsGuard:
    def __init__(self):
        self.fix, self.sats, self.hdop, self.hacc = 0, 0, None, None
        self.ekf_flags = None
        self.glitch = False             # FC said "GPS Glitch", until "Glitch cleared"
        self.pos = None                 # (lat, lon, t) shown
        self.cand = None                # (lat, lon, t) newest rejected fix
        self.cand_n = 0
        self.held_since = None
        self.rejected = 0               # total fixes not shown
        self.last_motion = 0.0          # last time the gyros showed rotation
        self.still_buf = []             # (t, lat, lon) while still and disarmed
        self.filtered = False

    # ---- inputs ----
    def on_gps_raw(self, msg):
        self.fix, self.sats = msg.fix_type, msg.satellites_visible
        self.hdop = msg.eph / 100 if msg.eph != 65535 else None
        h = getattr(msg, "h_acc", 0)
        self.hacc = h / 1000 if h else None

    def on_ekf(self, msg):
        self.ekf_flags = msg.flags

    def on_attitude(self, msg, now=None):
        if max(abs(msg.rollspeed), abs(msg.pitchspeed), abs(msg.yawspeed)) > STILL_RATE:
            self.last_motion = time.time() if now is None else now

    def on_text(self, text):
        if "GPS Glitch" in text:
            self.glitch = True
        elif "Glitch cleared" in text:
            self.glitch = False

    def on_position(self, lat, lon, speed, armed, now=None):
        """New FC position. Returns (lat, lon) to show; None before the first fix."""
        now = time.time() if now is None else now
        if lat == 0 and lon == 0:
            return self.pos[:2] if self.pos else None
        if self.pos is None:
            self.pos = (lat, lon, now)
            return lat, lon
        good = self.quality(raw=True)[0] == "good"
        still = not armed and now - self.last_motion > STILL_S
        if good or not still:
            self.still_buf = []
        if good:
            return self._take(lat, lon, now)
        if still:
            # cannot move: show the median of the recent fixes
            self.still_buf.append((now, lat, lon))
            while self.still_buf and now - self.still_buf[0][0] > MEDIAN_S:
                self.still_buf.pop(0)
            la = sorted(p[1] for p in self.still_buf)[len(self.still_buf) // 2]
            lo = sorted(p[2] for p in self.still_buf)[len(self.still_buf) // 2]
            # glide toward the median, slowly: the drone does not move
            d = dist_m(self.pos[0], self.pos[1], la, lo)
            step = STILL_DRIFT * max(0.05, now - self.pos[2])
            k = 1.0 if d <= step else step / d
            la, lo = self.pos[0] + (la - self.pos[0]) * k, self.pos[1] + (lo - self.pos[1]) * k
            self.pos, self.cand, self.cand_n = (la, lo, now), None, 0
            self._mark(lat, lon, now)
            return la, lo
        v = WALK_SPEED if not armed else abs(speed) + SPEED_MARGIN
        dt = max(0.05, now - self.pos[2])
        if dist_m(self.pos[0], self.pos[1], lat, lon) <= v * dt + GATE_SLACK:
            return self._take(lat, lon, now)
        # impossible jump: hold the shown position, watch whether the new place is stable
        if self.cand is not None:
            cdt = max(0.05, now - self.cand[2])
            ok = dist_m(self.cand[0], self.cand[1], lat, lon) <= v * cdt + GATE_SLACK
            self.cand_n = self.cand_n + 1 if ok else 0
        self.cand = (lat, lon, now)
        # Take the new place only when the fixes agree on it AND they can be trusted:
        # armed (the FC flies on this position, so the pilot must see it) or GPS not bad.
        # With a bad GPS on the ground, a wrong position can be stable too.
        trust = armed or self.quality(raw=True)[0] != "bad"
        if trust and (self.cand_n >= REANCHOR_N or (self.cand_n >= 2 and self.held_since and now - self.held_since >= REANCHOR_S)):
            return self._take(lat, lon, now)
        self._mark(lat, lon, now)
        return self.pos[0], self.pos[1]

    def _take(self, lat, lon, now):
        self.pos, self.cand, self.cand_n, self.held_since, self.filtered = (lat, lon, now), None, 0, None, False
        return lat, lon

    def _mark(self, lat, lon, now):
        """Note whether the FC position is far from the shown one."""
        far = dist_m(self.pos[0], self.pos[1], lat, lon) > FILTERED_M
        if far:
            self.rejected += 1
            if self.held_since is None:
                self.held_since = now
        else:
            self.held_since = None
        self.filtered = far

    # ---- output ----
    def quality(self, raw=False):
        """("good" | "poor" | "bad", [reasons]). raw=True leaves out the filter state."""
        bad, poor = [], []
        if self.fix < 3:
            bad.append("no 3D fix")
        if self.sats < SATS_BAD:
            bad.append(f"{self.sats} sats")
        elif self.sats < SATS_POOR:
            poor.append(f"{self.sats} sats")
        if self.hacc is not None:
            (bad if self.hacc > HACC_BAD else poor if self.hacc > HACC_POOR else []).append(f"±{self.hacc:.0f} m")
        if self.hdop is not None:
            (bad if self.hdop > HDOP_BAD else poor if self.hdop > HDOP_POOR else []).append(f"HDOP {self.hdop:.1f}")
        if self.glitch:
            bad.append("FC: GPS glitch")
        f = self.ekf_flags
        if f is not None:
            from pymavlink import mavutil
            if f & mavutil.mavlink.EKF_GPS_GLITCHING:
                if "FC: GPS glitch" not in bad:
                    bad.append("FC: GPS glitch")
            if not f & mavutil.mavlink.EKF_POS_HORIZ_ABS:
                bad.append("FC: no position")
        if self.filtered and not raw:
            poor.append("jump filtered")
        if self.hacc is None and self.fix >= 3:
            poor.append("accuracy unknown")       # no h_acc from this GPS or link: never "good"
        if bad:
            return "bad", bad + poor
        return ("poor", poor) if poor else ("good", [])

    def state(self):
        q, why = self.quality()
        return {"gps_q": q, "gps_why": why, "gps_hdop": self.hdop, "gps_hacc": self.hacc,
                "pos_filtered": self.filtered, "pos_rejected": self.rejected}
