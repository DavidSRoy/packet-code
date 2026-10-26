"""Automatic max altitude: sends the legal ceiling to the drone.

Twice per second it finds the ceiling at the drone (airspace/ceiling.py),
turns it into metres above home (FENCE_ALT_MAX_TP = 1) and sends it to
lua/ceil_guard.lua on the flight controller as NAMED_VALUE_FLOAT:

  CEIL_SET = ceiling (m MSL) - home height (m MSL) - VERTICAL_MARGIN_M
  CEIL_FB  = the same for the link-loss fallback

The script on the FC sets FENCE_ALT_MAX and reports back CEIL_FC / CEIL_ST.

Horizontal NO-FLY guard: it also sends the nearest NO-FLY edge

  CEIL_NLA, CEIL_NLO = the nearest point on the edge (deg; float32, about 0.6 m)
  CEIL_NFD = distance to that edge (m), negative inside, NO_EDGE_M if none near

and ceil_guard.lua stops the drone before it reaches the edge.

Home height: ground under home (USGS 3DEP), plus the roof when home is inside
a building outline, plus --home-offset (for a pad on a structure that the map
does not know).
"""
import threading
import time

from pymavlink import mavutil

VERTICAL_MARGIN_M = 10.0     # GPS/baro/map error budget
SEND_PERIOD_S = 0.5
NO_EDGE_M = 9999.0           # CEIL_NFD when no NO-FLY edge is within EDGE_SEARCH_M
ROUTE_EDGE_BUF_M = 50.0      # trips keep this far from NO-FLY edges
NO_POS = (None, 0)


class CeilingLink:
    def __init__(self, link, airspace, enabled=True, home_offset_m=0.0):
        self.link, self.air, self.enabled, self.home_offset = link, airspace, enabled, home_offset_m
        self.fc = {"fence": None, "state": None, "t": 0.0, "tp": None, "fence_on": None, "fence_type": None}
        self.state = {"mode": "auto" if enabled else "off"}
        self.home = None              # (lat, lon, amsl, source)
        link.hooks.append(self.on_msg)

    # ---- from the drone ---------------------------------------------------
    def on_msg(self, msg):
        t = msg.get_type()
        if t == "NAMED_VALUE_FLOAT":
            name = msg.name if isinstance(msg.name, str) else msg.name.decode(errors="ignore")
            name = name.rstrip("\x00")
            if name == "CEIL_FC":
                self.fc["fence"], self.fc["t"] = round(msg.value, 1), time.time()
            elif name == "CEIL_ST":
                self.fc["state"] = int(round(msg.value))
            elif name == "CEIL_NFL":
                self.fc["nf_lb"] = round(msg.value, 1)
        elif t == "PARAM_VALUE":
            pid = msg.param_id if isinstance(msg.param_id, str) else msg.param_id.decode(errors="ignore")
            if pid == "FENCE_ALT_MAX_TP":
                self.fc["tp"] = int(msg.param_value)
            elif pid == "FENCE_ENABLE":
                self.fc["fence_on"] = msg.param_value > 0
            elif pid == "FENCE_TYPE":
                self.fc["fence_type"] = int(msg.param_value)

    def _ask_params(self):
        L = self.link
        if L.sysid is None:
            return
        for name in (b"FENCE_ALT_MAX_TP", b"FENCE_ENABLE", b"FENCE_TYPE"):
            L.send(L.m.mav.param_request_read_send, L.sysid, L.compid, name, -1)

    def _send(self, name, value):
        L = self.link
        L.send(L.m.mav.named_value_float_send, int(time.time() * 1000) & 0xFFFFFFFF,
               name.encode(), float(value))

    # ---- loop ------------------------------------------------------------
    def step(self):
        s = self.link.state
        st = {"mode": "auto" if self.enabled else "off", "map": self.air.summary()}
        hl = (s.get("home_lat"), s.get("home_lon"))
        pos = (s.get("lat"), s.get("lon"))
        if pos[0] in NO_POS:
            pos = hl
        if hl[0] in NO_POS and pos[0] not in NO_POS:
            hl = pos                                     # no home yet: the drone sits on its take-off point
        if pos[0] in NO_POS:
            st["status"] = "no position"
            self.state = st
            return
        if self.home is None or self.home[:2] != hl:
            amsl, src = self.air.home_amsl(hl[0], hl[1], self.home_offset)
            if amsl is not None:
                self.home = (hl[0], hl[1], amsl, src)
        q = self.air.query(pos[0], pos[1])
        st["here"] = q
        if not q.get("ok") or self.home is None:
            st["status"] = q.get("reason") or "no home height"
            self.state = st
            return
        home_amsl = self.home[2]
        target = q["ceiling_amsl"] - home_amsl - VERTICAL_MARGIN_M
        if q["nofly"]:
            target = 10.0
        fb_amsl = self.air.fallback_amsl(pos[0], pos[1])
        fb = None if fb_amsl is None else fb_amsl - home_amsl - VERTICAL_MARGIN_M
        st.update(home_amsl=round(home_amsl, 1), home_src=self.home[3], target_m=round(target, 1),
                  fallback_m=None if fb is None else round(fb, 1), nofly=q["nofly"], edge=q.get("edge"))
        fc_ok = time.time() - self.fc["t"] < 3
        st["fc"] = dict(self.fc, fresh=fc_ok)
        if self.fc["tp"] not in (None, 1):
            st["status"] = f"FENCE_ALT_MAX_TP is {self.fc['tp']}, needs 1 (above home): not sending"
        elif not self.enabled:
            st["status"] = "off (--ceiling off)"
        elif not s.get("link"):
            st["status"] = "no link: the FC uses its fallback"
        else:
            self._send("CEIL_SET", max(10.0, min(1000.0, target)))
            if fb is not None:
                self._send("CEIL_FB", max(10.0, min(1000.0, fb)))
            e = q.get("edge")
            if e:                                        # point first: the FC acts on CEIL_NFD
                self._send("CEIL_NLA", e["lat"])
                self._send("CEIL_NLO", e["lon"])
                self._send("CEIL_NFD", -e["dist_m"] if e["inside"] else e["dist_m"])
            else:
                self._send("CEIL_NFD", NO_EDGE_M)
            if not fc_ok:
                st["status"] = "sent; no reply from ceil_guard.lua on the FC (script not installed?)"
            elif self.fc["state"] == 2:
                st["status"] = "ABOVE THE LEGAL CEILING: descend"
            else:
                st["status"] = "active"
        if q["nofly"]:
            st["status"] = "NO-FLY: " + q["reason"]
        self.state = st

    def loop(self):
        next_params = 0.0
        while self.link.running:
            try:
                if self.link.sysid is not None and time.time() > next_params:
                    self._ask_params()
                    next_params = time.time() + 30
                self.step()
            except Exception as exc:          # never stop the loop
                self.state = {"mode": "auto" if self.enabled else "off", "status": f"error: {exc}"}
            time.sleep(SEND_PERIOD_S)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="ceiling").start()
        return self

    def takeoff_block(self):
        """Reason to refuse a takeoff here, or None."""
        st = self.state
        if st.get("nofly"):
            return st.get("status")
        return None


