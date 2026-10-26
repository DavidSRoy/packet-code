"""Backend autonomy: landing pads, taught routes, and pad-to-pad missions.

How it fits together
--------------------
1. Teach: the pilot flies a route by hand (pad A -> pad B) while the laptop
   records it (RouteRecorder). The pad positions come from GPS while the
   drone sits on each pad.
2. Build: build_route() turns the recording into an ArduPilot mission:
   takeoff, the flown path (simplified), a point 3 m above pad B, LAND.
   It also builds the reverse route. New routes are saved with
   "approved": false. A person checks a route on the map, then approves it.
3. Fly: MissionRunner.goto("uplace") checks the SA switch and the preflight
   rules, uploads the approved route, arms, and starts AUTO. The pilot takes
   over at any time with the mode switch (SC) or by turning SA off.

Altitudes in routes are relative to the pad where the route starts, because
ArduPilot sets home at that pad when it arms. Files live in packethw/routes/.
"""
import json
import math
import threading
import time
from pathlib import Path

from pymavlink import mavutil

ROUTES = Path(__file__).resolve().parent.parent / "routes"
MAV = mavutil.mavlink

# Preflight rules for a backend flight
MIN_BATT_PCT = 60          # % charge to start a trip
MIN_CELL_V = 3.85          # V per cell at rest, also needed (the % is wrong if the pack was not full at power-up)
MIN_SATS = 12
PAD_MATCH_M = 8.0          # the drone is "on" a pad when it is this close
FINAL_ABOVE_PAD_M = 3.0    # last waypoint height above the pad, then LAND descends slowly
MAX_ROUTE_ALT_M = 110.0    # stay below 120 m (400 ft) with a margin
SIMPLIFY_M = 2.0           # path simplification tolerance
PAD_COLUMN_M = 5.0         # recorded points this close (horizontally) to a pad are the climb/approach, not the path
CRUISE_SPEED_MAX = 5.0     # m/s


def _now():
    return time.time()


def local_m(lat0, lon0, lat, lon):
    """North, east metres from (lat0, lon0). Good to well under 1 m over a few km."""
    k = 111_320.0
    return (lat - lat0) * k, (lon - lon0) * k * math.cos(math.radians(lat0))


