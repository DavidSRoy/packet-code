"""Legal ceiling for a small drone (Part 107) at any point of the map.

Static part (rebuilt when the data changes), one value per 20 m cell, metres MSL:

  rule  = max(ground + 400 ft,  top of the tallest building within 400 ft + 400 ft)   14 CFR 107.51(b)
  limit = floor of the Class B / C shelf above the cell - 100 ft margin
  static = min(rule, limit)

Cells inside the surface area of Class B/C/D airspace, or of Class E for an
airport, need an ATC authorization (14 CFR 107.41). Without a stored
authorization they are NO-FLY. With one, the ceiling is the authorized height.

Live part, checked at each query: TFRs from tfr.faa.gov and stadium events
(FDC 4/3621: 3 NM, up to 3000 ft AGL, 1 h before to 1 h after a game).

Look-ahead: the value for a point is the lowest value within LOOKAHEAD_M, so
the fence comes down before the drone reaches a lower area.
"""
import math
import time

import numpy as np

from . import geo
from .geo import FT, M_PER_DEG
from .sources import rings

AGL_LIMIT_M = 400 * FT            # 121.92 m
STRUCT_RADIUS_M = 400 * FT        # building bonus applies within 400 ft of the structure
CLASS_MARGIN_M = 100 * FT         # stay this far below a Class B/C shelf floor
LOOKAHEAD_M = 60.0
FALLBACK_RADIUS_M = 3000.0        # area for the link-loss fallback ceiling
TFR_LEAD_S = 600                  # a TFR counts as active this long before it starts
TFR_WARN_S = 1800                 # warn about TFRs that start within 30 min
STADIUM_RADIUS_M = 3 * 1852.0
STADIUM_PAD_S = 3600

# Stadiums under the blanket stadium TFR (MLB, NFL, NCAA D-I football). Positions: OpenStreetMap, 2026-10-26.
STADIUMS = {
    "husky": ("Husky Stadium", 47.65037, -122.30184),
    "lumen": ("Lumen Field", 47.59534, -122.33164),
    "tmobile": ("T-Mobile Park", 47.59136, -122.33243),
}

SURFACE_TYPES = {"CLASS_D", "CLASS_E2", "CLASS_E3", "CLASS_E4"}


def _floor_m(props):
    """Floor of an airspace shape: (metres, 'MSL' | 'AGL')."""
    v = float(props.get("LOWER_VAL") or 0)
    code = (props.get("LOWER_CODE") or "").upper()
    uom = (props.get("LOWER_UOM") or "FT").upper()
    if uom == "FL":
        v *= 100
    return v * FT, ("MSL" if code == "MSL" else "AGL")


