#!/usr/bin/env python3
"""Draw the FAA airspace around Seattle on a street map (one HTML file).

Layers:
- FAA UAS Facility Map cells: the altitude (ft AGL) up to which LAANC can give
  automatic approval. 0 = no automatic approval (further coordination).
- Class B shelves (floor/ceiling, ft MSL) and Class D surface areas.
- Packet takeoff points read from the flight logs.

Data: FAA ArcGIS services (services6.arcgis.com/ssFJjBXIUyZDrSYZ). The FAA says
these maps are for information only and are not an authorization.

  python3 tools/airspace_map.py --out ~/Downloads/"Seattle Airspace.html"
"""
import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services"
ENVELOPE = "-122.52,47.40,-122.08,47.86"   # greater Seattle (lon/lat)

# takeoff points from the dataflash logs (ORGN), not from satellite guesses
TAKEOFFS = [
    {"name": "Takeoff, logs 8-14", "lat": 47.662375, "lon": -122.29532},
    {"name": "Takeoff, log 16 (fence RTL)", "lat": 47.657895, "lon": -122.299404},
]


def query(service, fields):
    feats, offset = [], 0
    while True:
        qs = urllib.parse.urlencode({
            "geometry": ENVELOPE, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": fields, "outSR": 4326,
            "resultOffset": offset, "resultRecordCount": 2000, "f": "geojson"})
        req = urllib.request.Request(f"{BASE}/{service}/FeatureServer/0/query?{qs}",
                                     headers={"User-Agent": "packethw-airspace-map"})
        for attempt in range(4):
            with urllib.request.urlopen(req, timeout=90) as r:
                reply = json.load(r)
            if "features" in reply:
                break
            print(f"{service}: FAA service error {reply.get('error')}, retry {attempt + 1}")
            time.sleep(3 * (attempt + 1))
        else:
            raise SystemExit(f"{service}: no data from the FAA service")
        page = reply["features"]
        feats += page
        if len(page) < 2000:
            return feats
        offset += 2000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path.home() / "Downloads" / "Seattle Airspace.html"))
    a = ap.parse_args()

    cells = query("FAA_UAS_FacilityMap_Data", "CEILING,APT1_FAAID,APT1_NAME,AIRSPACE_1,MAP_EFF")
    classes = query("Class_Airspace", "NAME,CLASS,LOCAL_TYPE,LOWER_VAL,LOWER_CODE,UPPER_VAL,UPPER_CODE")
    classes = [f for f in classes if f["properties"]["CLASS"] in ("B", "D")]
    eff = sorted({f["properties"]["MAP_EFF"] for f in cells if f["properties"].get("MAP_EFF")})

    html = TEMPLATE.replace("/*CELLS*/null", json.dumps({"type": "FeatureCollection", "features": cells}))
    html = html.replace("/*CLASSES*/null", json.dumps({"type": "FeatureCollection", "features": classes}))
    html = html.replace("/*TAKEOFFS*/null", json.dumps(TAKEOFFS))
    html = html.replace("__EFF__", ", ".join(eff) or "unknown")
    Path(a.out).expanduser().write_text(html)
    print(f"{len(cells)} cells, {len(classes)} class B/D shapes -> {a.out}")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Seattle Drone Airspace</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>