def check_route(airspace, route, pad, step_m=25.0):
    """Reason to refuse a trip, or None: a point of the route is in a NO-FLY area
    or above the legal ceiling (less the margin). Heights in a route are m above pad A."""
    import math
    home_amsl, _ = airspace.home_amsl(pad["lat"], pad["lon"])
    if home_amsl is None:
        return "legal ceiling unknown here (ceiling map not loaded or outside the map)"
    pts = [(pad["lat"], pad["lon"], route["takeoff_alt"])]
    pts += [(w["lat"], w["lon"], w["alt"]) for w in route["waypoints"]]
    pts.append((route["final"]["lat"], route["final"]["lon"], route["final"]["alt"]))
    samples = []
    for (a1, o1, h1), (a2, o2, h2) in zip(pts, pts[1:]):
        d = math.hypot((a2 - a1) * 111320.0, (o2 - o1) * 111320.0 * math.cos(math.radians(a1)))
        n = max(1, int(d / step_m))
        samples += [(a1 + (a2 - a1) * i / n, o1 + (o2 - o1) * i / n, h1 + (h2 - h1) * i / n) for i in range(n)]
    samples.append(pts[-1])
    for lat, lon, rel in samples:
        q = airspace.query(lat, lon)
        if not q.get("ok"):
            return f"legal ceiling unknown on the route ({q.get('reason')})"
        if q["nofly"]:
            return f"route crosses a NO-FLY area: {q['reason']}"
        e = q.get("edge")
        if e and e["dist_m"] < ROUTE_EDGE_BUF_M:
            return f"route passes {e['dist_m']:.0f} m from a NO-FLY area ({e['name']}); keep {ROUTE_EDGE_BUF_M:.0f} m"
        if home_amsl + rel > q["ceiling_amsl"] - VERTICAL_MARGIN_M:
            return (f"route height {rel:.0f} m is above the legal ceiling there "
                    f"({q['ceiling_amsl'] - home_amsl - VERTICAL_MARGIN_M:.0f} m above the pad: {q['reason']})")
    return None
