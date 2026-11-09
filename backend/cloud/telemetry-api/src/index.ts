/**
 * Packet telemetry API.
 *
 * The laptop ground control server POSTs drone telemetry about once a second.
 * The app team reads the latest position/state, the recent track, or a live
 * WebSocket stream. Each drone has its own Durable Object (SQLite storage).
 *
 *   POST /v1/drones/:id/telemetry   Bearer INGEST_TOKEN
 *   GET  /v1/drones/:id/position    Bearer READ_TOKEN
 *   GET  /v1/drones/:id/state       Bearer READ_TOKEN
 *   GET  /v1/drones/:id/track       Bearer READ_TOKEN   ?since=<ms or ISO>&limit=<n>
 *   GET  /v1/drones/:id/stream      WebSocket, ?token=READ_TOKEN
 *   GET  /v1/drones/:id/messages    Bearer READ_TOKEN   ?since=<ms or ISO>&limit=<n>  (FC text messages)
 *   POST /v1/drones/:id/snapshot    Bearer INGEST_TOKEN, image/webp|jpeg, X-Frame, X-Frame-Time (radio snapshot)
 *   GET  /v1/drones/:id/snapshot    Bearer READ_TOKEN or ?token=   the last radio snapshot
 *   POST /v1/drones/:id/routes      Bearer INGEST_TOKEN, JSON: pads, routes, recording
 *   GET  /v1/drones/:id/routes      Bearer READ_TOKEN
 *   POST /v1/drones/:id/airspace/layers   Bearer INGEST_TOKEN, JSON (the laptop's airspace map data)
 *   GET  /v1/drones/:id/airspace/layers   Bearer READ_TOKEN
 *   POST /v1/drones/:id/airspace/overlay  Bearer INGEST_TOKEN, image/png, X-Bounds
 *   GET  /v1/drones/:id/airspace/overlay.png  Bearer READ_TOKEN or ?token=
 *   POST /v1/drones/:id/camera      Bearer INGEST_TOKEN, H.264 frame records (best effort, see below)
 *   GET  /v1/drones/:id/camera.h264 Bearer READ_TOKEN or ?token=   H.264 Annex B from the last keyframe, 503 when not live
 *   GET  /v1/drones/:id/camera/stream  WebSocket, ?token=READ_TOKEN, one H.264 frame record per message
 *
 * H.264 frame record (the Pi's format, companion/h264.py), big-endian:
 *   4 B data length, 1 B flags (1 = keyframe, SPS and PPS in front), 8 B capture time
 *   (ms since epoch, float64), then one H.264 Annex B access unit.
 *   POST /v1/drones/:id/commands    Bearer COMMAND_TOKEN  {"action":"goto","pad":"qfc"} | hold | resume | return
 *                                   | {"action":"flyto","lat":..,"lon":..,"alt":..,"land":true,"speed":2}
 *   GET  /v1/drones/:id/commands    Bearer READ_TOKEN or COMMAND_TOKEN (last 20)
 *   GET  /v1/drones/:id/commands/:c Bearer READ_TOKEN or COMMAND_TOKEN
 *   POST /v1/orders                 Bearer READ_TOKEN, JSON: items, pickup, dropoff (pads)
 *   GET  /v1/orders                 Bearer READ_TOKEN   ?status=<state>&limit=<n>
 *   GET  /v1/orders/:id             Bearer READ_TOKEN
 *   PATCH /v1/orders/:id            Bearer READ_TOKEN, JSON: status and/or drone_id
 *   DELETE /v1/orders/:id           Bearer READ_TOKEN (terminal orders only)
 *   GET  /v1/health                 no auth
 *
 * Orders are global (one Durable Object for all orders), not per-drone. Status:
 * placed -> accepted -> picked_up -> loaded -> in_flight -> delivered, plus
 * failed / cancelled. Dispatch files the whole flight plan on accept and
 * releases it as a goto command on loaded; reads mirror the trip progress.
 *
 * Commands reach the drone through the laptop: the reply to each telemetry
 * POST carries the next queued command. The laptop answers in a later POST
 * (acks), and the trip progress comes in the "autonomy" block.
 *
 * Reliability: the telemetry (everything in /state, /track, /messages) comes
 * over the telemetry radio and is meant to be reliable. The camera is BEST
 * EFFORT: the laptop forwards it only while it reaches the Pi over Wi-Fi, so
 * it drops out often (range, Wi-Fi, laptop upload). Nothing may depend on it.
 * The box pose (box_camera) is telemetry: it also comes over the radio.
 */
import { DurableObject } from "cloudflare:workers";

export interface Env {
  DRONE: DurableObjectNamespace<DroneState>;
  ORDERS: DurableObjectNamespace<Orders>;
  INGEST_TOKEN: string;
  READ_TOKEN: string;
  COMMAND_TOKEN: string;
}

const COMMAND_EXPIRE_MS = 15_000;      // a command the laptop did not pick up in this time expires
const ACTIONS = ["goto", "hold", "resume", "return", "flyto"] as const;
type Action = typeof ACTIONS[number];

/** Pad-to-pad autonomy block from the laptop. */
export interface Autonomy {
  sa_on: boolean;
  pad: string | null;
  pads: Record<string, { name: string; lat: number; lon: number }>;
  can_goto: string[];
  mission: { state: string; from: string | null; to: string | null; item: number; items: number;
             reason: string | null; cmd_id: string | null };
}

interface Ack { id: string; status: "accepted" | "rejected"; reason: string | null }

const CAMERA_LIVE_S = 5;               // a frame older than this = camera not live
const CAMERA_MAX_BYTES = 1_000_000;    // one POST
const GOP_MAX_BYTES = 4_000_000;       // kept from the last keyframe
const REC_HDR = 13;

/** Split H.264 frame records. Returns null when the body is not a clean list of records. */
export function splitRecords(buf: ArrayBuffer): { off: number; len: number; key: boolean; t: number }[] | null {
  const dv = new DataView(buf), out = [];
  let o = 0;
  while (o < buf.byteLength) {
    if (buf.byteLength - o < REC_HDR) return null;
    const len = dv.getUint32(o), key = (dv.getUint8(o + 4) & 1) === 1, t = dv.getFloat64(o + 5);
    if (len === 0 || o + REC_HDR + len > buf.byteLength) return null;
    out.push({ off: o, len, key, t });
    o += REC_HDR + len;
  }
  return out.length ? out : null;
}
const BLOB_CHUNK = 1_000_000;          // bytes per SQLite row for files from the laptop
const FILE_MAX_BYTES = 25_000_000;     // one file upload (airspace map, routes, snapshot)
type BlobRow = { name: string; type: string; bytes: number; updated_at: number; meta: string | null };
const ONLINE_S = 5;                    // no update for this long = offline
const TRACK_KEEP_MS = 24 * 3600_000;   // keep 24 h of track
const DRONE_ID = /^[a-z0-9-]{1,32}$/;

/** What the laptop sends. Every field is optional except ts. */
export interface Telemetry {
  ts: number;                 // laptop time, ms since epoch
  link?: boolean;             // laptop has a heartbeat from the drone
  lat?: number | null; lon?: number | null;
  alt_msl?: number | null;    // m
  height?: number | null;     // m above home
  vn?: number; ve?: number; vd?: number;  // m/s, NED
  hdg?: number | null;        // deg, GPS course
  roll?: number; pitch?: number;          // deg
  yaw?: number | null;        // deg, nose direction (compass)
  mode?: string; armed?: boolean;
  batt_v?: number | null; batt_a?: number | null;
  batt_pct?: number | null;   // % charge left, from the Pixhawk (mAh used vs BATT_CAPACITY)
  batt_mah?: number | null;   // mAh used since power-up
  batt_min?: number | null;   // estimated flight minutes left to the 20% reserve
  batt_min_basis?: string | null;   // "flight", "last flight" or "hover estimate"
  batt_cap?: number | null;   // mAh, BATT_CAPACITY
  rc_ok?: boolean | null; rssi?: number | null;   // pilot radio
  sd_stop?: boolean | null;   // SD kill switch on
  sa_on?: boolean | null;     // SA switch: backend control allowed
  fence_on?: boolean | null; fence_r?: number | null;
  // GPS quality (ground_control/gps_guard.py). lat/lon are filtered for display;
  // lat_fc/lon_fc are the FC's own position.
  lat_fc?: number | null; lon_fc?: number | null;
  gps_q?: "good" | "poor" | "bad" | null; gps_why?: string[];
  gps_hdop?: number | null; gps_hacc?: number | null; pos_filtered?: boolean;
  box_camera?: BoxCamera | null;
  camera_live?: boolean;      // the laptop forwards camera frames now
  radio_snapshot?: Record<string, unknown> | null;   // box camera pictures over the telemetry radio: link status
  lights?: { mode: string; sb_pwm: number | null } | null;   // arm lights (lua/lights.lua)
  ceiling?: Record<string, unknown> | null;          // legal ceiling / no-fly guard (ground_control/ceiling.py)
  laptop?: Record<string, unknown> | null;           // laptop side: takeoff, speed limits, camera forwarding, log
  recording?: Record<string, unknown> | null;        // route recording in progress
  pos_rejected?: number | null;                      // GPS jumps the laptop filter threw away
  flyto?: Record<string, unknown> | null;            // fly to a point (ground_control/flyto.py)
  messages?: FcMessage[];
  gps_fix?: number; sats?: number;
  home_lat?: number | null; home_lon?: number | null;
  autonomy?: Autonomy | null;
  acks?: Ack[];
}

