"""Download and cache the data for the ceiling map.

| Data | Source | Refresh |
|---|---|---|
| Ground height (bare earth, m, NAVD88) | USGS 3DEP ImageServer, exportImage | cached, kept |
| Building heights and outlines | OpenStreetMap (Overpass API) | 7 days |
| Class B/C/D/E2 airspace | FAA ADDS Class_Airspace FeatureServer | 1 day |
| LAANC grid (UAS Facility Maps) | FAA UAS FacilityMap FeatureServer | 1 day |
| TFRs | tfr.faa.gov (list JSON + one XML per NOTAM) | 5 min |

All network calls have timeouts and retries. When a download fails, the last
cached copy is used, and the caller sees its age.
"""
import datetime as dt
import math
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from .geo import FT, Grid

UA = {"User-Agent": "packethw-ceiling/1.0 (Packet drone ground control)"}
CACHE = Path(__file__).resolve().parent / "cache"
DEM_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
FAA = "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
TFR_LIST = "https://tfr.faa.gov/tfrapi/exportTfrList"
TFR_XML = "https://tfr.faa.gov/download/detail_{}.xml"

LEVEL_M = 2.5        # height per level when OSM has only building:levels (low on purpose: lower ceiling)


def _get(url, params=None, data=None, timeout=60, tries=3):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as exc:   # network, HTTP 5xx, timeouts
            err = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url[:80]}: {err}")


