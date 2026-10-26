"""Tests for the ceiling map. Run: python -m airspace.test_ceiling (from packethw/)."""
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ground_control"))

from airspace import geo, sources                      # noqa: E402
from airspace.ceiling import AGL_LIMIT_M, CLASS_MARGIN_M, CeilingMap   # noqa: E402

FT = geo.FT
fails = []


def check(name, ok, extra=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {extra}")
    if not ok:
        fails.append(name)


def offset(lat, lon, n, e):
    return lat + n / geo.M_PER_DEG, lon + e / (geo.M_PER_DEG * math.cos(math.radians(lat)))


def square(lat, lon, half_m):
    return [offset(lat, lon, -half_m, -half_m), offset(lat, lon, -half_m, half_m),
            offset(lat, lon, half_m, half_m), offset(lat, lon, half_m, -half_m)]


def feature(ring, **props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [[[lo, la] for la, lo in ring + ring[:1]]]}}


def synthetic():
    # 4 km x 4 km, 20 m cells, flat ground at 10 m
    s, w = 47.60, -122.30
    n, e = offset(s, w, 4000, 4000)
    g = geo.Grid(s, w, n, e, 20.0)
    ground = np.full(g.shape, 10.0, dtype=np.float32)
    c = offset(s, w, 2000, 1000)                        # tower 100 m tall, 40 m square
    blds = [{"name": "Tower", "h": 100.0, "src": "measured", "ring": square(*c, 20)}]
    shelf = [offset(s, w, 0, 2600), offset(s, w, 0, 4000), offset(s, w, 4000, 4000), offset(s, w, 4000, 2600)]
    surf_c = offset(s, w, 600, 3300)
    classes = {"features": [
        feature(shelf, NAME="TEST CLASS B", CLASS="B", LOCAL_TYPE="CLASS_B", LOWER_VAL=500, LOWER_CODE="MSL",
                UPPER_VAL=10000, UPPER_CODE="MSL"),
        feature(geo.circle_ring(*surf_c, 300), NAME="TEST D", CLASS="D", LOCAL_TYPE="CLASS_D", LOWER_VAL=0,
                LOWER_CODE="SFC", UPPER_VAL=2500, UPPER_CODE="MSL"),
    ]}
    return g, CeilingMap(g, ground, blds, classes, log=lambda *a: None), c, surf_c, (s, w)