class CeilingMap:
    def __init__(self, grid, ground, buildings, classes, uasfm=None, log=print):
        self.grid, self.ground, self.buildings, self.log = grid, ground.astype(np.float32), buildings, log
        self.classes = classes
        self.uasfm = uasfm
        self.built_at = time.time()
        self._build()

    # ------------------------------------------------------------ build
    def _build(self):
        g, ground = self.grid, self.ground
        t0 = time.time()
        # building tops (m MSL) on their own cells
        top = np.full(g.shape, -np.inf, dtype=np.float32)
        self.bins = {}
        for i, b in enumerate(self.buildings):
            lat = sum(p[0] for p in b["ring"]) / len(b["ring"])
            lon = sum(p[1] for p in b["ring"]) / len(b["ring"])
            b["lat"], b["lon"] = lat, lon
            cell = g.cell(lat, lon)
            if cell is None:
                continue
            b["top"] = float(ground[cell]) + b["h"]
            geo.fill_ring(g, b["ring"], top, np.float32(b["top"]), np.maximum)
            top[cell] = max(top[cell], b["top"])
            self.bins.setdefault((int(lat / 0.002), int(lon / 0.003)), []).append(i)
        near_top = geo.disk_filter(top, g.cells_for_m(STRUCT_RADIUS_M), np.maximum)
        self.rule = np.maximum(ground + AGL_LIMIT_M, near_top + AGL_LIMIT_M).astype(np.float32)

        # Class B/C shelves and surface areas
        floor_msl = np.full(g.shape, np.inf, dtype=np.float32)
        floor_agl = np.full(g.shape, np.inf, dtype=np.float32)
        self.surface = np.zeros(g.shape, dtype=bool)
        self.surface_names = []
        self.shelves = []
        for f in self.classes.get("features", []):
            p = f["properties"]
            cls, local = (p.get("CLASS") or ""), (p.get("LOCAL_TYPE") or "")
            floor, ref = _floor_m(p)
            for ring in rings(f.get("geometry")):
                if (cls in ("B", "C") and floor <= 0) or local in SURFACE_TYPES:
                    geo.fill_ring(g, ring, self.surface, True)
                    self.surface_names.append((p.get("NAME"), ring))
                elif cls in ("B", "C"):
                    geo.fill_ring(g, ring, floor_msl if ref == "MSL" else floor_agl, np.float32(floor), np.minimum)
                    self.shelves.append((p.get("NAME"), floor, ref, ring))
        self.floor = np.minimum(floor_msl, ground + floor_agl).astype(np.float32)
        self.limit = (self.floor - CLASS_MARGIN_M).astype(np.float32)
        self.static = np.minimum(self.rule, self.limit)

        r = g.cells_for_m(LOOKAHEAD_M)
        self.static_la = geo.disk_filter(self.static, r, np.minimum)
        self.surface_la = geo.disk_filter(self.surface, r, np.maximum)
        self.base_fb = np.minimum(ground + AGL_LIMIT_M, self.limit)   # no building bonus
        self.log(f"airspace: ceiling map built ({g.rows}x{g.cols} cells, {len(self.buildings)} buildings, "
                 f"{time.time() - t0:.1f} s)")

    # ------------------------------------------------------------ helpers
    def ground_at(self, lat, lon):
        cell = self.grid.cell(lat, lon)
        return None if cell is None else float(self.ground[cell])

    def building_at(self, lat, lon):
        """The building whose outline contains the point (or None)."""
        k = (int(lat / 0.002), int(lon / 0.003))
        for dk in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            for i in self.bins.get((k[0] + dk[0], k[1] + dk[1]), []):
                b = self.buildings[i]
                if geo.point_in_ring(lat, lon, b["ring"]):
                    return b
        return None

    def tallest_near(self, lat, lon, radius_m=STRUCT_RADIUS_M):
        best = None
        k = (int(lat / 0.002), int(lon / 0.003))
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                for i in self.bins.get((k[0] + dr, k[1] + dc), []):
                    b = self.buildings[i]
                    if "top" not in b or (best is not None and b["top"] <= best["top"]):
                        continue
                    if geo.point_in_ring(lat, lon, b["ring"]) or geo.dist_to_ring_m(lat, lon, b["ring"]) <= radius_m:
                        best = b
        return best

    def fallback_amsl(self, lat, lon):
        """Lowest '400 ft above ground' / shelf value within FALLBACK_RADIUS_M (no building bonus)."""
        g = self.grid
        cell = g.cell(lat, lon)
        if cell is None:
            return None
        k = int(g.cells_for_m(FALLBACK_RADIUS_M))
        r, c = cell
        sub = self.base_fb[max(0, r - k):r + k + 1, max(0, c - k):c + k + 1]
        return float(sub.min())

    # ------------------------------------------------------------ query
    def query(self, lat, lon, now=None, tfrs=(), events=(), auths=()):
        """Ceiling at a point, with the reason. All heights in metres MSL (NAVD88 ground)."""
        now = time.time() if now is None else now
        g = self.grid
        cell = g.cell(lat, lon)
        if cell is None:
            return {"ok": False, "reason": "outside the ceiling map", "nofly": False}
        ground = float(self.ground[cell])
        rule, limit = float(self.rule[cell]), float(self.limit[cell])
        ceil = float(self.static_la[cell])
        warnings = []
        if limit < rule and ceil >= limit - 0.5:
            reason = f"Class B floor {self.floor[cell] / FT:.0f} ft MSL, less 100 ft"
        elif ceil < min(rule, limit) - 0.5:
            reason = f"lower ceiling within {LOOKAHEAD_M:.0f} m"
        elif rule > ground + AGL_LIMIT_M + 0.5:
            b = self.tallest_near(lat, lon)
            reason = (f"{b['name']} ({b['h']:.0f} m{' est.' if b['src'] == 'levels' else ''}) + 400 ft"
                      if b else "building within 400 ft + 400 ft")
        else:
            reason = "400 ft above ground"
        nofly = False

        # surface areas: authorization needed
        if self.surface_la[cell]:
            auth = next((a for a in auths if a["start"] <= now <= a["end"]
                         and math.hypot(*geo.local_m(a["lat"], a["lon"], lat, lon)) <= a["radius_m"] - LOOKAHEAD_M),
                        None)
            name = next((n for n, ring in self.surface_names if geo.ring_touches_disk(lat, lon, LOOKAHEAD_M, ring)),
                        "controlled airspace")
            if auth:
                cap = ground + auth["max_ft"] * FT
                if cap < ceil:
                    ceil, reason = cap, f"ATC authorization '{auth['name']}' {auth['max_ft']:.0f} ft"
            else:
                nofly, reason = True, f"{name} surface area: needs an ATC authorization"

        # TFRs
        for t in tfrs:
            for a in t["areas"]:
                active = any((s is None or s - TFR_LEAD_S <= now) and (e is None or now <= e) for s, e in a["schedule"])
                soon = any(s is not None and now < s - TFR_LEAD_S <= now + TFR_WARN_S for s, e in a["schedule"])
                if not (active or soon) or not geo.ring_touches_disk(lat, lon, LOOKAHEAD_M, a["ring"]):
                    continue
                if soon and not active:
                    warnings.append(f"TFR {t['id']} starts soon")
                    continue
                lower = a["lower_m"] + (ground if a["lower_ref"] == "AGL" else 0.0)
                if lower <= ground + 1.0:
                    nofly, reason = True, f"TFR {t['id']} ({t.get('type') or 'TFR'})"
                elif lower - CLASS_MARGIN_M < ceil:
                    ceil, reason = lower - CLASS_MARGIN_M, f"TFR {t['id']} floor"

        # stadium events
        for ev in events:
            st = STADIUMS.get(ev["stadium"])
            if not st or not (ev["start"] - STADIUM_PAD_S - TFR_LEAD_S <= now <= ev["end"] + STADIUM_PAD_S):
                continue
            if math.hypot(*geo.local_m(st[1], st[2], lat, lon)) <= STADIUM_RADIUS_M + LOOKAHEAD_M:
                nofly, reason = True, f"stadium TFR: {st[0]} event"

        if not nofly and ceil < ground + 10:
            nofly, reason = True, reason + " (less than 10 m above ground)"
        return {"ok": True, "lat": lat, "lon": lon, "ground_m": round(ground, 1), "ceiling_amsl": round(ceil, 1),
                "ceiling_agl": round(ceil - ground, 1), "nofly": nofly, "reason": reason, "warnings": warnings}

    # ------------------------------------------------------------ picture for the map
    def overlay_png(self):
        """RGBA picture of the static ceiling above ground, for the ground-control map."""
        agl_ft = (self.static - self.ground) / FT
        h, w = agl_ft.shape
        img = np.zeros((h, w, 4), dtype=np.uint8)
        stops = [(0, (200, 30, 58)), (100, (234, 90, 44)), (200, (243, 146, 51)), (300, (233, 208, 74)),
                 (399, (127, 199, 122)), (400, (76, 175, 143)), (600, (64, 150, 220)), (1000, (110, 90, 230))]
        img[..., 3] = 120
        for lo, col in stops:
            sel = agl_ft >= lo
            img[sel, 0], img[sel, 1], img[sel, 2] = col
        # 400 ft exactly: plain area, lighter
        plain = np.abs(agl_ft - 400) < 1
        img[plain, 3] = 60
        # surface areas: red stripes
        rr, cc = np.indices((h, w))
        stripe = self.surface & (((rr + cc) // 4) % 2 == 0)
        img[stripe] = (255, 40, 40, 170)
        img[self.surface & ~stripe, 3] = 90
        # Leaflet stretches an image linearly in Web Mercator: pick the grid row for each Mercator row
        g = self.grid
        merc = lambda lat: np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
        y = merc(g.n_edge) - (np.arange(h) + 0.5) * (merc(g.n_edge) - merc(g.s_edge)) / h
        lat = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
        src = np.clip(((g.n_edge - lat) / g.dlat).astype(int), 0, h - 1)
        return geo.png_rgba(np.ascontiguousarray(img[src]))

    def bounds(self):
        g = self.grid
        return [[g.s_edge, g.w], [g.n_edge, g.e_edge]]