def dist_m(a_lat, a_lon, b_lat, b_lon):
    n, e = local_m(a_lat, a_lon, b_lat, b_lon)
    return math.hypot(n, e)


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def simplify(points, tol):
    """Ramer-Douglas-Peucker in 3D. points: list of (n, e, u, payload)."""
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    L2 = sum(c * c for c in ab) or 1e-9
    best, idx = -1.0, 0
    for i in range(1, len(points) - 1):
        p = points[i]
        ap = (p[0] - a[0], p[1] - a[1], p[2] - a[2])
        t = max(0.0, min(1.0, sum(x * y for x, y in zip(ap, ab)) / L2))
        d = math.dist(p[:3], (a[0] + t * ab[0], a[1] + t * ab[1], a[2] + t * ab[2]))
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [a, b]
    return simplify(points[: idx + 1], tol)[:-1] + simplify(points[idx:], tol)


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
class Store:
    """pads.json + one JSON file per route, in packethw/routes/."""

    def __init__(self, root=ROUTES):
        self.root = Path(root)
        (self.root / "recordings").mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    @property
    def pads_path(self):
        return self.root / "pads.json"

    def pads(self):
        try:
            return json.loads(self.pads_path.read_text())["pads"]
        except FileNotFoundError:
            return {}

    def save_pad(self, pad_id, lat, lon, alt_msl, samples, source):
        with self.lock:
            pads = self.pads()
            old = pads.get(pad_id, {})
            pads[pad_id] = {"name": old.get("name", pad_id.upper()), "lat": round(lat, 7), "lon": round(lon, 7),
                            "alt_msl": None if alt_msl is None else round(alt_msl, 1),
                            "gps_samples": samples, "source": source,
                            "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}
            self.pads_path.write_text(json.dumps({"pads": pads}, indent=2) + "\n")

    def route_path(self, a, b):
        return self.root / f"{a}__{b}.json"

    def route(self, a, b):
        try:
            return json.loads(self.route_path(a, b).read_text())
        except FileNotFoundError:
            return None

    def routes(self):
        out = []
        for p in sorted(self.root.glob("*__*.json")):
            try:
                out.append(json.loads(p.read_text()))
            except (OSError, ValueError):
                continue
        return out

    def save_route(self, r):
        self.route_path(r["from"], r["to"]).write_text(json.dumps(r, indent=2) + "\n")

    def set_approved(self, a, b, ok):
        r = self.route(a, b)
        if not r:
            return False
        r["approved"] = bool(ok)
        r["approved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S") if ok else None
        self.save_route(r)
        return True


# --------------------------------------------------------------------------
# Teach: record a hand-flown route
# --------------------------------------------------------------------------
class RouteRecorder:
    """Records one hand-flown trip from pad A to pad B.

    Start it while the drone sits on pad A, disarmed. It keeps the GPS while
    the drone waits (pad A position), records the flight from arm to disarm,
    then keeps 5 s of GPS on pad B (pad B position) and saves everything."""

    PAD_SAMPLE_S = 10.0

    def __init__(self, link, store, on_done):
        self.link, self.store, self.on_done = link, store, on_done
        self.active = None

    def status(self):
        a = self.active
        if not a:
            return None
        return {"from": a["from"], "to": a["to"], "phase": a["phase"], "samples": len(a["flight"]),
                "since": a["started"]}

    def start(self, a, b):
        s = self.link.state
        if self.active:
            return "a recording is already running"
        if a == b or not a or not b:
            return "pick two different pads"
        if s["armed"]:
            return "start the recording on pad A before you arm"
        if s["gps_fix"] < 3:
            return "no 3D GPS fix"
        self.active = {"from": a, "to": b, "phase": "on pad A", "started": _now(),
                       "pad_a": [], "flight": [], "pad_b": [], "landed_at": None}
        self.link.note(f"Laptop: route recording {a} -> {b}. Arm on pad {a.upper()} and fly to {b.upper()}.")
        return None

    def cancel(self):
        if self.active:
            self.link.note("Laptop: route recording cancelled")
        self.active = None

    def on_position(self, s):
        """Called at each GLOBAL_POSITION_INT (5 Hz)."""
        a = self.active
        if not a or s["lat"] is None:
            return
        row = {"t": round(_now(), 2), "lat": s["lat"], "lon": s["lon"], "rel": s["alt"], "msl": s["alt_msl"],
               "mode": s["mode"], "armed": s["armed"]}
        if a["phase"] == "on pad A":
            if s["armed"]:
                a["phase"] = "flying"
                a["flight"].append(row)
            else:
                a["pad_a"].append(row)
                a["pad_a"] = [r for r in a["pad_a"] if row["t"] - r["t"] <= self.PAD_SAMPLE_S]
        elif a["phase"] == "flying":
            if s["armed"]:
                a["flight"].append(row)
            else:
                a["phase"] = "on pad B"
                a["landed_at"] = row["t"]
                a["pad_b"].append(row)
        elif a["phase"] == "on pad B":
            if s["armed"]:  # took off again before we finished: keep what we have
                self.finish()
                return
            a["pad_b"].append(row)
            if row["t"] - a["landed_at"] >= 5.0:
                self.finish()

    def finish(self):
        a, self.active = self.active, None
        if not a["pad_a"] or len(a["flight"]) < 10 or not a["pad_b"]:
            self.link.note("Laptop: route recording too short, not saved", 3)
            return
        stamp = time.strftime("%Y-%m-%d_%H%M%S")
        path = self.store.root / "recordings" / f"{stamp}_{a['from']}_to_{a['to']}.json"
        path.write_text(json.dumps(a))
        self.link.note(f"Laptop: route recorded ({len(a['flight'])} points) -> {path.name}")
        self.on_done(path)


def pad_fix(rows):
    """Mean position of the samples on a pad."""
    return (_mean([r["lat"] for r in rows]), _mean([r["lon"] for r in rows]),
            _mean([r["msl"] for r in rows if r["msl"] is not None]),
            _mean([r["rel"] for r in rows if r["rel"] is not None]))


def build_route(rec, frm, to, pad_a, pad_b, touch_rel, flight, note=""):
    """Mission from pad_a to pad_b along 'flight' (rows with lat, lon, rel to pad_a).

    touch_rel: height of pad_b relative to pad_a (m)."""
    air = [r for r in flight if r["rel"] is not None]
    lat0, lon0 = pad_a
    bn, be = local_m(lat0, lon0, *pad_b)
    pts = [(*local_m(lat0, lon0, r["lat"], r["lon"]), r["rel"], r) for r in air]

    def off_a(p):
        return math.hypot(p[0], p[1]) > PAD_COLUMN_M

    def off_b(p):
        return math.hypot(p[0] - bn, p[1] - be) > PAD_COLUMN_M

    # path: from leaving the column above pad A to entering the column above pad B
    start = next((i for i, p in enumerate(pts) if off_a(p)), 0)
    end = next((i for i in range(len(pts) - 1, -1, -1) if off_b(pts[i])), len(pts) - 1)
    path = [p for p in pts[start:end + 1] if off_a(p) and off_b(p)] if end > start else []
    # takeoff height: the height when the pilot left the column above pad A
    takeoff_alt = round(max(3.0, path[0][2] if path else 5.0), 1)
    keep = simplify(path, SIMPLIFY_M) if path else []
    wps = [{"lat": round(p[3]["lat"], 7), "lon": round(p[3]["lon"], 7), "alt": round(p[2], 1)} for p in keep]
    final = {"lat": round(pad_b[0], 7), "lon": round(pad_b[1], 7), "alt": round(touch_rel + FINAL_ABOVE_PAD_M, 1)}
    # cruise speed: median ground speed in the cruise part, capped
    speeds = []
    for i in range(start + 1, min(end + 1, len(pts))):
        dt = abs(air[i]["t"] - air[i - 1]["t"])  # abs: the reverse route has time running backwards
        if dt > 0:
            speeds.append(math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) / dt)
    speeds.sort()
    cruise = round(min(CRUISE_SPEED_MAX, max(1.0, speeds[len(speeds) // 2] if speeds else 2.0)), 1)
    length = 0.0
    chain = [(pad_a[0], pad_a[1])] + [(w["lat"], w["lon"]) for w in wps] + [(final["lat"], final["lon"])]
    for (a1, o1), (a2, o2) in zip(chain, chain[1:]):
        length += dist_m(a1, o1, a2, o2)
    max_alt = max([takeoff_alt, final["alt"]] + [w["alt"] for w in wps])
    return {
        "from": frm, "to": to, "approved": False, "approved_at": None,
        "takeoff_alt": takeoff_alt, "cruise_speed": cruise, "waypoints": wps, "final": final,
        "land": {"lat": final["lat"], "lon": final["lon"]}, "dest_rel_alt": round(touch_rel, 1),
        "length_m": round(length), "max_alt": round(max_alt, 1),
        "est_time_s": round(length / cruise + takeoff_alt / 1.5 + FINAL_ABOVE_PAD_M / 0.5 + 15),
        "source": rec, "note": note, "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def check_route(r):
    """List of problems that block approval."""
    out = []
    if r["max_alt"] > MAX_ROUTE_ALT_M:
        out.append(f"max height {r['max_alt']} m is above {MAX_ROUTE_ALT_M} m")
    if not r["waypoints"]:
        out.append("no waypoints between the pads")
    if r["length_m"] < 5:
        out.append("route is shorter than 5 m")
    for w in r["waypoints"]:
        if w["alt"] < 3.0 and w["alt"] < r["dest_rel_alt"] + 3.0:
            out.append(f"waypoint at {w['alt']} m is under 3 m")
            break
    return out


def routes_from_recording(path, store):
    """Pads + forward route + reverse route from one recording file."""
    rec = json.loads(Path(path).read_text())
    a, b = rec["from"], rec["to"]
    la, oa, ma, ra = pad_fix(rec["pad_a"])
    lb, ob, mb, rb = pad_fix(rec["pad_b"])
    store.save_pad(a, la, oa, ma, len(rec["pad_a"]), Path(path).name)
    store.save_pad(b, lb, ob, mb, len(rec["pad_b"]), Path(path).name)
    # heights relative to pad A: use the barometer (rel), which is good over a short flight
    touch = rb - (ra or 0.0) if rb is not None else 0.0
    flight = [dict(r, rel=r["rel"] - (ra or 0.0)) for r in rec["flight"]]
    fwd = build_route(Path(path).name, a, b, (la, oa), (lb, ob), touch, flight)
    # reverse: same path backwards, heights relative to pad B
    back = [dict(r, rel=r["rel"] - touch) for r in reversed(flight)]
    rev = build_route(Path(path).name, b, a, (lb, ob), (la, oa), -touch, back,
                      note="built by reversing the recorded flight; fly it once by hand to confirm")
    for r in (fwd, rev):
        r["problems"] = check_route(r)
        store.save_route(r)
    return fwd, rev


def mission_items(route, sysid, compid):
    """MISSION_ITEM_INT list. Item 0 is the home slot, which ArduPilot overwrites."""
    rel = MAV.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
    items = []

    def add(cmd, frame=rel, p1=0, p2=0, p3=0, p4=0, lat=0.0, lon=0.0, alt=0.0):
        items.append(dict(cmd=cmd, frame=frame, p1=p1, p2=p2, p3=p3, p4=p4,
                          x=int(round(lat * 1e7)), y=int(round(lon * 1e7)), z=float(alt)))

    add(MAV.MAV_CMD_NAV_WAYPOINT, frame=MAV.MAV_FRAME_GLOBAL)          # 0: home
    add(MAV.MAV_CMD_NAV_TAKEOFF, alt=route["takeoff_alt"])            # 1
    add(MAV.MAV_CMD_DO_CHANGE_SPEED, frame=MAV.MAV_FRAME_MISSION, p1=1, p2=route["cruise_speed"], p3=-1)
    for w in route["waypoints"]:
        add(MAV.MAV_CMD_NAV_WAYPOINT, lat=w["lat"], lon=w["lon"], alt=w["alt"])
    f = route["final"]
    add(MAV.MAV_CMD_NAV_WAYPOINT, p1=2, lat=f["lat"], lon=f["lon"], alt=f["alt"])  # wait 2 s above the pad
    add(MAV.MAV_CMD_NAV_LAND, lat=route["land"]["lat"], lon=route["land"]["lon"], alt=0)
    return items


# --------------------------------------------------------------------------
# Fly: run a pad-to-pad trip
# --------------------------------------------------------------------------
class MissionRunner:
    """One backend trip at a time. All entry points return quickly; the trip
    runs in its own thread. state is reported to the page and the cloud."""

    def __init__(self, link, store, sa_ch):
        self.link, self.store, self.sa_ch = link, store, sa_ch
        self.lock = threading.Lock()
        self.thread = None
        self.items = None
        self.upload_event = threading.Event()
        self.upload_result = None
        self.mission = {"state": "idle", "from": None, "to": None, "item": 0, "items": 0,
                        "reason": None, "cmd_id": None, "started": None, "ended": None}
        self.current_seq = 0
        self.reached_seq = -1
        self.route_check = None     # route, pad -> reason to refuse (the legal ceiling), set by the server

    # ---- state shown to the page / cloud ----------------------------------
    def sa_on(self):
        return bool(self.link.state.get("sa_on"))

    def current_pad(self):
        s = self.link.state
        if s["lat"] is None or s["armed"]:
            return None
        best = None
        for pid, p in self.store.pads().items():
            d = dist_m(s["lat"], s["lon"], p["lat"], p["lon"])
            if d <= PAD_MATCH_M and (best is None or d < best[1]):
                best = (pid, d)
        return best[0] if best else None

    def status(self):
        m = dict(self.mission)
        return m

    def _set(self, **kw):
        self.mission.update(kw)

    # ---- MAVLink hooks (called from the link thread) -----------------------
    def on_message(self, msg):
        t = msg.get_type()
        if t in ("MISSION_REQUEST_INT", "MISSION_REQUEST") and self.items is not None:
            seq = msg.seq
            if 0 <= seq < len(self.items):
                it = self.items[seq]
                L = self.link
                L.send(L.m.mav.mission_item_int_send, L.sysid, L.compid, seq, it["frame"], it["cmd"],
                       0, 1, it["p1"], it["p2"], it["p3"], it["p4"], it["x"], it["y"], it["z"],
                       MAV.MAV_MISSION_TYPE_MISSION)
        elif t == "MISSION_ACK" and self.items is not None and getattr(msg, "mission_type", 0) == 0:
            self.upload_result = msg.type
            self.upload_event.set()
        elif t == "MISSION_CURRENT":
            self.current_seq = msg.seq
            if self.mission["state"] in ("enroute", "landing"):
                self._set(item=msg.seq)
        elif t == "MISSION_ITEM_REACHED":
            self.reached_seq = msg.seq

    # ---- checks -----------------------------------------------------------
    def preflight(self, dest):
        s = self.link.state
        if not s["link"]:
            return None, "no link to the drone"
        if not self.sa_on():
            return None, "SA switch is off: backend control not allowed"
        if s["armed"]:
            return None, "drone is armed: it must be landed on a pad"
        if s["sd_stop"]:
            return None, "SD kill switch is on stop"
        pads = self.store.pads()
        if dest not in pads:
            return None, f"unknown pad '{dest}'"
        here = self.current_pad()
        if here is None:
            return None, "drone is not on a known pad"
        if here == dest:
            return None, f"drone is already on {dest}"
        route = self.store.route(here, dest)
        if not route:
            return None, f"no route {here} -> {dest}; record one first"
        if not route.get("approved"):
            return None, f"route {here} -> {dest} is not approved"
        if s["gps_fix"] < 3 or s["sats"] < MIN_SATS:
            return None, f"GPS: fix {s['gps_fix']}, {s['sats']} sats (need 3D, {MIN_SATS}+)"
        if s["batt_pct"] is None or s["batt_pct"] < MIN_BATT_PCT:
            return None, f"battery {s['batt_pct']}% (need {MIN_BATT_PCT}%+)"
        if s["batt_v"] is None or s["batt_v"] / 6 < MIN_CELL_V:
            return None, f"battery {s['batt_v']} V (need {MIN_CELL_V * 6:.1f} V+)"
        if self.thread and self.thread.is_alive():
            return None, "a trip is already running"
        if self.route_check:
            why = self.route_check(route, pads[here])
            if why:
                return None, why
        return (here, route), None

    # ---- commands ---------------------------------------------------------
    def command(self, action, pad=None, cmd_id=None):
        """Returns (accepted: bool, reason). Never blocks long."""
        with self.lock:
            if action == "goto":
                ok, why = self.preflight(pad)
                if why:
                    self.link.note(f"Backend: goto {pad} refused: {why}", 4)
                    return False, why
                here, route = ok
                self._set(state="starting", **{"from": here}, to=pad, item=0, items=0, reason=None,
                          cmd_id=cmd_id, started=_now(), ended=None)
                self.thread = threading.Thread(target=self._trip, args=(route,), daemon=True)
                self.thread.start()
                return True, None
            if action == "hold":
                if self.mission["state"] not in ("starting", "enroute", "landing"):
                    return False, "no trip in progress"
                # BRAKE holds position and height and ignores the sticks. LOITER would
                # follow the throttle stick, which is often at the bottom during AUTO.
                self.link.set_mode("BRAKE")
                self._set(state="holding", reason="hold from backend", cmd_id=cmd_id)
                self.link.note("Backend: HOLD (BRAKE)")
                return True, None
            if action == "resume":
                if self.mission["state"] != "holding":
                    return False, "trip is not on hold"
                if not self.sa_on():
                    return False, "SA switch is off"
                self.link.set_mode("AUTO")
                self._set(state="enroute", reason=None, cmd_id=cmd_id)
                self.link.note("Backend: RESUME (AUTO)")
                return True, None
            if action == "return":
                if not self.link.state["armed"]:
                    return False, "drone is on the ground"
                if not self.sa_on():
                    return False, "SA switch is off"
                self.link.set_mode("RTL")
                self._set(state="returning", reason="return from backend", cmd_id=cmd_id)
                self.link.note("Backend: RETURN (RTL to the start pad)")
                return True, None
            return False, f"unknown action '{action}'"

    # ---- the trip ---------------------------------------------------------
    def _wait(self, cond, timeout):
        end = _now() + timeout
        while _now() < end:
            if cond():
                return True
            time.sleep(0.1)
        return False

    def _fail(self, why):
        self._set(state="failed", reason=why, ended=_now())
        self.link.note(f"Backend: trip failed: {why}", 3)

    def upload(self, route):
        L = self.link
        self.items = mission_items(route, L.sysid, L.compid)
        for attempt in range(3):
            self.upload_event.clear()
            self.upload_result = None
            L.send(L.m.mav.mission_count_send, L.sysid, L.compid, len(self.items), MAV.MAV_MISSION_TYPE_MISSION)
            if self.upload_event.wait(15) and self.upload_result == MAV.MAV_MISSION_ACCEPTED:
                return True
        return False

    def _trip(self, route):
        L, s = self.link, self.link.state
        try:
            self._set(state="uploading")
            if not self.upload(route):
                return self._fail(f"mission upload failed (ack {self.upload_result})")
            n = len(self.items)
            self._set(items=n - 1)
            L.note(f"Backend: route {route['from']} -> {route['to']} uploaded ({n - 1} items)")
            # Arm in GUIDED (no throttle needed), then start the mission.
            L.set_mode("GUIDED")
            if not self._wait(lambda: s["mode"] == "GUIDED", 5):
                return self._fail("drone did not enter GUIDED")
            if not self.sa_on():
                return self._fail("SA turned off before takeoff")
            L.command(MAV.MAV_CMD_COMPONENT_ARM_DISARM, 1)
            if not self._wait(lambda: s["armed"], 6):
                return self._fail("drone refused to arm (see its PreArm message)")
            self.reached_seq = -1
            L.command(MAV.MAV_CMD_MISSION_START, 0, 0)
            if not self._wait(lambda: s["mode"] == "AUTO", 5):
                L.set_mode("LAND")
                return self._fail("drone did not start AUTO; landing")
            self._set(state="enroute")
            land_seq = n - 1
            while True:
                time.sleep(0.2)
                if not s["armed"]:
                    if self.reached_seq >= land_seq - 1 or self.current_seq >= land_seq:
                        self._set(state="arrived", item=land_seq, ended=_now())
                        L.note(f"Backend: arrived at {route['to'].upper()}")
                    else:
                        self._fail("disarmed before the landing")
                    return
                st = self.mission["state"]
                if st == "holding":
                    if s["mode"] != "BRAKE":  # the pilot or the SA guard took over during the hold
                        self._set(state="pilot", reason=f"pilot control (mode changed to {s['mode']})", ended=_now())
                        L.note(f"Backend: hold ended, mode {s['mode']}. Pilot has control.", 4)
                        return
                    continue
                if st == "returning":
                    continue
                if self.current_seq >= land_seq and st == "enroute":
                    self._set(state="landing")
                if s["mode"] != "AUTO":
                    # pilot moved the mode switch, or the SA guard / a failsafe changed mode
                    why = "SA off" if not self.sa_on() else f"mode changed to {s['mode']}"
                    self._set(state="pilot", reason=f"pilot control ({why})", ended=_now())
                    L.note(f"Backend: trip stopped, {why}. Pilot has control.", 4)
                    return
        except Exception as exc:  # never die silently
            self._fail(f"error: {exc}")
        finally:
            self.items = None


# --------------------------------------------------------------------------
# One object for the server: wires the parts to the link
# --------------------------------------------------------------------------
class Autonomy:
    def __init__(self, link, sa_ch, root=ROUTES):
        self.link = link
        link.sa_ch = sa_ch
        self.store = Store(root)
        self.runner = MissionRunner(link, self.store, sa_ch)
        self.recorder = RouteRecorder(link, self.store, self._recorded)
        link.hooks.append(self.runner.on_message)
        link.pos_hooks.append(self.recorder.on_position)
        self.acks = []   # command results waiting to go to the cloud

    def _recorded(self, path):
        try:
            fwd, rev = routes_from_recording(path, self.store)
            for r in (fwd, rev):
                p = "; ".join(r["problems"]) or "no problems found"
                self.link.note(f"Laptop: route {r['from']} -> {r['to']} built: {r['length_m']} m, "
                               f"{len(r['waypoints'])} waypoints. Not approved yet ({p}).")
        except Exception as exc:
            self.link.note(f"Laptop: route build failed: {exc}", 3)

    def summary(self):
        pads = self.store.pads()
        routes = [{"from": r["from"], "to": r["to"], "approved": r.get("approved", False),
                   "length_m": r.get("length_m"), "est_time_s": r.get("est_time_s"), "max_alt": r.get("max_alt"),
                   "problems": r.get("problems", []), "takeoff_alt": r.get("takeoff_alt"),
                   "path": [[pads.get(r["from"], {}).get("lat"), pads.get(r["from"], {}).get("lon")]]
                           + [[w["lat"], w["lon"]] for w in r["waypoints"]] + [[r["land"]["lat"], r["land"]["lon"]]]}
                  for r in self.store.routes()]
        return {"sa_ch": self.link.sa_ch, "sa_on": self.link.state["sa_on"], "pad": self.runner.current_pad(),
                "pads": {k: {"name": v["name"], "lat": v["lat"], "lon": v["lon"]} for k, v in pads.items()},
                "routes": routes, "mission": self.runner.status(), "recording": self.recorder.status()}

    def cloud_summary(self):
        """Small version for the 1 Hz cloud push."""
        m = self.runner.status()
        ready = sorted({r["to"] for r in self.store.routes()
                        if r.get("approved") and r["from"] == self.runner.current_pad()})
        return {"sa_on": self.link.state["sa_on"], "pad": self.runner.current_pad(),
                "pads": {k: {"name": v["name"], "lat": v["lat"], "lon": v["lon"]}
                         for k, v in self.store.pads().items()},
                "can_goto": ready,
                "mission": {k: m[k] for k in ("state", "from", "to", "item", "items", "reason", "cmd_id")}}

    def handle_command(self, cmd, source):
        """cmd: {"id", "action", "pad"?}. Returns the ack for the cloud."""
        ok, why = self.runner.command(cmd.get("action"), cmd.get("pad"), cmd.get("id"))
        ack = {"id": cmd.get("id"), "status": "accepted" if ok else "rejected", "reason": why}
        self.link.note(f"{source}: {cmd.get('action')} {cmd.get('pad') or ''} -> {ack['status']}"
                       + (f" ({why})" if why else ""), 6 if ok else 4)
        return ack
