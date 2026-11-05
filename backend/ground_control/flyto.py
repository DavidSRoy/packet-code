"""Fly to a point: take off (if on the ground), fly to lat/lon at a height, then land or hover.

How it works
------------
1. Checks (refused with a reason, nothing is sent): drone link, SD on run, GPS
   (3D fix, 8+ sats), battery, the target height (FLYTO_MIN_ALT..FLYTO_MAX_ALT),
   the distance (FLYTO_MAX_M), the geofence circle, and the legal ceiling and
   NO-FLY areas along the straight line (ceiling.check_route, the same check as
   trips). A backend command also needs the SA switch on.
2. On the ground: GUIDED, arm, take off to the target height (the same steps as
   the page's Auto takeoff). In the air: GUIDED, from where it is.
3. One position target (SET_POSITION_TARGET_GLOBAL_INT, height above home) and
   the speed (DO_CHANGE_SPEED). ArduCopter flies there in a straight line and
   holds there by itself, so nothing has to be resent.
4. Arrived (within ARRIVE_H_M / ARRIVE_V_M): LAND at that spot, or hover in GUIDED.

It stops (state "stopped", the drone keeps what it does) when anything else takes
the drone: a page key, Hold, Land, RTL, Kill, a mode change by the SA guard, a
failsafe or the FC. A trip that takes far longer than planned holds in place.
"""
import math
import threading
import time

from pymavlink import mavutil

import ceiling

MAV = mavutil.mavlink

FLYTO_MIN_ALT = 2.0        # m above home
FLYTO_MAX_ALT = 60.0       # m above home (the legal ceiling check can lower it)
FLYTO_MAX_M = 1000.0       # m from the drone
FENCE_MARGIN_M = 5.0       # stay this far inside the geofence circle
MIN_BATT_PCT = 30
SPEED_MIN, SPEED_MAX = 0.5, 5.0   # m/s
ARRIVE_H_M = 1.5           # horizontal arrival radius
ARRIVE_V_M = 0.7
CLIMB_TIMEOUT_S = 40.0
POS_ONLY_MASK = 0b0000_1101_1111_1000   # use lat, lon, alt; ignore velocity, acceleration, yaw, yaw rate
ACTIVE = ("starting", "taking_off", "enroute", "landing")


def dist_m(a_lat, a_lon, b_lat, b_lon):
    n = (b_lat - a_lat) * 111_320.0
    e = (b_lon - a_lon) * 111_320.0 * math.cos(math.radians(a_lat))
    return math.hypot(n, e)