interface Stored { t: Telemetry; received_at: number }

/** Lid pose from the Pi's box camera (lid frame: x long side, y short side, z up, m).
 *  rvec/tvec: the lid -> camera pose (OpenCV Rodrigues vector; lid origin in the camera frame, m). */
export interface Box {
  id: number; tags: string[] | null; ntags: number; px_per_cell: number | null;
  drone_m: number[]; camera_m: (number | null)[]; yaw_deg: number; tilt_deg: number;
  range_m: number | null; rvec: (number | null)[] | null; tvec: (number | null)[] | null;
  outlines: unknown;          // tag outlines in the picture, px (Wi-Fi only)
}
export interface BoxCamera {
  source: "wifi" | "radio";
  age_s: number | null;
  detection_hz: number | null;
  camera: Record<string, unknown> | null;   // name, hfov_deg, width, height, frames, mount (Wi-Fi only)
  box: Box | null;            // the first box in view (same as boxes[0])
  boxes: Box[];               // every box in view (the radio sends one)
}
export interface FcMessage { ts: number; sev: number; text: string }

const NUM_FIELDS = ["ts", "lat", "lon", "alt_msl", "height", "vn", "ve", "vd", "hdg", "roll", "pitch",
  "batt_v", "batt_a", "batt_pct", "batt_mah", "batt_min", "gps_fix", "sats", "home_lat", "home_lon",
  "yaw", "batt_cap", "rssi", "fence_r", "lat_fc", "lon_fc", "gps_hdop", "gps_hacc"] as const;
const BOOL_FIELDS = ["rc_ok", "sd_stop", "sa_on", "fence_on"] as const;

function cleanTelemetry(body: unknown): Telemetry | string {
  if (!body || typeof body !== "object") return "body must be a JSON object";
  const b = body as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const k of NUM_FIELDS) {
    const v = b[k];
    if (v === undefined || v === null) { out[k] = null; continue; }
    if (typeof v !== "number" || !Number.isFinite(v)) return `${k} must be a finite number`;
    out[k] = v;
  }
  if (typeof out.ts !== "number") return "ts is required";
  const lat = out.lat as number | null, lon = out.lon as number | null;
  if ((lat == null) !== (lon == null)) return "send lat and lon together";
  if (lat != null && lon != null && (Math.abs(lat) > 90 || Math.abs(lon) > 180)) return "lat/lon out of range";
  if (b.mode !== undefined && typeof b.mode !== "string") return "mode must be a string";
  out.mode = typeof b.mode === "string" ? b.mode.slice(0, 24) : null;
  out.armed = b.armed === true;
  out.link = b.link !== false;
  for (const k of BOOL_FIELDS) out[k] = typeof b[k] === "boolean" ? b[k] : null;
  out.batt_min_basis = str(b.batt_min_basis, 24);
  out.gps_q = b.gps_q === "good" || b.gps_q === "poor" || b.gps_q === "bad" ? b.gps_q : null;
  out.gps_why = Array.isArray(b.gps_why) ? b.gps_why.filter(x => typeof x === "string").slice(0, 10).map(x => (x as string).slice(0, 40)) : [];
  out.pos_filtered = b.pos_filtered === true;
  out.camera_live = b.camera_live === true;
  out.box_camera = cleanBox(b.box_camera);
  out.radio_snapshot = obj(b.radio_snapshot, 4_096);
  const li = b.lights as Record<string, unknown> | null;
  out.lights = li && typeof li === "object" && typeof li.mode === "string" ? { mode: li.mode.slice(0, 16), sb_pwm: num(li.sb_pwm) } : null;
  out.ceiling = obj(b.ceiling, 32_768);
  out.laptop = obj(b.laptop, 4_096);
  out.recording = obj(b.recording, 2_048);
  out.pos_rejected = num(b.pos_rejected);
  out.flyto = obj(b.flyto, 4_096);
  out.messages = Array.isArray(b.messages)
    ? b.messages.filter((m): m is FcMessage => !!m && typeof m === "object" && typeof (m as FcMessage).ts === "number"
                                               && typeof (m as FcMessage).text === "string")
        .slice(-20).map(m => ({ ts: m.ts, sev: typeof m.sev === "number" ? m.sev : 6, text: m.text.slice(0, 200) }))
    : [];
  out.autonomy = cleanAutonomy(b.autonomy);
  out.acks = Array.isArray(b.acks)
    ? b.acks.filter((a): a is Ack => !!a && typeof a === "object" && typeof (a as Ack).id === "string")
        .slice(0, 10).map(a => ({ id: a.id.slice(0, 40), status: a.status === "accepted" ? "accepted" : "rejected",
                                 reason: typeof a.reason === "string" ? a.reason.slice(0, 200) : null }))
    : [];
  return out as unknown as Telemetry;
}

const str = (v: unknown, n = 64) => (typeof v === "string" ? v.slice(0, n) : null);
const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const nums = (v: unknown, n: number) => (Array.isArray(v) ? v.slice(0, n).map(num) : Array(n).fill(null));

/** A JSON object from the laptop, kept as it is when its JSON is at most maxBytes. */
function obj(v: unknown, maxBytes = 16_384): Record<string, unknown> | null {
  if (!v || typeof v !== "object" || Array.isArray(v)) return null;
  const s = JSON.stringify(v);
  return s.length <= maxBytes ? (JSON.parse(s) as Record<string, unknown>) : null;
}

function cleanOneBox(v: unknown): Box | null {
  const b = v as Record<string, unknown> | null;
  if (!b || typeof b !== "object" || num(b.id) == null) return null;
  const outlines = b.outlines != null && JSON.stringify(b.outlines).length <= 8_192 ? b.outlines : null;
  return {
    id: b.id as number,
    tags: Array.isArray(b.tags) ? b.tags.filter(x => typeof x === "string").slice(0, 20) as string[] : null,
    ntags: num(b.ntags) ?? 0, px_per_cell: num(b.px_per_cell),
    drone_m: nums(b.drone_m, 3) as number[], camera_m: nums(b.camera_m, 3),
    yaw_deg: num(b.yaw_deg) ?? 0, tilt_deg: num(b.tilt_deg) ?? 0,
    range_m: num(b.range_m),
    rvec: Array.isArray(b.rvec) ? nums(b.rvec, 3) : null,
    tvec: Array.isArray(b.tvec) ? nums(b.tvec, 3) : null,
    outlines,
  };
}

function cleanBox(v: unknown): BoxCamera | null {
  if (!v || typeof v !== "object") return null;
  const c = v as Record<string, unknown>;
  const list = Array.isArray(c.boxes) && c.boxes.length ? c.boxes : [c.box];
  const boxes = list.slice(0, 8).map(cleanOneBox).filter((b): b is Box => b != null);
  return {
    source: c.source === "wifi" ? "wifi" : "radio",
    age_s: num(c.age_s),
    detection_hz: num(c.detection_hz),
    camera: obj(c.camera, 4_096),
    box: cleanOneBox(c.box) ?? boxes[0] ?? null,
    boxes,
  };
}
const PAD_ID = /^[a-z0-9-]{1,32}$/;