def _cache(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / name


def _age(path):
    return time.time() - path.stat().st_mtime if path.exists() else None


# ---------------------------------------------------------------- ground
def dem(grid: Grid, log=print):
    """Ground height (m) for each grid cell. Missing data is 0 (sea level): a lower
    ground gives a lower ceiling, so a gap is on the safe side."""
    path = _cache(f"dem_{grid.key()}.npy")
    if path.exists():
        return np.load(path)
    out = np.zeros(grid.shape, dtype=np.float32)
    T = 400
    tiles = [(r, c) for r in range(0, grid.rows, T) for c in range(0, grid.cols, T)]
    for i, (r0, c0) in enumerate(tiles):
        h, w = min(T, grid.rows - r0), min(T, grid.cols - c0)
        north = grid.n - r0 * grid.dlat
        south = north - h * grid.dlat
        west = grid.w + c0 * grid.dlon
        # The service keeps pixels square in degrees (it widens a bbox that is not),
        # so ask for square pixels of dlat and resample the columns to the grid.
        w2 = int(math.ceil(w * grid.dlon / grid.dlat)) + 1
        east = west + w2 * grid.dlat
        raw = _get(DEM_URL, {
            "bbox": f"{west},{south},{east},{north}", "bboxSR": 4326, "imageSR": 4326,
            "size": f"{w2},{h}", "format": "bsq", "pixelType": "F32",
            "interpolation": "RSP_BilinearInterpolation", "f": "image"}, timeout=120, tries=4)
        # bsq = w2*h float32 (row 0 north), then a 1-bit-per-pixel valid mask
        n_px = w2 * h
        vals = np.frombuffer(raw[:n_px * 4], dtype="<f4").reshape(h, w2)
        mask = np.unpackbits(np.frombuffer(raw[n_px * 4:n_px * 4 + (n_px + 7) // 8], dtype=np.uint8),
                             bitorder="big")[:n_px].reshape(h, w2).astype(bool)
        tile = np.where(mask & np.isfinite(vals) & (vals > -500), vals, 0.0)
        src_x = (np.arange(w2) + 0.5) * grid.dlat          # degrees east of west, pixel centres
        dst_x = (np.arange(w) + 0.5) * grid.dlon
        out[r0:r0 + h, c0:c0 + w] = np.stack([np.interp(dst_x, src_x, row) for row in tile])
        log(f"airspace: ground tile {i + 1}/{len(tiles)}")
    np.save(path, out)
    return out


# ---------------------------------------------------------------- buildings
def _height_m(tags):
    for key in ("height", "building:height"):
        v = tags.get(key)
        if v:
            s = v.strip().lower().replace(",", ".")
            m = re.match(r"([\d.]+)", s)
            if m:
                x = float(m.group(1))
                if "ft" in s or "'" in s:
                    x *= FT
                return x, "measured"
    v = tags.get("building:levels")
    if v:
        m = re.match(r"([\d.]+)", v.strip())
        if m:
            return float(m.group(1)) * LEVEL_M, "levels"
    return None, None


def buildings(grid: Grid, max_age_s=7 * 86400, log=print):
    """[{name, h, src, ring: [(lat, lon), ...]}] for buildings with a height or level count."""
    path = _cache(f"buildings_{grid.key()}.json")
    if _age(path) is None or _age(path) > max_age_s:
        q = (f"[out:json][timeout:180];(way[\"building\"][\"height\"]({grid.s},{grid.w},{grid.n},{grid.e});"
             f"way[\"building\"][\"building:levels\"]({grid.s},{grid.w},{grid.n},{grid.e}););out tags geom;")
        last = None
        for url in OVERPASS:
            try:
                raw = _get(url, data=urllib.parse.urlencode({"data": q}).encode(), timeout=200, tries=2)
                json.loads(raw)
                path.write_bytes(raw)
                log("airspace: building heights downloaded")
                break
            except Exception as exc:
                last = exc
        else:
            if not path.exists():
                raise RuntimeError(f"building data: {last}")
            log(f"airspace: building download failed, using the cache ({last})")
    out = []
    for e in json.loads(path.read_bytes())["elements"]:
        h, src = _height_m(e.get("tags", {}))
        geom = e.get("geometry")
        if h is None or h <= 0 or not geom:
            continue
        out.append({"name": e["tags"].get("name") or e["tags"].get("addr:street") or "building",
                    "h": h, "src": src, "ring": [(p["lat"], p["lon"]) for p in geom]})
    return out, _age(path)


# ---------------------------------------------------------------- FAA ArcGIS layers
def _faa_layer(service, fields, grid, name, max_age_s):
    path = _cache(f"{name}_{grid.key()}.geojson")
    if _age(path) is None or _age(path) > max_age_s:
        try:
            feats, offset = [], 0
            while True:
                raw = _get(f"{FAA}/{service}/FeatureServer/0/query", {
                    "geometry": f"{grid.w},{grid.s},{grid.e},{grid.n}", "geometryType": "esriGeometryEnvelope",
                    "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": fields, "outSR": 4326,
                    "resultOffset": offset, "resultRecordCount": 2000, "f": "geojson"}, timeout=90)
                page = json.loads(raw).get("features")
                if page is None:
                    raise RuntimeError(f"{service}: no features in the reply")
                feats += page
                if len(page) < 2000:
                    break
                offset += 2000
            path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        except Exception:
            if not path.exists():
                raise
    return json.loads(path.read_text()), _age(path)


def faa_classes(grid, max_age_s=86400):
    return _faa_layer("Class_Airspace",
                      "NAME,CLASS,LOCAL_TYPE,LOWER_VAL,LOWER_UOM,LOWER_CODE,UPPER_VAL,UPPER_UOM,UPPER_CODE",
                      grid, "class", max_age_s)


def faa_uasfm(grid, max_age_s=86400):
    return _faa_layer("FAA_UAS_FacilityMap_Data", "CEILING,UNIT,APT1_FAAID,APT1_NAME,AIRSPACE_1,MAP_EFF",
                      grid, "uasfm", max_age_s)


def rings(geometry):
    """Outer rings of a GeoJSON polygon / multipolygon as [(lat, lon), ...]."""
    if not geometry:
        return []
    polys = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return [[(y, x) for x, y in p[0]] for p in polys if p and p[0]]


# ---------------------------------------------------------------- TFRs
def _deg(s):
    m = re.match(r"([\d.]+)([NSEW])", s.strip())
    v = float(m.group(1))
    return -v if m.group(2) in "SW" else v


def _utc(s):
    if not s:
        return None
    return dt.datetime.fromisoformat(s.strip()).replace(tzinfo=dt.timezone.utc).timestamp()


def parse_tfr_xml(raw, notam_id):
    """One TFR XML (tfr.faa.gov/download/detail_*.xml) -> dict with areas."""
    root = ET.fromstring(raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw)
    t = lambda el, tag: (el.findtext(tag) or "").strip() if el is not None else ""
    grp_eff = _utc(t(root.find(".//Not"), "dateEffective"))
    grp_exp = _utc(t(root.find(".//Not"), "dateExpire"))
    areas = []
    for g in root.iter("TFRAreaGroup"):
        a = g.find("aseTFRArea")
        merged = g.find("abdMergedArea")
        if a is None or merged is None:
            continue
        ring = [(_deg(v.findtext("geoLat")), _deg(v.findtext("geoLong"))) for v in merged.findall("Avx")
                if v.findtext("geoLat") and v.findtext("geoLong")]
        if len(ring) < 3:
            continue

        def alt(which):
            val = t(a, f"valDistVer{which}")
            code = t(a, f"codeDistVer{which}")      # HEI = above ground, ALT = MSL, STD = flight level
            uom = t(a, f"uomDistVer{which}")
            if not val:
                return None, None
            v = float(val)
            if uom == "FL" or code == "STD":
                return v * 100 * FT, "MSL"
            return v * FT, ("AGL" if code == "HEI" else "MSL")

        lo, lo_ref = alt("Lower")
        hi, hi_ref = alt("Upper")
        sched = []
        for sg in a.findall("ScheduleGroup"):
            sched.append((_utc(t(sg, "dateEffective")) or grp_eff, _utc(t(sg, "dateExpire")) or grp_exp))
        if not sched:
            sched = [(grp_eff, grp_exp)]
        areas.append({"name": t(a, "txtName"), "ring": ring, "lower_m": lo or 0.0, "lower_ref": lo_ref or "AGL",
                      "upper_m": hi, "upper_ref": hi_ref, "schedule": sched})
    return {"id": notam_id, "areas": areas}


def tfrs(grid, max_age_s=300, log=print):
    """TFRs that touch the grid area. Returns (list, age_s)."""
    path = _cache("tfr_list.json")
    if _age(path) is None or _age(path) > max_age_s:
        try:
            path.write_bytes(_get(TFR_LIST, timeout=30, tries=2))
        except Exception as exc:
            if not path.exists():
                raise
            log(f"airspace: TFR list download failed, using the cache ({exc})")
    out = []
    for item in json.loads(path.read_bytes()):
        nid = item.get("notam_id", "")
        if not re.match(r"^\d+/\d+$", nid):
            continue
        xml_path = _cache(f"tfr_{nid.replace('/', '_')}.xml")
        if not xml_path.exists():
            try:
                xml_path.write_bytes(_get(TFR_XML.format(nid.replace("/", "_")), timeout=30, tries=2))
            except Exception as exc:
                log(f"airspace: TFR {nid} details not loaded ({exc})")
                continue
        try:
            d = parse_tfr_xml(xml_path.read_bytes(), nid)
        except Exception as exc:
            log(f"airspace: TFR {nid} not parsed ({exc})")
            continue
        d.update(type=item.get("type"), desc=item.get("description"), state=item.get("state"))
        d["areas"] = [a for a in d["areas"] if _touches_box(a["ring"], grid)]
        if d["areas"]:
            out.append(d)
    return out, _age(path)


def _touches_box(ring, grid, pad=0.05):
    lats = [p[0] for p in ring]
    lons = [p[1] for p in ring]
    return not (max(lats) < grid.s - pad or min(lats) > grid.n + pad or max(lons) < grid.w - pad or min(lons) > grid.e + pad)
