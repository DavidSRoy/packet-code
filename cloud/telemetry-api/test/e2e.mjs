// End-to-end test against a running `wrangler dev` (default http://127.0.0.1:8787).
// Uses the tokens from .dev.vars. Run: npm run dev  (in one terminal), then: npm test
const BASE = process.env.API ?? "http://127.0.0.1:8787";
const ING = { Authorization: "Bearer dev-ingest-token", "Content-Type": "application/json" };
const RD = { Authorization: "Bearer dev-read-token" };
const ID = `test-${Date.now() % 100000}`;
let fails = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "PASS" : "FAIL"} ${name} ${extra}`); if (!ok) fails++; };
const get = (p, h = RD) => fetch(BASE + p, { headers: h });
const post = (p, body, h = ING) => fetch(BASE + p, { method: "POST", headers: h, body: JSON.stringify(body) });
const sample = (i) => ({ ts: Date.now(), link: true, lat: 37.7749 + i * 1e-5, lon: -122.4194, alt_msl: 30, height: 1.0 + i,
  vn: 0.5, ve: 0, vd: -0.1, hdg: 317, roll: 0.5, pitch: -0.2, mode: "GUIDED", armed: true, batt_v: 24.6, batt_a: 18.2,
  gps_fix: 3, sats: 18, home_lat: 37.7749, home_lon: -122.4194 });

let r = await get("/v1/health", {});
check("health", r.ok);

r = await get(`/v1/drones/${ID}/position`, {});
check("read without token -> 401", r.status === 401);
r = await post(`/v1/drones/${ID}/telemetry`, sample(0), { ...ING, Authorization: "Bearer dev-read-token" });
check("ingest with read token -> 401", r.status === 401);
r = await post(`/v1/drones/${ID}/telemetry`, { ts: Date.now(), lat: 200, lon: 0 });
check("lat out of range -> 400", r.status === 400);
r = await post(`/v1/drones/${ID}/telemetry`, { lat: 1, lon: 1 });
check("missing ts -> 400", r.status === 400);
r = await get(`/v1/drones/BAD_ID/position`);
check("bad drone id -> 400", r.status === 400);

r = await get(`/v1/drones/${ID}/position`);
let j = await r.json();
check("no data yet -> offline, null position", r.ok && j.online === false && j.position === null);

// WebSocket stream: open it, then ingest, and wait for the update
const ws = new WebSocket(`${BASE.replace("http", "ws")}/v1/drones/${ID}/stream?token=dev-read-token`);
const got = [];
ws.onmessage = (e) => got.push(JSON.parse(e.data));
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

for (let i = 0; i < 3; i++) {
  r = await post(`/v1/drones/${ID}/telemetry`, sample(i));
  check(`ingest ${i}`, r.ok);
}
await new Promise((res) => setTimeout(res, 300));

r = await get(`/v1/drones/${ID}/position`);
j = await r.json();
check("position online", j.online === true, JSON.stringify(j.position));
check("position matches last sample", Math.abs(j.position.lat - (37.7749 + 2e-5)) < 1e-9 && j.position.height_m === 3);
check("velocity", j.velocity.ground_speed_ms === 0.5 && j.heading_deg === 317);

r = await get(`/v1/drones/${ID}/state`);
j = await r.json();
check("state fields", j.mode === "GUIDED" && j.armed === true && j.battery.cell_v === 4.1 && j.gps.satellites === 18);

r = await get(`/v1/drones/${ID}/track?limit=2`);
j = await r.json();
check("track limit=2 gives newest 2, oldest first", j.count === 2 && j.points[0].height_m === 2 && j.points[1].height_m === 3);

check("stream got initial + 3 updates", got.length >= 4 && got.at(-1).data.position.height_m === 3, `(${got.length} msgs)`);
ws.close();

const bad = new WebSocket(`${BASE.replace("http", "ws")}/v1/drones/${ID}/stream?token=wrong`);
const opened = await new Promise((res) => { bad.onopen = () => res(true); bad.onerror = () => res(false); });
check("stream bad token is refused", opened === false);

console.log(fails ? `${fails} FAILED` : "ALL PASS");
process.exit(fails ? 1 : 0);