function cleanAutonomy(v: unknown): Autonomy | null {
  if (!v || typeof v !== "object") return null;
  const a = v as Record<string, unknown>;
  const pads: Autonomy["pads"] = {};
  if (a.pads && typeof a.pads === "object") {
    for (const [k, p] of Object.entries(a.pads as Record<string, Record<string, unknown>>).slice(0, 20)) {
      if (PAD_ID.test(k) && p && typeof p.lat === "number" && typeof p.lon === "number")
        pads[k] = { name: str(p.name, 40) ?? k, lat: p.lat, lon: p.lon };
    }
  }
  const m = (a.mission && typeof a.mission === "object" ? a.mission : {}) as Record<string, unknown>;
  return {
    sa_on: a.sa_on === true,
    pad: str(a.pad, 32),
    pads,
    can_goto: Array.isArray(a.can_goto) ? a.can_goto.filter(x => typeof x === "string").slice(0, 20) as string[] : [],
    mission: {
      state: str(m.state, 24) ?? "idle", from: str(m.from, 32), to: str(m.to, 32),
      item: typeof m.item === "number" ? m.item : 0, items: typeof m.items === "number" ? m.items : 0,
      reason: str(m.reason, 200), cmd_id: str(m.cmd_id, 40),
    },
  };
}

const r1 = (v: number | null | undefined, d = 1) => (v == null ? null : Math.round(v * 10 ** d) / 10 ** d);

/** The public shapes the app team gets. */
function toPosition(id: string, s: Stored | null, now: number) {
  if (!s) return { drone_id: id, online: false, updated_at: null, age_s: null, position: null };
  const t = s.t;
  const age = (now - s.received_at) / 1000;
  const hasFix = t.lat != null && t.lon != null && !(t.lat === 0 && t.lon === 0);
  return {
    drone_id: id,
    online: age < ONLINE_S && t.link !== false,
    updated_at: new Date(s.received_at).toISOString(),
    age_s: r1(age),
    position: hasFix ? { lat: t.lat, lon: t.lon, alt_msl_m: r1(t.alt_msl), height_m: r1(t.height) } : null,
    velocity: {
      north_ms: r1(t.vn ?? 0, 2), east_ms: r1(t.ve ?? 0, 2), down_ms: r1(t.vd ?? 0, 2),
      ground_speed_ms: r1(Math.hypot(t.vn ?? 0, t.ve ?? 0), 2),
    },
    heading_deg: r1(t.hdg),
    home: t.home_lat != null && t.home_lon != null ? { lat: t.home_lat, lon: t.home_lon } : null,
  };
}

function toState(id: string, s: Stored | null, now: number) {
  const p = toPosition(id, s, now);
  if (!s) return p;
  const t = s.t;
  return {
    ...p,
    mode: t.mode,
    armed: t.armed,
    attitude: { roll_deg: r1(t.roll), pitch_deg: r1(t.pitch), yaw_deg: r1(t.yaw) },
    battery: {
      percent: t.batt_pct ?? null,
      voltage_v: r1(t.batt_v, 2), current_a: r1(t.batt_a), cell_v: t.batt_v == null ? null : r1(t.batt_v / 6, 2),
      used_mah: t.batt_mah ?? null,
      time_left_min: r1(t.batt_min),
      time_left_basis: t.batt_min_basis ?? null,
      capacity_mah: t.batt_cap ?? null,
    },
    gps: { fix_type: t.gps_fix, satellites: t.sats,
           quality: t.gps_q ?? null, reasons: t.gps_why ?? [], hdop: r1(t.gps_hdop, 2), accuracy_m: r1(t.gps_hacc),
           position_filtered: t.pos_filtered === true, positions_rejected: t.pos_rejected ?? null,
           fc_position: t.lat_fc != null && t.lon_fc != null ? { lat: t.lat_fc, lon: t.lon_fc } : null },
    pilot_radio: { link_ok: t.rc_ok ?? null, rssi: t.rssi ?? null,
                   kill_switch_on: t.sd_stop ?? null, backend_switch_on: t.sa_on ?? null },
    fence: { enabled: t.fence_on ?? null, radius_m: t.fence_r ?? null },
    box_camera: t.box_camera ?? null,
    lights: t.lights ?? null,
    ceiling: t.ceiling ?? null,
    laptop: t.laptop ?? null,
    flyto: t.flyto ?? null,
    autonomy: toAutonomy(t.autonomy, t.recording),
  };
}

/** Camera status. Best effort: it is often down, and nothing may depend on it. */
function toCamera(id: string, frameAt: number | null, laptopLive: boolean, now: number) {
  const age = frameAt == null ? null : (now - frameAt) / 1000;
  return {
    best_effort: true,
    live: age != null && age < CAMERA_LIVE_S,
    laptop_forwarding: laptopLive,
    last_frame_at: frameAt == null ? null : new Date(frameAt).toISOString(),
    frame_age_s: r1(age),
    format: "H.264 (Annex B), 1280x720, about 10 fps",
    frame_url: `/v1/drones/${id}/camera.h264`,
    stream_url: `/v1/drones/${id}/camera/stream`,
    note: "Best effort: frames come only while the laptop reaches the drone's Pi over Wi-Fi. Expect gaps. Use box_camera (radio) for the box pose.",
  };
}

function toAutonomy(a: Autonomy | null | undefined, recording: Record<string, unknown> | null | undefined) {
  if (!a) return null;
  const m = a.mission;
  return {
    backend_control_allowed: a.sa_on,       // SA switch on the pilot's radio
    current_pad: a.pad,                      // null when flying or not on a known pad
    pads: a.pads,
    can_goto: a.can_goto,                    // pads with an approved route from the current pad
    recording: recording ?? null,            // route recording in progress (full routes: GET /routes)
    trip: {
      state: m.state, from: m.from, to: m.to,
      progress: m.items ? Math.round((Math.min(m.item, m.items) / m.items) * 100) : 0,
      reason: m.reason, command_id: m.cmd_id,
    },
  };
}

/** Command status from the fly-to state the laptop reports. */
function flytoStatus(state: string): string | null {
  switch (state) {
    case "starting": case "taking_off": case "enroute": case "landing": return "in_progress";
    case "arrived": return "done";
    case "failed": return "failed";
    case "stopped": return "stopped_by_pilot";
    default: return null;
  }
}

/** Command status from the trip state the laptop reports. */
function tripStatus(state: string): string | null {
  switch (state) {
    case "starting": case "uploading": case "enroute": case "landing": return "in_progress";
    case "holding": return "holding";
    case "returning": return "returning";
    case "arrived": return "done";
    case "failed": return "failed";
    case "pilot": return "stopped_by_pilot";
    default: return null;
  }
}

type CommandRow = {
  id: string; action: string; pad: string | null; status: string; reason: string | null;
  created_at: number; updated_at: number; args?: string | null;
};
export interface FlytoArgs { lat: number; lon: number; alt: number; land: boolean; speed: number | null }
function commandOut(c: CommandRow) {
  return { id: c.id, action: c.action, pad: c.pad, args: c.args ? JSON.parse(c.args) : null, status: c.status, reason: c.reason,
           created_at: new Date(c.created_at).toISOString(), updated_at: new Date(c.updated_at).toISOString() };
}