class FlyTo:
    def __init__(self, link, pilot, air=None, ceil=None):
        self.link, self.pilot, self.air, self.ceil = link, pilot, air, ceil
        self.lock = threading.Lock()
        self.thread = None
        self.cancel_reason = None
        self.status = {"state": "idle", "target": None, "land": None, "speed": None, "dist_m": None,
                       "eta_s": None, "reason": None, "source": None, "cmd_id": None,
                       "started": None, "ended": None}

    # ---- state -------------------------------------------------------------
    def active(self):
        return self.status["state"] in ACTIVE

    def _set(self, **kw):
        self.status = dict(self.status, **kw)

    def cancel(self, reason):
        """Something else took the drone (page key, Hold, Land, RTL, Kill, backend)."""
        if self.active():
            self.cancel_reason = reason

    # ---- checks ------------------------------------------------------------
    def check(self, lat, lon, alt, speed, backend):
        """Reason to refuse, or None."""
        s = self.link.state
        if not s["link"]:
            return "no link to the drone"
        if self.active() or self.pilot.busy:
            return "a fly-to or takeoff is already running"
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            return "bad target position"
        if not FLYTO_MIN_ALT <= alt <= FLYTO_MAX_ALT:
            return f"height must be {FLYTO_MIN_ALT:g}..{FLYTO_MAX_ALT:g} m above home"
        if not SPEED_MIN <= speed <= SPEED_MAX:
            return f"speed must be {SPEED_MIN:g}..{SPEED_MAX:g} m/s"
        if backend and not s.get("sa_on"):
            return "SA switch is off: backend control not allowed"
        if s["sd_stop"]:
            return "SD kill switch is on stop"
        if s["gps_fix"] < 3 or s["sats"] < 8:
            return f"GPS fix {s['gps_fix']} with {s['sats']} sats (need 3D, 8+)"
        if s["lat"] is None:
            return "no drone position"
        if s["batt_pct"] is not None and s["batt_pct"] < MIN_BATT_PCT:
            return f"battery {s['batt_pct']}% (need {MIN_BATT_PCT}%+)"
        if s["armed"] and s["mode"] not in ("GUIDED", "LOITER", "BRAKE", "ALT_HOLD", "AUTO"):
            return f"drone is in {s['mode']}: fly-to starts on the ground, or in the air from GUIDED/LOITER"
        if not s["armed"] and self.ceil and self.ceil.takeoff_block():
            return self.ceil.takeoff_block()
        d = dist_m(s["lat"], s["lon"], lat, lon)
        if d > FLYTO_MAX_M:
            return f"target is {d:.0f} m away (max {FLYTO_MAX_M:.0f} m)"
        fc = (self.ceil.state.get("fc") if self.ceil else None) or {}
        circle = ((fc.get("fence_type") or 0) & 2) != 0
        if s.get("fence_on") and circle and s.get("fence_r") and s.get("home_lat") is not None:
            r = dist_m(s["home_lat"], s["home_lon"], lat, lon)
            if r > s["fence_r"] - FENCE_MARGIN_M:
                return f"target is {r:.0f} m from home, outside the {s['fence_r']:.0f} m geofence (less {FENCE_MARGIN_M:.0f} m)"
        if self.air is not None:
            # Straight line at the target height, heights above home (the route check measures them from 'pad')
            start = {"lat": s["home_lat"], "lon": s["home_lon"]} if s.get("home_lat") is not None and s["armed"] \
                else {"lat": s["lat"], "lon": s["lon"]}
            line = {"takeoff_alt": alt, "waypoints": [{"lat": s["lat"], "lon": s["lon"], "alt": alt}],
                    "final": {"lat": lat, "lon": lon, "alt": alt}}
            why = ceiling.check_route(self.air, line, start)
            if why:
                return why
        return None

    # ---- start -------------------------------------------------------------
    def start(self, lat, lon, alt, land=True, speed=None, source="Laptop", cmd_id=None):
        """Returns (accepted, reason). The flight runs in its own thread."""
        try:
            lat, lon, alt = float(lat), float(lon), float(alt)
            speed = float(speed) if speed is not None else self.pilot.speeds["h"]
        except (TypeError, ValueError):
            return False, "lat, lon, alt and speed must be numbers"
        with self.lock:
            why = self.check(lat, lon, alt, speed, backend=source != "Laptop")
            if why:
                self.link.note(f"{source}: fly-to refused: {why}", 4)
                return False, why
            s = self.link.state
            d = dist_m(s["lat"], s["lon"], lat, lon)
            self.cancel_reason = None
            self._set(state="starting", target={"lat": lat, "lon": lon, "alt": alt}, land=bool(land), speed=speed,
                      dist_m=round(d, 1), eta_s=round(d / speed), reason=None, source=source, cmd_id=cmd_id,
                      started=time.time(), ended=None)
            self.link.note(f"{source}: fly to {lat:.6f}, {lon:.6f} at {alt:g} m, {speed:g} m/s, "
                           + ("then land" if land else "then hover") + f" ({d:.0f} m)")
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            return True, None

    # ---- the flight --------------------------------------------------------
    def _wait(self, cond, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if self.cancel_reason or cond():
                return True
            time.sleep(0.1)
        return False

    def _end(self, state, reason=None, sev=4):
        self._set(state=state, reason=reason, ended=time.time())
        self.link.note(f"Laptop: fly-to {state}" + (f": {reason}" if reason else ""), sev)

    def _send_target(self):
        L, t = self.link, self.status["target"]
        L.command(MAV.MAV_CMD_DO_CHANGE_SPEED, 1, self.status["speed"], -1)
        L.send(L.m.mav.set_position_target_global_int_send, 0, L.sysid, L.compid,
               MAV.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, POS_ONLY_MASK,
               int(round(t["lat"] * 1e7)), int(round(t["lon"] * 1e7)), t["alt"],
               0, 0, 0, 0, 0, 0, 0, 0)

    def _run(self):
        L, s, p = self.link, self.link.state, self.pilot
        t = self.status["target"]
        try:
            # 1. In the air: take over in GUIDED. On the ground: GUIDED, arm, take off.
            if s["armed"]:
                L.set_mode("GUIDED")
                if not self._wait(lambda: s["mode"] == "GUIDED", 4) or s["mode"] != "GUIDED":
                    return self._end("failed", self.cancel_reason or "drone did not enter GUIDED", 3)
            else:
                self._set(state="taking_off")
                p.busy = True
                try:
                    L.set_mode("GUIDED")
                    if not self._wait(lambda: s["mode"] == "GUIDED", 4) or s["mode"] != "GUIDED":
                        return self._end("failed", self.cancel_reason or "drone did not enter GUIDED", 3)
                    L.command(MAV.MAV_CMD_COMPONENT_ARM_DISARM, 1)
                    if not self._wait(lambda: s["armed"], 5) or not s["armed"]:
                        return self._end("failed", self.cancel_reason or "drone refused to arm (see its PreArm message)", 3)
                    p.takeoff_target, p.takeoff_until = t["alt"], time.time() + CLIMB_TIMEOUT_S
                    L.command(MAV.MAV_CMD_NAV_TAKEOFF, p7=t["alt"])
                finally:
                    p.busy = False
                ok = self._wait(lambda: s["alt"] is not None and s["alt"] >= 0.9 * t["alt"]
                                or not s["armed"] or s["mode"] != "GUIDED", CLIMB_TIMEOUT_S)
                if self.cancel_reason:
                    return self._end("stopped", self.cancel_reason)
                if not s["armed"] or s["mode"] != "GUIDED":
                    return self._end("stopped", f"mode changed to {s['mode']}" if s["armed"] else "disarmed")
                if not ok:
                    p.takeoff_target = None
                    L.note("Laptop: fly-to climb is slow; going on from here", 4)
                p.takeoff_target = None
            # 2. Fly there.
            self._set(state="enroute")
            self._send_target()
            d0 = dist_m(s["lat"], s["lon"], t["lat"], t["lon"])
            deadline = time.time() + d0 / self.status["speed"] * 2.0 + 30.0
            last_send = time.time()
            while True:
                time.sleep(0.2)
                if self.cancel_reason:
                    return self._end("stopped", self.cancel_reason)
                if not s["armed"]:
                    return self._end("failed", "disarmed in the air", 3)
                if s["mode"] != "GUIDED":
                    return self._end("stopped", f"mode changed to {s['mode']} (SA guard, failsafe or the FC)")
                d = dist_m(s["lat"], s["lon"], t["lat"], t["lon"])
                dz = abs((s["alt"] or 0.0) - t["alt"])
                gs = math.hypot(s["vn"], s["ve"])
                self._set(dist_m=round(d, 1), eta_s=round(d / max(gs, 0.3)) if d > ARRIVE_H_M else 0)
                if d <= ARRIVE_H_M and dz <= ARRIVE_V_M:
                    break
                if time.time() - last_send > 5.0:   # the link may have lost the first one
                    self._send_target()
                    last_send = time.time()
                if time.time() > deadline:
                    L.velocity(0, 0, 0, 0)          # hold where it is
                    return self._end("failed", f"took too long, holding {d:.0f} m short", 3)
            # 3. Land there, or hover.
            if not self.status["land"]:
                return self._end("arrived", "hovering at the point (GUIDED)", 6)
            self._set(state="landing")
            L.set_mode("LAND")
            self._wait(lambda: s["mode"] == "LAND", 4)
            while s["armed"]:
                time.sleep(0.2)
                if self.cancel_reason:
                    return self._end("stopped", self.cancel_reason)
                if s["mode"] != "LAND":
                    return self._end("stopped", f"mode changed to {s['mode']} while landing")
            self._end("arrived", "landed at the point", 6)
        except Exception as exc:   # never die silently
            self._end("failed", f"error: {exc}", 3)