def main():
    g, m, tower, surf_c, (s, w) = synthetic()
    base = 10 + AGL_LIMIT_M
    far = offset(s, w, 3500, 300)
    q = m.query(*far)
    check("plain area: 400 ft above ground", abs(q["ceiling_amsl"] - base) < 0.2 and not q["nofly"], str(q))
    q = m.query(*offset(*tower, 0, 60))                       # 60 m east of the centre: 40 m from the wall
    check("near a tower: tower top + 400 ft", abs(q["ceiling_amsl"] - (10 + 100 + AGL_LIMIT_M)) < 0.2, str(q))
    q = m.query(*offset(*tower, 0, 20 + 122 + 80))            # well outside 400 ft of the wall
    check("beyond 400 ft of the tower: back to 400 ft AGL", abs(q["ceiling_amsl"] - base) < 0.2, str(q))
    q = m.query(*offset(*tower, 0, 20 + 122 - 30))            # in the tower zone, 30 m from its edge
    check("look-ahead: lower value within 60 m wins", abs(q["ceiling_amsl"] - base) < 0.2 and "within" in q["reason"], str(q))
    q = m.query(*offset(s, w, 2000, 3500))                    # under the 500 ft MSL shelf
    check("Class B shelf: floor - 100 ft", abs(q["ceiling_amsl"] - (500 * FT - CLASS_MARGIN_M)) < 0.2, str(q))
    q = m.query(*surf_c)
    check("Class D surface area: NO-FLY", q["nofly"] and "authorization" in q["reason"], str(q))
    now = time.time()
    auth = {"name": "LAANC test", "lat": surf_c[0], "lon": surf_c[1], "radius_m": 2000, "max_ft": 200,
            "start": now - 60, "end": now + 3600}
    q = m.query(*surf_c, auths=[auth])
    check("with an authorization: authorized height", not q["nofly"] and abs(q["ceiling_amsl"] - (10 + 200 * FT)) < 0.2, str(q))
    q = m.query(*surf_c, auths=[dict(auth, start=now + 600)])
    check("authorization not started: NO-FLY", q["nofly"], str(q))

    tfr_ring = square(*offset(s, w, 3000, 2000), 150)
    tfr = {"id": "9/9999", "type": "TEST", "areas": [{"name": "A", "ring": tfr_ring, "lower_m": 0, "lower_ref": "AGL",
                                                       "upper_m": 400 * FT, "upper_ref": "AGL", "schedule": [(now - 60, now + 600)]}]}
    inside = offset(s, w, 3000, 2000)
    check("active TFR: NO-FLY", m.query(*inside, tfrs=[tfr])["nofly"])
    q = m.query(*offset(*inside, 0, 150 + 40), tfrs=[tfr])
    e = q["edge"] or {}
    check("40 m outside a TFR: not NO-FLY, edge 40 m away", not q["nofly"] and not e.get("inside")
          and abs(e.get("dist_m", 0) - 40) < 1.5, str(q))
    zone = {"name": "pad", "lat": inside[0], "lon": inside[1] + 0.02, "radius_m": 50}
    zc = (zone["lat"], zone["lon"])
    q = m.query(*zc, zones=[zone])
    check("keep-out zone: NO-FLY inside", q["nofly"] and "keep-out" in q["reason"] and q["edge"]["inside"], str(q))
    q = m.query(*offset(*zc, 0, 80), zones=[zone])
    e = q["edge"] or {}
    check("30 m outside a keep-out zone: edge 30 m, edge point toward the zone",
          not q["nofly"] and abs(e.get("dist_m", 0) - 30) < 1.5 and e["lon"] < offset(*zc, 0, 80)[1], str(q))
    q = m.query(*offset(*zc, 0, -2200), zones=[zone])
    check("zone more than 2 km away: no edge", q.get("ok") and q["edge"] is None, str(q))
    later = dict(tfr, areas=[dict(tfr["areas"][0], schedule=[(now + 1200, now + 3600)])])
    q = m.query(*inside, tfrs=[later])
    check("TFR in 20 min: warning only", not q["nofly"] and q["warnings"], str(q))
    high = dict(tfr, areas=[dict(tfr["areas"][0], lower_m=300 * FT, lower_ref="AGL")])
    q = m.query(*inside, tfrs=[high])
    check("TFR with a 300 ft floor: ceiling = floor - 100 ft", abs(q["ceiling_amsl"] - (10 + 200 * FT)) < 0.2, str(q))

    import ceiling as gc_ceiling
    from airspace.ceiling import STADIUMS
    # stadium rule with the real Husky Stadium position on a map that covers it
    hs = STADIUMS["husky"]
    g2 = geo.Grid(hs[1] - 0.06, hs[2] - 0.08, hs[1] + 0.06, hs[2] + 0.08, 20.0)
    m2 = CeilingMap(g2, np.full(g2.shape, 20.0, dtype=np.float32), [], {"features": []}, log=lambda *a: None)
    ev = {"stadium": "husky", "start": now + 1800, "end": now + 3 * 3600}
    q = m2.query(*offset(hs[1], hs[2], 0, 4000), events=[ev])
    check("stadium event: NO-FLY from 1 h before, 4 km away", q["nofly"], str(q))
    q = m2.query(*offset(hs[1], hs[2], 0, 6000), events=[ev])
    check("stadium event: 6 km away is clear", not q["nofly"], str(q))

    # route check through the TFR
    class Air:
        def query(self, lat, lon):
            return m.query(lat, lon, tfrs=[tfr])

        def home_amsl(self, lat, lon, extra=0.0):
            return 10.0, "ground"
    pad = {"lat": far[0], "lon": far[1]}
    end = offset(s, w, 3000, 3000)
    route = {"takeoff_alt": 10, "waypoints": [{"lat": far[0], "lon": far[1] + 0.001, "alt": 30}],
             "final": {"lat": end[0], "lon": end[1], "alt": 5}}
    why = gc_ceiling.check_route(Air(), route, pad)
    check("route through an active TFR is refused", why is not None and "NO-FLY" in why, str(why))
    route_hi = dict(route, waypoints=[{"lat": far[0], "lon": far[1] + 0.001, "alt": 130}], final={"lat": far[0] - 0.001, "lon": far[1], "alt": 5})
    why = gc_ceiling.check_route(Air(), route_hi, pad)
    check("route above the ceiling is refused", why is not None and "above the legal ceiling" in why, str(why))
    route_ok = dict(route, final={"lat": far[0] - 0.001, "lon": far[1], "alt": 5})
    check("route under the ceiling is accepted", gc_ceiling.check_route(Air(), route_ok, pad) is None)

    # every cached TFR file parses
    xs = sorted(sources.CACHE.glob("tfr_*.xml"))
    bad = []
    for x in xs:
        try:
            d = sources.parse_tfr_xml(x.read_bytes(), x.stem)
            if any(len(a["ring"]) < 3 for a in d["areas"]):
                bad.append(x.name)
        except Exception as exc:
            bad.append(f"{x.name}: {exc}")
    check(f"all {len(xs)} cached TFR XML files parse", not bad, str(bad[:3]))

    # PNG writer
    png = geo.png_rgba(np.zeros((3, 4, 4), dtype=np.uint8))
    check("PNG writer", png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 40)
    print(f"\n{len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