export class DroneState extends DurableObject<Env> {
  private latest: Stored | null = null;
  private inserts = 0;
  private gop: ArrayBuffer[] = [];            // frame records from the last keyframe, memory only (best effort)
  private gopBytes = 0;
  private frameAt: number | null = null;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(async () => {
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS latest (k INTEGER PRIMARY KEY CHECK (k = 1), json TEXT NOT NULL)`);
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS track (
        received_at INTEGER PRIMARY KEY, lat REAL, lon REAL, alt_msl REAL, height REAL,
        vn REAL, ve REAL, vd REAL, hdg REAL, mode TEXT, armed INTEGER, batt_v REAL)`);
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS messages (
        ts INTEGER NOT NULL, sev INTEGER NOT NULL, text TEXT NOT NULL, PRIMARY KEY (ts, text))`);
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS commands (
        id TEXT PRIMARY KEY, action TEXT NOT NULL, pad TEXT, status TEXT NOT NULL, reason TEXT,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)`);
      try { ctx.storage.sql.exec("ALTER TABLE commands ADD COLUMN args TEXT"); } catch { /* already there */ }
      // Files from the laptop (radio snapshot, routes, airspace map): the latest of each, in chunks
      // (a SQLite value is at most 2 MB).
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS blob_chunks (
        name TEXT NOT NULL, idx INTEGER NOT NULL, data BLOB NOT NULL, PRIMARY KEY (name, idx))`);
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS blobs (
        name TEXT PRIMARY KEY, type TEXT NOT NULL, bytes INTEGER NOT NULL, updated_at INTEGER NOT NULL, meta TEXT)`);
      const row = ctx.storage.sql.exec<{ json: string }>("SELECT json FROM latest WHERE k = 1").toArray()[0];
      this.latest = row ? (JSON.parse(row.json) as Stored) : null;
      for (const b of ctx.storage.sql.exec<BlobRow>("SELECT * FROM blobs").toArray()) this.blobInfo.set(b.name, b);
    });
  }

  /* ---- files from the laptop ---- */
  private blobInfo = new Map<string, BlobRow>();

  async putBlob(name: string, data: ArrayBuffer, type: string, meta: Record<string, unknown> = {}) {
    const sql = this.ctx.storage.sql, now = Date.now();
    this.ctx.storage.transactionSync(() => {
      sql.exec("DELETE FROM blob_chunks WHERE name = ?", name);
      for (let i = 0, o = 0; o < data.byteLength; i++, o += BLOB_CHUNK)
        sql.exec("INSERT INTO blob_chunks VALUES (?,?,?)", name, i, data.slice(o, o + BLOB_CHUNK));
      sql.exec("INSERT OR REPLACE INTO blobs VALUES (?,?,?,?,?)", name, type, data.byteLength, now, JSON.stringify(meta));
    });
    this.blobInfo.set(name, { name, type, bytes: data.byteLength, updated_at: now, meta: JSON.stringify(meta) });
    if (name === "snapshot") {    // tell stream clients a new picture is there (they fetch GET /snapshot)
      const msg = JSON.stringify({ type: "snapshot", data: this.snapshotInfo(this.droneId ?? "") });
      for (const ws of this.ctx.getWebSockets("state")) { try { ws.send(msg); } catch { /* closing */ } }
    }
  }

  async getBlob(name: string): Promise<{ data: Uint8Array; info: BlobRow } | null> {
    const info = this.blobInfo.get(name);
    if (!info) return null;
    const out = new Uint8Array(info.bytes);
    let o = 0;
    for (const c of this.ctx.storage.sql.exec<{ data: ArrayBuffer }>(
      "SELECT data FROM blob_chunks WHERE name = ? ORDER BY idx", name)) {
      out.set(new Uint8Array(c.data), o); o += c.data.byteLength;
    }
    return { data: out, info };
  }

  private droneId: string | null = null;

  /** The last box camera picture that came over the telemetry radio, plus the radio link status. */
  private snapshotInfo(id: string) {
    const b = this.blobInfo.get("snapshot");
    const meta = b?.meta ? (JSON.parse(b.meta) as Record<string, unknown>) : {};
    const captured = num(meta.captured_at);
    return {
      available: !!b,
      frame: num(meta.frame),
      captured_at: captured == null ? null : new Date(captured).toISOString(),
      uploaded_at: b ? new Date(b.updated_at).toISOString() : null,
      age_s: b ? r1((Date.now() - (captured ?? b.updated_at)) / 1000) : null,
      bytes: b?.bytes ?? null, content_type: b?.type ?? null,
      url: `/v1/drones/${id}/snapshot`,
      radio: this.latest?.t.radio_snapshot ?? null,     // link status: state, rate, loss, frame being received
      note: "About 320x180, sent over the telemetry radio when the Pi is not on Wi-Fi (a few seconds per picture).",
    };
  }

  private setStatus(cid: string, status: string, reason: string | null, now: number) {
    this.ctx.storage.sql.exec("UPDATE commands SET status = ?, reason = ?, updated_at = ? WHERE id = ?",
      status, reason, now, cid);
  }

  /** Commands: apply the laptop's acks and trip state; return the next queued command, if any. */
  private exchange(t: Telemetry, now: number): { id: string; action: string; pad: string | null; args: unknown } | null {
    const sql = this.ctx.storage.sql;
    for (const a of t.acks ?? []) this.setStatus(a.id, a.status, a.reason, now);
    const m = t.autonomy?.mission;
    if (m?.cmd_id) {
      const st = tripStatus(m.state);
      const row = sql.exec<CommandRow>("SELECT * FROM commands WHERE id = ?", m.cmd_id).toArray()[0];
      if (st && row && row.status !== st && !["rejected", "superseded", "expired"].includes(row.status))
        this.setStatus(m.cmd_id, st, m.reason, now);
    }
    const f = t.flyto as { cmd_id?: unknown; state?: unknown; reason?: unknown } | null | undefined;
    if (f && typeof f.cmd_id === "string" && typeof f.state === "string") {
      const st = flytoStatus(f.state);
      const row = sql.exec<CommandRow>("SELECT * FROM commands WHERE id = ?", f.cmd_id).toArray()[0];
      if (st && row && row.status !== st && !["rejected", "superseded", "expired"].includes(row.status))
        this.setStatus(f.cmd_id, st, typeof f.reason === "string" ? f.reason.slice(0, 200) : null, now);
    }
    sql.exec("UPDATE commands SET status = 'expired', reason = 'the laptop did not pick it up', updated_at = ? " +
             "WHERE status = 'queued' AND created_at < ?", now, now - COMMAND_EXPIRE_MS);
    const next = sql.exec<CommandRow>("SELECT * FROM commands WHERE status = 'queued' ORDER BY created_at LIMIT 1").toArray()[0];
    if (!next) return null;
    this.setStatus(next.id, "delivered", null, now);
    return { id: next.id, action: next.action, pad: next.pad, args: next.args ? JSON.parse(next.args) : null };
  }

  async command(id: string, action: Action, pad: string | null, args: FlytoArgs | null = null) {
    const now = Date.now();
    const s = this.latest;
    if (!s || now - s.received_at > ONLINE_S * 1000 || s.t.link === false)
      return { error: "drone offline: no data from the laptop, or the laptop has no link to the drone", status: 409 };
    const sql = this.ctx.storage.sql;
    // a newer command replaces one the laptop has not picked up yet
    sql.exec("UPDATE commands SET status = 'superseded', updated_at = ? WHERE status = 'queued'", now);
    const cid = `cmd_${now.toString(36)}${crypto.randomUUID().slice(0, 6)}`;
    sql.exec("INSERT INTO commands (id, action, pad, status, reason, created_at, updated_at, args) VALUES (?,?,?,?,?,?,?,?)",
      cid, action, pad, "queued", null, now, now, args ? JSON.stringify(args) : null);
    sql.exec("DELETE FROM commands WHERE created_at < ?", now - TRACK_KEEP_MS);
    return { command: commandOut(sql.exec<CommandRow>("SELECT * FROM commands WHERE id = ?", cid).one()) };
  }

  async getCommand(cid: string) {
    const row = this.ctx.storage.sql.exec<CommandRow>("SELECT * FROM commands WHERE id = ?", cid).toArray()[0];
    return row ? commandOut(row) : null;
  }

  async listCommands() {
    return this.ctx.storage.sql.exec<CommandRow>("SELECT * FROM commands ORDER BY created_at DESC LIMIT 20")
      .toArray().map(commandOut);
  }

  async ingest(id: string, t: Telemetry): Promise<{ id: string; action: string; pad: string | null; args: unknown } | null> {
    const now = Date.now();
    const next = this.exchange(t, now);
    delete t.acks;
    const sql0 = this.ctx.storage.sql;
    for (const m of t.messages ?? []) sql0.exec("INSERT OR IGNORE INTO messages VALUES (?,?,?)", m.ts, m.sev, m.text);
    if ((t.messages ?? []).length) sql0.exec("DELETE FROM messages WHERE ts < ?", now - TRACK_KEEP_MS);
    delete t.messages;
    const s: Stored = { t, received_at: now };
    const sql = this.ctx.storage.sql;
    // persist first, then cache
    sql.exec("INSERT OR REPLACE INTO latest (k, json) VALUES (1, ?)", JSON.stringify(s));
    if (t.lat != null && t.lon != null && !(t.lat === 0 && t.lon === 0)) {
      sql.exec(`INSERT OR REPLACE INTO track VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`,
        now, t.lat, t.lon, t.alt_msl ?? null, t.height ?? null, t.vn ?? null, t.ve ?? null, t.vd ?? null,
        t.hdg ?? null, t.mode ?? null, t.armed ? 1 : 0, t.batt_v ?? null);
      if (++this.inserts % 60 === 0) sql.exec("DELETE FROM track WHERE received_at < ?", now - TRACK_KEEP_MS);
    }
    this.latest = s;
    const msg = JSON.stringify({ type: "state", data: this.stateOf(id, now) });
    for (const ws of this.ctx.getWebSockets("state")) {
      try { ws.send(msg); } catch { /* socket closing */ }
    }
    return next;
  }

  private recentMessages(n: number) {
    return this.ctx.storage.sql.exec<{ ts: number; sev: number; text: string }>("SELECT * FROM messages ORDER BY ts DESC LIMIT ?", n).toArray()
      .reverse().map(m => ({ time: new Date(m.ts).toISOString(), severity: m.sev, text: m.text }));
  }

  private stateOf(id: string, now: number) {
    this.droneId = id;
    const st = toState(id, this.latest, now) as Record<string, unknown>;
    if (!this.latest) return st;
    const files = (name: string, url: string) => {
      const b = this.blobInfo.get(name);
      return b ? { url, updated_at: new Date(b.updated_at).toISOString(), bytes: b.bytes } : null;
    };
    return { ...st, camera: toCamera(id, this.frameAt, this.latest.t.camera_live === true, now),
             radio_snapshot: this.snapshotInfo(id),
             files: {
               routes: files("routes", `/v1/drones/${id}/routes`),
               airspace_layers: files("airspace_layers", `/v1/drones/${id}/airspace/layers`),
               airspace_overlay: files("airspace_overlay", `/v1/drones/${id}/airspace/overlay.png`),
             },
             messages: this.recentMessages(10) };
  }

  async position(id: string) { return toPosition(id, this.latest, Date.now()); }
  async state(id: string) { return this.stateOf(id, Date.now()); }

  async messages(id: string, since: number, limit: number) {
    const rows = this.ctx.storage.sql.exec<{ ts: number; sev: number; text: string }>(
      "SELECT * FROM (SELECT * FROM messages WHERE ts >= ? ORDER BY ts DESC LIMIT ?) ORDER BY ts", since, limit).toArray();
    return { drone_id: id, count: rows.length,
             messages: rows.map(m => ({ time: new Date(m.ts).toISOString(), severity: m.sev, text: m.text })) };
  }

  /** H.264 frame records from the laptop: keep the frames since the last keyframe in memory
   *  (a new viewer needs a keyframe to start), and send each frame to camera stream clients. */
  async putVideo(body: ArrayBuffer) {
    const recs = splitRecords(body);
    if (!recs) return;
    const sockets = this.ctx.getWebSockets("camera");
    for (const r of recs) {
      const rec = body.slice(r.off, r.off + REC_HDR + r.len);
      if (r.key) { this.gop = []; this.gopBytes = 0; }
      if (this.gop.length || r.key) {
        this.gop.push(rec); this.gopBytes += rec.byteLength;
        if (this.gopBytes > GOP_MAX_BYTES) { this.gop = []; this.gopBytes = 0; }   // no keyframe for too long
      }
      for (const ws of sockets) {
        const started = (ws.deserializeAttachment() as { started?: boolean } | null)?.started === true;
        if (!started && !r.key) continue;                     // a decoder must start at a keyframe
        if (!started) ws.serializeAttachment({ started: true });
        try { ws.send(rec); } catch { /* socket closing */ }
      }
    }
    this.frameAt = Date.now();
  }

  private live() { return this.frameAt != null && Date.now() - this.frameAt <= CAMERA_LIVE_S * 1000; }

  /** H.264 Annex B from the last keyframe to now, or null when the camera is not live. */
  async getVideo(): Promise<{ h264: Uint8Array; frames: number; at: number } | null> {
    if (!this.live() || !this.gop.length) return null;
    const n = this.gop.reduce((a, r) => a + r.byteLength - REC_HDR, 0), out = new Uint8Array(n);
    let o = 0;
    for (const r of this.gop) { out.set(new Uint8Array(r, REC_HDR), o); o += r.byteLength - REC_HDR; }
    return { h264: out, frames: this.gop.length, at: this.frameAt! };
  }

  async track(id: string, since: number, limit: number) {
    const rows = this.ctx.storage.sql.exec<Record<string, number | string | null>>(
      `SELECT * FROM (SELECT * FROM track WHERE received_at >= ? ORDER BY received_at DESC LIMIT ?) ORDER BY received_at`,
      since, limit).toArray();
    return {
      drone_id: id,
      count: rows.length,
      points: rows.map(r => ({
        time: new Date(r.received_at as number).toISOString(),
        lat: r.lat, lon: r.lon, alt_msl_m: r1(r.alt_msl as number | null), height_m: r1(r.height as number | null),
        ground_speed_ms: r1(Math.hypot((r.vn as number) ?? 0, (r.ve as number) ?? 0), 2),
        heading_deg: r1(r.hdg as number | null), mode: r.mode, armed: r.armed === 1,
      })),
    };
  }

  /** WebSocket stream (hibernation API): sends the current state, then each update. */
  async fetch(request: Request): Promise<Response> {
    const u = new URL(request.url);
    const id = u.searchParams.get("drone") ?? "";
    const pair = new WebSocketPair();
    if (u.pathname === "/camera") {
      this.ctx.acceptWebSocket(pair[1], ["camera"]);
      const live = this.live() && this.gop.length > 0;
      pair[1].serializeAttachment({ started: live });
      if (live) for (const r of this.gop) pair[1].send(r);   // from the last keyframe: the viewer can decode at once
    } else {
      this.ctx.acceptWebSocket(pair[1], ["state"]);
      pair[1].send(JSON.stringify({ type: "state", data: this.stateOf(id, Date.now()) }));
    }
    return new Response(null, { status: 101, webSocket: pair[0] });
  }

  async webSocketMessage(ws: WebSocket, message: string | ArrayBuffer) {
    if (message === "ping") ws.send("pong");  // read-only stream; clients may ping
  }

  async webSocketClose(ws: WebSocket, code: number) {
    try { ws.close(code, "bye"); } catch { /* already closed */ }
  }
}