:root{--ink:#14161a;--muted:#5b616b;--card:rgba(255,255,255,.94);--line:#e3e5e9;--b:#1f5fd6;--d:#1f5fd6}
html,body{margin:0;height:100%;background:#eef0f3;font-family:Inter,system-ui,sans-serif;color:var(--ink)}
#map{position:absolute;inset:0}
.card{position:absolute;z-index:1000;background:var(--card);border:1px solid var(--line);border-radius:12px;
  box-shadow:0 6px 24px rgba(20,22,26,.12);backdrop-filter:blur(6px)}
#title{top:16px;left:16px;padding:14px 18px;max-width:340px}
#title h1{font-size:17px;margin:0 0 4px;font-weight:700;letter-spacing:-.01em}
#title p{margin:0;font-size:12.5px;color:var(--muted);line-height:1.45}
#legend{bottom:24px;left:16px;padding:14px 16px;font-size:12.5px;width:250px}
#legend h2{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 8px}
.row{display:flex;align-items:center;gap:8px;margin:4px 0}
.sw{width:22px;height:14px;border-radius:3px;border:1px solid rgba(0,0,0,.15)}
.ln{width:22px;height:0;border-top:2.5px solid var(--b)}
.ln.d{border-top:2.5px dashed var(--d)}
.dot{width:12px;height:12px;border-radius:50%;background:#111;border:2.5px solid #ffd23f;margin:0 5px}
hr{border:0;border-top:1px solid var(--line);margin:10px 0}
.lbl{font:600 11px 'JetBrains Mono',monospace;color:#1f5fd6;background:rgba(255,255,255,.85);
  padding:1px 4px;border-radius:3px;border:1px solid rgba(31,95,214,.35);white-space:nowrap}
.lbl.d{color:#123a86}
.leaflet-popup-content{font-size:13px;line-height:1.5}
.big{font:700 20px 'JetBrains Mono',monospace}
@media (max-width:640px){#title{right:16px;max-width:none}#legend{width:auto;right:16px;bottom:16px}}
</style></head><body>
<div id="map"></div>
<div id="title" class="card"><h1>Seattle drone airspace</h1>
<p>FAA UAS Facility Map: the height (ft above ground) at which LAANC gives automatic approval. Click a cell for details. FAA map effective __EFF__. Information only, not an authorization.</p></div>
<div id="legend" class="card"><h2>LAANC auto-approval ceiling</h2><div id="ramp"></div><hr>
<div class="row"><span class="sw" style="background:transparent"></span>No cell: uncontrolled (Class G) to 400 ft</div><hr>
<div class="row"><span class="ln"></span>Class B shelf (floor / top, ft MSL)</div>
<div class="row"><span class="ln d"></span>Class D surface area</div>
<div class="row"><span class="dot"></span>Packet takeoff (from flight logs)</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const CELLS=/*CELLS*/null, CLASSES=/*CLASSES*/null, TAKEOFFS=/*TAKEOFFS*/null;
const STEPS=[[0,'#c81e3a','0 ft: further coordination only'],[50,'#ea5a2c',''],[100,'#f39233',''],[150,'#f6b73c',''],
  [200,'#e9d04a',''],[250,'#b9d65a',''],[300,'#7fc77a',''],[400,'#4caf8f','']];
const col=c=>{let k=STEPS[0][1];for(const s of STEPS)if(c>=s[0])k=s[1];return k};
document.getElementById('ramp').innerHTML=STEPS.map(s=>`<div class="row"><span class="sw" style="background:${s[1]};opacity:.8"></span>${s[2]||s[0]+' ft'}</div>`).join('');
const map=L.map('map',{zoomControl:false}).setView([47.62,-122.31],11);
L.control.zoom({position:'topright'}).addTo(map);
const ESRI='https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/';
L.tileLayer(ESRI+'World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:16,attribution:'Esri, HERE, Garmin, OpenStreetMap | FAA'}).addTo(map);
map.createPane('ref');map.getPane('ref').style.zIndex=450;map.getPane('ref').style.pointerEvents='none';
L.tileLayer(ESRI+'World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',{maxZoom:16,pane:'ref'}).addTo(map);
const cells=L.geoJSON(CELLS,{style:f=>({fillColor:col(f.properties.CEILING),fillOpacity:.5,color:'#ffffff',weight:.5,opacity:.7}),
  onEachFeature:(f,l)=>{const p=f.properties;l.bindPopup(`<div class="big">${p.CEILING} ft AGL</div>
   ${p.CEILING===0?'No automatic LAANC approval. Needs further coordination (manual ATC review).<br>':'LAANC can approve automatically up to this height.<br>'}
   Airport: <b>${p.APT1_NAME}</b> (${p.APT1_FAAID})<br>Airspace: Class ${p.AIRSPACE_1}`)}}).addTo(map);
const fmt=(v,c)=>c==='SFC'||v===0?'SFC':v>=100?String(Math.round(v/100)):v;
const shapes=L.layerGroup().addTo(map), labels=L.layerGroup().addTo(map);
for(const f of CLASSES.features){const p=f.properties, isD=p.CLASS==='D';
  const g=L.geoJSON(f,{style:{color:isD?'#1f5fd6':'#1f5fd6',weight:isD?2:2.2,dashArray:isD?'7 5':null,fill:false},interactive:false}).addTo(shapes);
  const c=g.getBounds().getCenter();
  const t=isD?`D ${fmt(p.UPPER_VAL)}`:`${fmt(p.UPPER_VAL)}/${fmt(p.LOWER_VAL,p.LOWER_CODE)}`;
  L.marker(c,{interactive:false,icon:L.divIcon({className:'',html:`<span class="lbl ${isD?'d':''}">${t}</span>`,iconSize:null})}).addTo(labels)}
for(const t of TAKEOFFS)L.circleMarker([t.lat,t.lon],{radius:7,color:'#ffd23f',weight:3,fillColor:'#111',fillOpacity:1}).bindTooltip(t.name).addTo(map);
L.control.layers(null,{'LAANC grid':cells,'Class B / D':shapes,'Labels':labels},{position:'topright',collapsed:false}).addTo(map);
map.fitBounds([[47.43,-122.43],[47.70,-122.17]],{paddingTopLeft:[280,10],paddingBottomRight:[10,10]});
map.on('zoomend',()=>{const z=map.getZoom();z<10?map.removeLayer(labels):map.addLayer(labels)});
</script></body></html>
"""

if __name__ == "__main__":
    main()
