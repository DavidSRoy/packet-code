// Mock drone + laptop uplink for the Packet telemetry API.
//
// Speaks the laptop side of the cloud contract: POSTs 1 Hz telemetry to
// /v1/drones/:id/telemetry, uploads routes once at startup, and executes the
// trip command the ingest reply carries (goto/hold/resume/return/flyto).
// Lets orders fly placed -> delivered with no hardware and no laptop.
//
//   node mock-drone.mjs            # needs wrangler dev on 127.0.0.1:8787
//
// Env: API (default http://127.0.0.1:8787), DRONE_ID (default mock-v0),
// INGEST_TOKEN (default dev-ingest-token). Ctrl-C stops it.
const API = process.env.API ?? "http://127.0.0.1:8787";
const ID = process.env.DRONE_ID ?? "mock-v0";
const INGEST = process.env.INGEST_TOKEN ?? "dev-ingest-token";
const TICK_MS = 1000;
const SPEED_MPS = 5;
const CRUISE_M = 10;

const PADS = {
  qfc: { name: "QFC", lat: 47.6625, lon: -122.2950 },
  uplace: { name: "UPLACE", lat: 47.6640, lon: -122.2990 },
};
const ROUTES = [
  { from: "qfc", to: "uplace", approved: true, path: [[47.6625, -122.2950], [47.6640, -122.2990]], length_m: 500, est_time_s: 120 },
  { from: "uplace", to: "qfc", approved: true, path: [[47.6640, -122.2990], [47.6625, -122.2950]], length_m: 500, est_time_s: 120 },
];

const drone = {
  lat: PADS.qfc.lat, lon: PADS.qfc.lon, height: 0,
  vn: 0, ve: 0, hdg: 0, mode: "IDLE", armed: false,
  batt: 95, pad: "qfc",
  mission: { state: "idle", from: null, to: null, item: 0, items: 1, reason: null, cmd_id: null },
  flyto: null,
  target: null,           // { lat, lon, then: "land" | "hover" | pad-id | "home" }
  holdPhase: null,        // mission state to resume after a hold
  uploadTicks: 0,
  acks: []
};

const M = 111320;
const distM = (a, b) => Math.hypot((a.lat - b.lat) * M, (a.lon - b.lon) * M * Math.cos(a.lat * Math.PI / 180));
const stepToward = (t) => {
  const d = distM(drone, t);
  if (d < 1) return true;
  const v = Math.min(SPEED_MPS, d), f = v / d;
  const dLat = (t.lat - drone.lat) * f, dLon = (t.lon - drone.lon) * f;
  drone.vn = dLat * M; drone.ve = dLon * M * Math.cos(drone.lat * Math.PI / 180);
  drone.hdg = (Math.atan2(drone.ve, drone.vn) * 180 / Math.PI + 360) % 360;
  drone.lat += dLat; drone.lon += dLon;
  return false;
};

function onCommand(cmd) {
  if (!cmd) return;
  const { id, action, pad, args } = cmd;
  const ack = (status, reason = null) => drone.acks.push({ id, status, reason });
  if (action === "goto" && drone.mission.state === "idle" && PADS[pad]) {
    drone.mission = { state: "uploading", from: drone.pad, to: pad, item: 0, items: 1, reason: null, cmd_id: id };
    drone.uploadTicks = 2;
    drone.armed = true;
  } else if (action === "hold" && drone.mission.state === "enroute") {
    drone.holdPhase = drone.mission.state;
    drone.mission.state = "holding";
    drone.vn = drone.ve = 0;
    ack("accepted");
  } else if (action === "resume" && drone.mission.state === "holding") {
    drone.mission.state = drone.holdPhase ?? "enroute";
    drone.holdPhase = null;
    ack("accepted");
  } else if (action === "return" && (drone.mission.state !== "idle" || drone.height > 0)) {
    drone.target = { ...PADS.qfc, then: "home" };
    drone.flyto = null;   // a return preempts any hover leg
    drone.mission = { ...drone.mission, state: "returning" };
    drone.vn = drone.ve = 0;
    ack("accepted");
  } else if (action === "flyto" && args && drone.mission.state === "idle" && !drone.flyto) {
    drone.target = { lat: args.lat, lon: args.lon, then: args.land === false ? "hover" : "land", alt: args.alt };
    drone.flyto = { cmd_id: id, state: "taking_off", reason: null, hold: 0 };
    drone.pad = null;
    drone.armed = true;
    ack("accepted");
  } else {
    ack("rejected", `mock cannot ${action} while ${drone.mission.state}`);
  }
}