/* ---------------- orders ---------------- */
// Customer/ops orders. One global Durable Object (getByName("orders")), not
// per-drone: orders outlive trips and dispatch assigns them across drones.
// POC auth is READ_TOKEN on every order endpoint (guest checkout, CORS-open);
// operator auth is a follow-up, not a blocker.

const ORDER_STATUS = ["placed", "accepted", "picked_up", "loaded", "in_flight",
  "delivered", "failed", "cancelled"] as const;
type OrderStatus = typeof ORDER_STATUS[number];

/** Legal status moves. Terminal states (delivered, failed, cancelled) have no exits. */
const ORDER_NEXT: Record<OrderStatus, OrderStatus[]> = {
  placed: ["accepted", "cancelled"],
  accepted: ["picked_up", "failed", "cancelled"],
  picked_up: ["loaded", "failed", "cancelled"],
  loaded: ["in_flight", "failed", "cancelled"],
  in_flight: ["delivered", "failed"],
  delivered: [],
  failed: [],
  cancelled: [],
};

const ORDER_ID = /^[A-Za-z0-9_-]{1,64}$/;
const ITEMS_MAX = 20;

type OrderRow = {
  id: string; status: string; items: string; pickup: string; dropoff: string;
  drone_id: string | null; command_id: string | null; reason: string | null;
  created_at: number; updated_at: number;
};

/**
 * Whole flight plan filed by dispatch. Concrete JSON shapes only: RPC stub
 * methods reject `unknown` return types as unserializable, so the plan is
 * validated at the dispatch boundary instead of passed through as JSON.
 */
export interface FlightPlan {
  order_id: string;
  drone_id: string | null;
  from: string;
  to: string;
  route_path: number[][] | null;
  length_m: number | null;
  est_time_s: number | null;
  issued_at: string;
}

