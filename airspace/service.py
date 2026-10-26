"""Keeps the ceiling map loaded and up to date for ground control.

- Builds the map in a background thread at start (first run downloads about
  30 MB; later runs use airspace/cache).
- Refreshes TFRs every 5 minutes, FAA airspace daily, buildings weekly.
- Holds stadium events and ATC authorizations that the operator enters on the
  ground-control page (saved in airspace/cache/operator.json).
"""
import json
import threading
import time
import traceback

from . import geo, sources
from .ceiling import STADIUMS, CeilingMap

# greater Seattle: Everett to Federal Way, Puget Sound to Issaquah
DEFAULT_REGION = (47.40, -122.52, 47.86, -122.00)


class AirspaceService:
    def __init__(self, region=DEFAULT_REGION, res_m=20.0, log=print):
        self.grid = geo.Grid(*region, res_m=res_m)
        self.log = log
        self.map = None
        self.tfrs, self.tfr_age = [], None
        self.classes = self.uasfm = None
        self.status = {"state": "loading", "error": None, "built": None, "tfr_t": None,
                       "class_t": None, "bld_t": None, "buildings": 0}
        self.lock = threading.Lock()
        self.op_path = sources._cache("operator.json")
        self.operator = {"events": [], "auths": []}
        try:
            self.operator = json.loads(self.op_path.read_text())
        except (OSError, ValueError):
            pass
        self._overlay = None

    # ------------------------------------------------------------ data
    def start(self):
        threading.Thread(target=self._run, daemon=True, name="airspace").start()
        return self

    def _build(self):
        g = self.grid
        ground = sources.dem(g, log=self.log)
        blds, bld_age = sources.buildings(g, log=self.log)
        classes, _ = sources.faa_classes(g)
        uasfm, _ = sources.faa_uasfm(g)
        m = CeilingMap(g, ground, blds, classes, uasfm, log=self.log)
        with self.lock:
            self.map, self.classes, self.uasfm, self._overlay = m, classes, uasfm, None
        now = time.time()
        self.status.update(state="ready", error=None, built=now, class_t=now,
                           bld_t=now - (bld_age or 0), buildings=len(blds))

    def _refresh_tfrs(self):
        t, age = sources.tfrs(self.grid, log=self.log)
        with self.lock:
            self.tfrs = t
        self.status["tfr_t"] = time.time() - (age or 0)

    def _run(self):
        next_build = 0.0
        next_tfr = 0.0
        while True:
            now = time.time()
            try:
                if now >= next_build:
                    self._build()
                    next_build = now + 86400
            except Exception as exc:
                self.status.update(state="error" if self.map is None else "ready", error=f"map: {exc}")
                self.log(f"airspace: map build failed: {exc}")
                traceback.print_exc()
                next_build = now + 300
            try:
                if now >= next_tfr:
                    self._refresh_tfrs()
                    next_tfr = now + 300
            except Exception as exc:
                self.status["error"] = f"TFR: {exc}"
                self.log(f"airspace: TFR refresh failed: {exc}")
                next_tfr = now + 60
            time.sleep(5)

    # ------------------------------------------------------------ operator input
    def _save(self):
        self.op_path.write_text(json.dumps(self.operator, indent=1))

    def add_event(self, stadium, start, end):
        if stadium not in STADIUMS or not end > start:
            raise ValueError("unknown stadium or bad times")
        self.operator["events"].append({"stadium": stadium, "start": float(start), "end": float(end)})
        self._prune()

    def add_auth(self, name, lat, lon, radius_m, max_ft, start, end):
        if not (0 < max_ft <= 400 and 50 <= radius_m <= 20000 and end > start):
            raise ValueError("authorization: height 1-400 ft, radius 50-20000 m, end after start")
        self.operator["auths"].append({"name": str(name)[:60], "lat": float(lat), "lon": float(lon),
                                       "radius_m": float(radius_m), "max_ft": float(max_ft),
                                       "start": float(start), "end": float(end)})
        self._prune()

    def remove(self, kind, index):
        lst = self.operator.get(kind)
        if lst is not None and 0 <= index < len(lst):
            lst.pop(index)
            self._save()

    def _prune(self):
        now = time.time()
        self.operator["events"] = [e for e in self.operator["events"] if e["end"] + 7200 > now]
        self.operator["auths"] = [a for a in self.operator["auths"] if a["end"] > now]
        self._save()

    # ------------------------------------------------------------ queries
    def ready(self):
        return self.map is not None

    def query(self, lat, lon, now=None):
        m = self.map
        if m is None:
            return {"ok": False, "reason": "ceiling map not loaded yet", "nofly": False}
        with self.lock:
            tfrs = list(self.tfrs)
        return m.query(lat, lon, now, tfrs, self.operator["events"], self.operator["auths"])

    def home_amsl(self, lat, lon, extra_m=0.0):
        """Height (m, NAVD88) of the take-off point: ground, plus the roof when the
        point is inside a building outline, plus an operator offset."""
        m = self.map
        if m is None:
            return None, "no map"
        g = m.ground_at(lat, lon)
        if g is None:
            return None, "outside the map"
        b = m.building_at(lat, lon)
        if b is not None:
            return g + b["h"] + extra_m, f"roof of {b['name']} ({b['h']:.0f} m)"
        return g + extra_m, "ground"

    def fallback_amsl(self, lat, lon):
        m = self.map
        return None if m is None else m.fallback_amsl(lat, lon)

    def overlay(self):
        m = self.map
        if m is None:
            return None
        if self._overlay is None:
            self._overlay = m.overlay_png()
        return self._overlay

    def layers(self):
        """GeoJSON-ish data for the map page."""
        m = self.map
        now = time.time()
        out = {"status": self.summary(), "bounds": m.bounds() if m else None,
               "classes": self.classes, "uasfm": self.uasfm, "tfrs": [], "stadiums": [], "auths": []}
        with self.lock:
            tfrs = list(self.tfrs)
        for t in tfrs:
            for a in t["areas"]:
                active = any((s is None or s <= now) and (e is None or now <= e) for s, e in a["schedule"])
                out["tfrs"].append({"id": t["id"], "type": t.get("type"), "desc": t.get("desc"), "name": a["name"],
                                    "ring": a["ring"], "active": active, "lower_m": a["lower_m"],
                                    "lower_ref": a["lower_ref"], "upper_m": a["upper_m"], "upper_ref": a["upper_ref"],
                                    "schedule": a["schedule"]})
        for key, (name, lat, lon) in STADIUMS.items():
            evs = [e for e in self.operator["events"] if e["stadium"] == key]
            out["stadiums"].append({"key": key, "name": name, "lat": lat, "lon": lon, "events": evs,
                                    "active": any(e["start"] - 3600 <= now <= e["end"] + 3600 for e in evs)})
        out["auths"] = self.operator["auths"]
        out["events"] = self.operator["events"]
        return out

    def summary(self):
        s = dict(self.status)
        now = time.time()
        for k in ("built", "tfr_t", "class_t", "bld_t"):
            s[k.replace("_t", "") + "_age_s"] = None if s.get(k) is None else round(now - s[k])
        s["tfr_count"] = len(self.tfrs)
        return s