function tick() {
  const m = drone.mission;
  if (m.state === "uploading") {
    drone.mode = "GUIDED";
    if (--drone.uploadTicks <= 0 && PADS[m.to]) {
      drone.target = { ...PADS[m.to], then: m.to };
      drone.pad = null;
      m.state = "enroute";
      m.item = 1;
    }
  } else if ((m.state === "enroute" || m.state === "returning") && drone.target) {
    drone.mode = "GUIDED";
    if (drone.height < CRUISE_M && distM(drone, drone.target) >= 3) {
      drone.height = Math.min(CRUISE_M, drone.height + 2);
      drone.vn = drone.ve = 0;
    } else if (stepToward(drone.target)) {
      drone.mode = "LAND";
      drone.height = Math.max(0, drone.height - 2);
      if (drone.height === 0) {
        const done = drone.target.then;
        drone.target = null;
        drone.vn = drone.ve = 0;
        if (done === "hover") {
          drone.height = CRUISE_M;
          drone.armed = true;
          drone.mode = "LOITER";
        } else {
          drone.armed = false;
          drone.mode = "IDLE";
          drone.pad = typeof done === "string" && PADS[done] ? done : (done === "home" ? "qfc" : drone.pad);
          if (!drone.pad) {
            // landed off the waypoint network: claim the pad if we are on one
            for (const [k, p] of Object.entries(PADS)) {
              if (distM(drone, p) < 5) { drone.pad = k; break; }
            }
          }
        }
        // hold "arrived" so the worker maps the trip to done before we clear it
        drone.mission = { state: "arrived", from: m.from, to: m.to, item: 1, items: 1,
          reason: null, cmd_id: m.cmd_id, hold: 5 };
      }
    }
  } else if (m.state === "arrived") {
    if (--m.hold <= 0) {
      drone.mission = { state: "idle", from: null, to: null, item: 0, items: 1, reason: null, cmd_id: null };
    }
  } else if (drone.flyto && drone.target) {
    drone.mode = "GUIDED";
    drone.flyto.state = "enroute";
    if (stepToward(drone.target)) {
      drone.mode = "LAND";
      drone.height = Math.max(0, drone.height - 2);
      if (drone.height === 0) {
        const done = drone.target.then;
        drone.target = null;
        drone.vn = drone.ve = 0;
        if (done === "hover") {
          drone.height = CRUISE_M;
          drone.mode = "LOITER";
        } else {
          drone.armed = false;
          drone.mode = "IDLE";
        }
        drone.flyto = { cmd_id: drone.flyto.cmd_id, state: "arrived", reason: null, hold: 5 };
      }
    }
  } else if (drone.flyto?.state === "arrived") {
    if (--drone.flyto.hold <= 0) drone.flyto = null;   // report arrived a few times, then clear
  } else if (m.state === "idle" || m.state === "holding") {
    drone.vn = drone.ve = 0;
  }
  drone.batt = Math.max(20, drone.batt - (drone.armed ? 0.02 : 0.001));
}

async function loop() {
  const body = {
    ts: Date.now(), link: true, lat: drone.lat, lon: drone.lon,
    alt_msl: 20 + drone.height, height: drone.height,
    vn: drone.vn, ve: drone.ve, hdg: drone.hdg,
    mode: drone.mode, armed: drone.armed,
    batt_pct: Math.round(drone.batt), batt_min: 8,
    gps_fix: 3, sats: 18, home_lat: PADS.qfc.lat, home_lon: PADS.qfc.lon,
    autonomy: {
      sa_on: true, pad: drone.pad,
      pads: Object.fromEntries(Object.entries(PADS).map(([k, p]) => [k, { name: p.name, lat: p.lat, lon: p.lon }])),
      can_goto: drone.pad ? ROUTES.filter((r) => r.from === drone.pad && r.approved).map((r) => r.to) : [],
      mission: drone.mission,
    },
    flyto: drone.flyto,
    acks: drone.acks,
  };
  drone.acks = [];
  const r = await fetch(`${API}/v1/drones/${ID}/telemetry`, {
    method: "POST",
    headers: { Authorization: `Bearer ${INGEST}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    console.log(`ingest ${r.status} (is wrangler dev up at ${API}?)`);
  } else {
    const reply = await r.json();
    if (reply.command) {
      console.log(`command: ${reply.command.action} ${reply.command.pad ?? ""}`.trim());
      onCommand(reply.command);
    }
  }
  tick();
}

async function main() {
  for (;;) {
    try {
      const r = await fetch(`${API}/v1/drones/${ID}/routes`, {
        method: "POST",
        headers: { Authorization: `Bearer ${INGEST}`, "Content-Type": "application/json" },
        body: JSON.stringify({ pads: PADS, routes: ROUTES, recording: null }),
      });
      console.log(`routes upload: ${r.status}`);
      if (r.ok) break;
    } catch {
      console.log(`waiting for worker at ${API}...`);
    }
    await new Promise((res) => setTimeout(res, 2000));
  }
  console.log(`mock ${ID} flying (1 Hz) -> ${API}. Ctrl-C to land it.`);
  for (;;) {
    try { await loop(); } catch (e) { console.log(`loop: ${e.message}`); }
    await new Promise((res) => setTimeout(res, TICK_MS));
  }
}

main();