function orderOut(o: OrderRow, plan: FlightPlan | null) {
  return { id: o.id, status: o.status, items: JSON.parse(o.items) as OrderItem[], pickup: o.pickup, dropoff: o.dropoff,
           drone_id: o.drone_id, command_id: o.command_id, reason: o.reason, flight_plan: plan,
           created_at: new Date(o.created_at).toISOString(), updated_at: new Date(o.updated_at).toISOString() };
}
type OrderOut = ReturnType<typeof orderOut>;

/** An order item: menu name and quantity. The menu itself lives in the customer app. */
export interface OrderItem {
  name: string;
  qty: number;
}
function cleanItems(v: unknown): OrderItem[] | string {
  if (!Array.isArray(v) || !v.length || v.length > ITEMS_MAX) return `items must be 1..${ITEMS_MAX} entries`;
  const out: OrderItem[] = [];
  for (const it of v) {
    const o = it as Record<string, unknown>;
    const name = str(o?.name, 80);
    const qty = num(o?.qty);
    if (!name) return "each item needs a name (up to 80 chars)";
    if (qty == null || !Number.isInteger(qty) || qty < 1 || qty > 99) return "each item needs qty, 1..99";
    out.push({ name, qty });
  }
  return out;
}

export class Orders extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(async () => {
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY, status TEXT NOT NULL, items TEXT NOT NULL,
        pickup TEXT NOT NULL, dropoff TEXT NOT NULL, drone_id TEXT, command_id TEXT, reason TEXT,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)`);
      // Whole flight plans filed by dispatch (phase 2); keyed by order.
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS flight_plans (
        order_id TEXT PRIMARY KEY, plan TEXT NOT NULL,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)`);
    });
  }

  async create(items: { name: string; qty: number }[], pickup: string, dropoff: string) {
    const now = Date.now();
    const id = `ord_${now.toString(36)}${crypto.randomUUID().slice(0, 6)}`;
    const sql = this.ctx.storage.sql;
    sql.exec("INSERT INTO orders (id, status, items, pickup, dropoff, drone_id, command_id, reason, " +
             "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
      id, "placed", JSON.stringify(items), pickup, dropoff, null, null, null, now, now);
    return orderOut(sql.exec<OrderRow>("SELECT * FROM orders WHERE id = ?", id).one(), null);
  }

  private planOf(id: string): FlightPlan | null {
    const r = this.ctx.storage.sql.exec<{ plan: string }>(
      "SELECT plan FROM flight_plans WHERE order_id = ?", id).toArray()[0];
    return r ? JSON.parse(r.plan) as FlightPlan : null;
  }

  async get(id: string) {
    const row = this.ctx.storage.sql.exec<OrderRow>("SELECT * FROM orders WHERE id = ?", id).toArray()[0];
    return row ? orderOut(row, this.planOf(id)) : null;
  }

  async list(status: string | null, limit: number) {
    const sql = this.ctx.storage.sql;
    const rows = (status
      ? sql.exec<OrderRow>("SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?", status, limit)
      : sql.exec<OrderRow>("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", limit)).toArray();
    return rows.map((r) => orderOut(r, this.planOf(r.id)));
  }

  /** File the whole flight plan dispatch validated. */
  async putFlightPlan(orderId: string, plan: FlightPlan) {
    this.ctx.storage.sql.exec("INSERT OR REPLACE INTO flight_plans (order_id, plan, created_at, updated_at) " +
                             "VALUES (?,?,?,?)", orderId, JSON.stringify(plan), Date.now(), Date.now());
  }

  /** Release: attach the filed plan's trip command, clearing any deferral. Dispatch-owned. */
  async linkCommand(id: string, commandId: string) {
    this.ctx.storage.sql.exec("UPDATE orders SET command_id = ?, reason = NULL, updated_at = ? WHERE id = ?",
      commandId, Date.now(), id);
    return this.get(id);
  }

  /** Dispatch preconditions unmet: keep the order where it is, say why. */
  async setReason(id: string, reason: string | null) {
    this.ctx.storage.sql.exec("UPDATE orders SET reason = ?, updated_at = ? WHERE id = ?",
      reason, Date.now(), id);
    return this.get(id);
  }

  /** Command-mirror writes; the caller guarantees a legal move. */
  async setStatus(id: string, status: OrderStatus, reason: string | null) {
    this.ctx.storage.sql.exec("UPDATE orders SET status = ?, reason = ?, updated_at = ? WHERE id = ?",
      status, reason, Date.now(), id);
    return this.get(id);
  }

  /** Advance status (validated against ORDER_NEXT) and/or assign a drone. command_id is dispatch-owned. */
  async patch(id: string, b: { status?: unknown; drone_id?: unknown; reason?: unknown }) {
    const sql = this.ctx.storage.sql;
    const row = sql.exec<OrderRow>("SELECT * FROM orders WHERE id = ?", id).toArray()[0];
    if (!row) return { error: "no such order", status: 404 };
    const terminal = ORDER_NEXT[row.status as OrderStatus].length === 0;
    let status = row.status, drone = row.drone_id, reason = row.reason;
    if (b.status != null) {
      if (typeof b.status !== "string" || !(ORDER_STATUS as readonly string[]).includes(b.status))
        return { error: `status must be one of ${ORDER_STATUS.join(", ")}`, status: 400 };
      if (!ORDER_NEXT[row.status as OrderStatus].includes(b.status as OrderStatus))
        return { error: `cannot move from ${row.status} to ${b.status}`, status: 400 };
      status = b.status;
    }
    if (b.drone_id !== undefined) {
      if (b.drone_id !== null && (typeof b.drone_id !== "string" || !DRONE_ID.test(b.drone_id)))
        return { error: "drone_id must be 1-32 chars of a-z, 0-9 or -", status: 400 };
      drone = b.drone_id;
    }
    if (status === "accepted" && !drone)
      return { error: "accept needs drone_id (dispatch assigns the trip to a drone)", status: 400 };
    if (b.reason !== undefined) {
      if (b.reason !== null && typeof b.reason !== "string") return { error: "reason must be a string", status: 400 };
      reason = b.reason == null ? null : b.reason.slice(0, 200);
    }
    if (status === row.status && drone === row.drone_id && reason === row.reason)
      return { order: orderOut(row, this.planOf(id)) };                    // no-op patch: return as-is
    if (terminal) return { error: `order is ${row.status}`, status: 400 };
    const now = Date.now();
    sql.exec("UPDATE orders SET status = ?, drone_id = ?, reason = ?, updated_at = ? WHERE id = ?",
      status, drone, reason, now, id);
    return { order: orderOut(sql.exec<OrderRow>("SELECT * FROM orders WHERE id = ?", id).one(), this.planOf(id)) };
  }

  /** Delete terminal orders only. Cancel live ones instead (the ops queue needs the trail). */
  async remove(id: string) {
    const sql = this.ctx.storage.sql;
    const row = sql.exec<OrderRow>("SELECT * FROM orders WHERE id = ?", id).toArray()[0];
    if (!row) return { error: "no such order", status: 404 };
    if (ORDER_NEXT[row.status as OrderStatus].length !== 0)
      return { error: `cannot delete a ${row.status} order (cancel it first)`, status: 400 };
    sql.exec("DELETE FROM orders WHERE id = ?", id);
    return { ok: true };
  }
}

/* ---------------- dispatch (rule-based, v1) ---------------- */
// Two phases matching the operator workflow: on accept dispatch validates and
// files the whole flight plan; on loaded it releases the plan as a goto
// command. Precondition failures keep the order where it is with a reason, so
// the operator can fix and re-drive it (re-PATCH the same status).

const DISPATCH_MIN_BATT = 60;   // the laptop refuses trips under 60% (see README)

/**
 * The slice of drone state dispatch reads. Typed separately because the
 * worker's public state carries opaque laptop blobs (ceiling, flyto, …),
 * which makes the generated RPC stub type unserializable.
 */
type DroneDispatchState = {
  online: boolean;
  battery: { percent: number | null } | null;
  autonomy: {
    backend_control_allowed: boolean;
    current_pad: string | null;
    can_goto: string[];
  } | null;
};

async function dispatch(env: Env, id: string): Promise<OrderOut | null> {
  const orders = env.ORDERS.getByName("orders");
  const cur = await orders.get(id);
  if (!cur || cur.status === "placed" || ORDER_NEXT[cur.status as OrderStatus].length === 0) return cur;
  const fail = async (why: string) => (await orders.setReason(id, `dispatch deferred: ${why}`)) ?? cur;
  if (!cur.flight_plan && cur.drone_id) {
    const drone = env.DRONE.getByName(cur.drone_id);
    const st = (await drone.state(cur.drone_id)) as unknown as DroneDispatchState;
    if (!st.online) return fail("drone offline");
    const au = st.autonomy;
    if (!au) return fail("no autonomy from laptop");
    if (!au.backend_control_allowed) return fail("backend control off (SA switch)");
    if ((st.battery?.percent ?? 0) < DISPATCH_MIN_BATT)
      return fail(`battery ${st.battery?.percent ?? "?"}% below ${DISPATCH_MIN_BATT}%`);
    if (au.current_pad !== cur.pickup)
      return fail(`drone is at ${au.current_pad ?? "unknown pad"}, order picks up at ${cur.pickup}`);
    if (!au.can_goto.includes(cur.dropoff))
      return fail(`no approved route ${cur.pickup} -> ${cur.dropoff} from the current pad`);
    const blob = await drone.getBlob("routes");
    if (!blob) return fail("laptop has not uploaded routes yet");
    let uploaded: { routes?: unknown };
    try { uploaded = JSON.parse(new TextDecoder().decode(blob.data)); }
    catch { return fail("laptop routes are not JSON"); }
    const route = (Array.isArray(uploaded.routes) ? uploaded.routes : []).find((r) =>
      r != null && typeof r === "object" && (r as Record<string, unknown>).from === cur.pickup &&
      (r as Record<string, unknown>).to === cur.dropoff && (r as Record<string, unknown>).approved === true);
    if (!route) return fail(`no approved route ${cur.pickup} -> ${cur.dropoff}`);
    const rp = route as Record<string, unknown>;
    await orders.putFlightPlan(id, { order_id: id, drone_id: cur.drone_id, from: cur.pickup, to: cur.dropoff,
      route_path: Array.isArray(rp.path) ? rp.path as number[][] : null,
      length_m: typeof rp.length_m === "number" ? rp.length_m : null,
      est_time_s: typeof rp.est_time_s === "number" ? rp.est_time_s : null,
      issued_at: new Date().toISOString() });
    await orders.setReason(id, null);   // filed: any earlier deferral is stale
  }
  const planned = await orders.get(id);
  if (!planned) return cur;
  if (planned.status === "loaded" && planned.flight_plan && !planned.command_id && planned.drone_id) {
    const r = await env.DRONE.getByName(planned.drone_id).command(planned.drone_id, "goto", planned.dropoff);
    if ("error" in r) return fail(`drone refused the trip: ${r.error}`);
    return (await orders.linkCommand(id, (r.command as { id: string }).id)) ?? planned;
  }
  return planned;
}

/** Map a trip command status onto the order machine. Null = still with dispatch/operator. */
function mirrorTarget(cmdStatus: string): OrderStatus | null {
  switch (cmdStatus) {
    case "in_progress": case "holding": case "returning": return "in_flight";
    case "done": return "delivered";
    case "failed": case "rejected": case "expired": case "superseded": return "failed";
    case "stopped_by_pilot": return "failed";
    default: return null;   // queued, delivered, accepted: the trip has not started
  }
}

/** Fold the trip command's progress into the order on read. Writes only legal moves. */
async function mirrorOrder(env: Env, o: OrderOut): Promise<OrderOut> {
  if (!o.command_id || !o.drone_id) return o;
  if (ORDER_NEXT[o.status as OrderStatus].length === 0) return o;
  let cmd: Awaited<ReturnType<DroneState["getCommand"]>>;
  try {
    cmd = await env.DRONE.getByName(o.drone_id).getCommand(o.command_id);
  } catch { return o; }
  if (!cmd) return o;
  const target = mirrorTarget(cmd.status);
  if (!target || target === o.status) return o;
  if (!ORDER_NEXT[o.status as OrderStatus].includes(target)) return o;
  const reason = target === "failed" ? (cmd.reason ?? o.reason ?? "trip failed") : o.reason;
  return (await env.ORDERS.getByName("orders").setStatus(o.id, target, reason)) ?? o;
}

/* ---------------- router ---------------- */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type",
  "Access-Control-Expose-Headers": "X-Frame-Time, X-Frame, X-Frames, X-Bounds, X-Updated-At",
  "Access-Control-Max-Age": "86400",
};

/** Files the laptop uploads (stored in the drone's Durable Object, the latest of each). */
const FILES = {
  snapshot: { name: "snapshot", label: "radio snapshot", types: ["image/webp", "image/jpeg"] },
  routes: { name: "routes", label: "routes", types: ["application/json"] },
  layers: { name: "airspace_layers", label: "airspace layers", types: ["application/json"] },
  overlay: { name: "airspace_overlay", label: "airspace overlay", types: ["image/png"] },
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...CORS },
  });
}
const error = (status: number, message: string) => json({ error: message }, status);

async function safeEqual(a: string, b: string): Promise<boolean> {
  if (!a || !b) return false;
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([crypto.subtle.digest("SHA-256", enc.encode(a)), crypto.subtle.digest("SHA-256", enc.encode(b))]);
  return crypto.subtle.timingSafeEqual(ha, hb);
}
function bearer(req: Request): string {
  const h = req.headers.get("Authorization") ?? "";
  return h.startsWith("Bearer ") ? h.slice(7) : "";
}

function parseSince(v: string | null): number {
  if (!v) return Date.now() - 3600_000;  // default: last hour
  const n = Number(v);
  if (Number.isFinite(n)) return n;
  const d = Date.parse(v);
  return Number.isFinite(d) ? d : NaN;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);  // v1 drones :id :what [:cid]

    if (url.pathname === "/v1/health") return json({ ok: true, time: new Date().toISOString() });

    // Orders: customer/ops CRUD (global, not per-drone). POC auth: READ_TOKEN.
    if (parts[0] === "v1" && parts[1] === "orders") {
      if (!(await safeEqual(bearer(request), env.READ_TOKEN))) return error(401, "bad read token");
      const orders = env.ORDERS.getByName("orders");
      if (parts.length === 2) {
        if (request.method === "POST") {
          let b: Record<string, unknown>;
          try { b = (await request.json()) as Record<string, unknown>; } catch { return error(400, "invalid JSON"); }
          const items = cleanItems(b.items);
          if (typeof items === "string") return error(400, items);
          const pickup = str(b.pickup, 32), dropoff = str(b.dropoff, 32);
          if (!pickup || !PAD_ID.test(pickup)) return error(400, "pickup must be a pad id (a-z, 0-9, -, up to 32 chars)");
          if (!dropoff || !PAD_ID.test(dropoff)) return error(400, "dropoff must be a pad id (a-z, 0-9, -, up to 32 chars)");
          return json(await orders.create(items, pickup, dropoff), 201);
        }
        if (request.method !== "GET") return error(405, "use GET or POST");
        const st = url.searchParams.get("status");
        if (st != null && !(ORDER_STATUS as readonly string[]).includes(st))
          return error(400, `status must be one of ${ORDER_STATUS.join(", ")}`);
        const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 100) || 100, 1), 500);
        const found = await orders.list(st, limit);
        return json({ orders: await Promise.all(found.map((o) => mirrorOrder(env, o))) });
      }
      if (parts.length === 3 && ORDER_ID.test(parts[2])) {
        const oid = parts[2];
        if (request.method === "GET") {
          const o = await orders.get(oid);
          return o ? json(await mirrorOrder(env, o)) : error(404, "no such order");
        }
        if (request.method === "PATCH") {
          let b: Record<string, unknown>;
          try { b = (await request.json()) as Record<string, unknown>; } catch { return error(400, "invalid JSON"); }
          const r = await orders.patch(oid, b);
          if ("error" in r) return error(r.status as number, r.error as string);
          let order = r.order;
          // Accept files the flight plan; loaded releases it as a goto. Re-PATCH
          // the same status to retry after fixing a dispatch-deferred reason.
          if (b.status === "accepted" || order.status === "loaded")
            order = (await dispatch(env, oid)) ?? order;
          return json(await mirrorOrder(env, order));
        }
        if (request.method === "DELETE") {
          const r = await orders.remove(oid);
          return "error" in r ? error(r.status as number, r.error as string) : json({ ok: true });
        }
        return error(405, "use GET, PATCH or DELETE");
      }
      return error(404, "not found");
    }

    if (parts.length < 4 || parts.length > 5 || parts[0] !== "v1" || parts[1] !== "drones") return error(404, "not found");
    const [, , id, what] = parts;
    if (!DRONE_ID.test(id)) return error(400, "drone id must be 1-32 chars of a-z, 0-9 or -");
    const stub = env.DRONE.getByName(id);

    // Camera: best effort (see the top of this file).
    if (what === "camera" && parts.length === 4) {
      if (request.method !== "POST") return error(405, "use POST");
      if (!(await safeEqual(bearer(request), env.INGEST_TOKEN))) return error(401, "bad ingest token");
      const body = await request.arrayBuffer();
      if (body.byteLength > CAMERA_MAX_BYTES) return error(400, "up to 1 MB per POST");
      const recs = splitRecords(body);
      if (!recs) return error(400, "send H.264 frame records (see the top of this file)");
      await stub.putVideo(body);
      return json({ ok: true, frames: recs.length });
    }
    if (what === "camera.h264" || (what === "camera" && parts[4] === "stream")) {
      if (request.method !== "GET") return error(405, "use GET");
      const tok = bearer(request) || (url.searchParams.get("token") ?? "");
      if (!(await safeEqual(tok, env.READ_TOKEN))) return error(401, "bad read token");
      if (what === "camera") {
        if (request.headers.get("Upgrade") !== "websocket") return error(426, "WebSocket upgrade required");
        return stub.fetch(new Request(`https://do/camera?drone=${id}`, request));
      }
      const v = await stub.getVideo();
      if (!v) return error(503, "camera not live (best effort: it is often down)");
      return new Response(v.h264, { headers: { "Content-Type": "video/h264", "Cache-Control": "no-store",
        "X-Frame-Time": new Date(v.at).toISOString(), "X-Frames": String(v.frames), ...CORS } });
    }

    // Files from the laptop: the radio snapshot, the routes and pads, the airspace map.
    const file = what === "snapshot" && parts.length === 4 ? FILES.snapshot
      : what === "routes" && parts.length === 4 ? FILES.routes
      : what === "airspace" && parts[4] === "layers" ? FILES.layers
      : what === "airspace" && (parts[4] === "overlay" || parts[4] === "overlay.png") ? FILES.overlay
      : null;
    if (file) {
      if (request.method === "POST") {
        if (!(await safeEqual(bearer(request), env.INGEST_TOKEN))) return error(401, "bad ingest token");
        const type = (request.headers.get("Content-Type") ?? "").split(";")[0].trim();
        if (!file.types.includes(type)) return error(415, `Content-Type must be ${file.types.join(" or ")}`);
        const body = await request.arrayBuffer();
        if (!body.byteLength || body.byteLength > FILE_MAX_BYTES) return error(400, "empty, or over 25 MB");
        if (type === "application/json") {
          try { JSON.parse(new TextDecoder().decode(body)); } catch { return error(400, "invalid JSON"); }
        }
        const meta: Record<string, unknown> = {};
        const frame = Number(request.headers.get("X-Frame")), at = Number(request.headers.get("X-Frame-Time"));
        if (Number.isFinite(frame)) meta.frame = frame;
        if (Number.isFinite(at) && at > 0) meta.captured_at = at;
        const bounds = request.headers.get("X-Bounds");
        if (bounds) { try { meta.bounds = JSON.parse(bounds); } catch { /* ignore */ } }
        await stub.putBlob(file.name, body, type, meta);
        return json({ ok: true, bytes: body.byteLength });
      }
      if (request.method !== "GET") return error(405, "use GET or POST");
      const tok = bearer(request) || (url.searchParams.get("token") ?? "");   // token in the URL: for <img src>
      if (!(await safeEqual(tok, env.READ_TOKEN))) return error(401, "bad read token");
      const b = await stub.getBlob(file.name);
      if (!b) return error(404, `no ${file.label} from the laptop yet`);
      const meta = b.info.meta ? (JSON.parse(b.info.meta) as Record<string, unknown>) : {};
      const h: Record<string, string> = { "Content-Type": b.info.type, "Cache-Control": "no-store",
        "X-Updated-At": new Date(b.info.updated_at).toISOString(), ...CORS };
      if (meta.frame != null) h["X-Frame"] = String(meta.frame);
      if (typeof meta.captured_at === "number") h["X-Frame-Time"] = new Date(meta.captured_at).toISOString();
      if (meta.bounds != null) h["X-Bounds"] = JSON.stringify(meta.bounds);
      return new Response(b.data, { headers: h });
    }

    if (what === "telemetry") {
      if (request.method !== "POST") return error(405, "use POST");
      if (!(await safeEqual(bearer(request), env.INGEST_TOKEN))) return error(401, "bad ingest token");
      let body: unknown;
      try { body = await request.json(); } catch { return error(400, "invalid JSON"); }
      const t = cleanTelemetry(body);
      if (typeof t === "string") return error(400, t);
      const command = await stub.ingest(id, t);
      return json(command ? { ok: true, command } : { ok: true });
    }

    if (what === "commands") {
      const tok = bearer(request);
      const isCmd = await safeEqual(tok, env.COMMAND_TOKEN);
      if (request.method === "POST" && parts.length === 4) {
        if (!isCmd) return error(401, "bad command token");
        let b: Record<string, unknown>;
        try { b = (await request.json()) as Record<string, unknown>; } catch { return error(400, "invalid JSON"); }
        const action = b?.action as Action;
        if (!ACTIONS.includes(action)) return error(400, `action must be one of ${ACTIONS.join(", ")}`);
        const pad = action === "goto" ? b.pad : null;
        if (action === "goto" && (typeof pad !== "string" || !PAD_ID.test(pad))) return error(400, "goto needs pad (a-z, 0-9, -)");
        let args: FlytoArgs | null = null;
        if (action === "flyto") {
          const lat = num(b.lat), lon = num(b.lon), alt = num(b.alt), speed = b.speed == null ? null : num(b.speed);
          if (lat == null || lon == null || Math.abs(lat) > 90 || Math.abs(lon) > 180) return error(400, "flyto needs lat and lon");
          if (alt == null || alt < 2 || alt > 60) return error(400, "flyto needs alt, 2..60 m above home");
          if (b.speed != null && (speed == null || speed < 0.5 || speed > 5)) return error(400, "speed must be 0.5..5 m/s");
          if (b.land != null && typeof b.land !== "boolean") return error(400, "land must be true or false");
          args = { lat, lon, alt, land: b.land !== false, speed };
        }
        const r = await stub.command(id, action, pad as string | null, args);
        if ("error" in r) return error(r.status as number, r.error as string);
        return json(r, 202);
      }
      if (request.method !== "GET") return error(405, "use GET or POST");
      if (!isCmd && !(await safeEqual(tok, env.READ_TOKEN))) return error(401, "bad token");
      if (parts.length === 5) {
        const c = await stub.getCommand(parts[4]);
        return c ? json(c) : error(404, "no such command");
      }
      return json({ drone_id: id, commands: await stub.listCommands() });
    }
    if (parts.length !== 4) return error(404, "not found");

    if (request.method !== "GET") return error(405, "use GET");

    if (what === "stream") {
      if (request.headers.get("Upgrade") !== "websocket") return error(426, "WebSocket upgrade required");
      if (!(await safeEqual(url.searchParams.get("token") ?? "", env.READ_TOKEN))) return error(401, "bad read token");
      return stub.fetch(new Request(`https://do/stream?drone=${id}`, request));
    }

    if (!(await safeEqual(bearer(request), env.READ_TOKEN))) return error(401, "bad read token");
    if (what === "position") return json(await stub.position(id));
    if (what === "state") return json(await stub.state(id));
    if (what === "messages") {
      const since = parseSince(url.searchParams.get("since"));
      if (!Number.isFinite(since)) return error(400, "since must be ms since epoch or an ISO time");
      const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 200) || 200, 1), 2000);
      return json(await stub.messages(id, since, limit));
    }
    if (what === "track") {
      const since = parseSince(url.searchParams.get("since"));
      if (!Number.isFinite(since)) return error(400, "since must be ms since epoch or an ISO time");
      const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 3600) || 3600, 1), 20000);
      return json(await stub.track(id, since, limit));
    }
    return error(404, "not found");
  },
} satisfies ExportedHandler<Env>;
