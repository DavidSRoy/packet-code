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
 *   GET  /v1/health                 no auth
 */
import { DurableObject } from "cloudflare:workers";

export interface Env {
  DRONE: DurableObjectNamespace<DroneState>;
  INGEST_TOKEN: string;
  READ_TOKEN: string;
}

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
  hdg?: number | null;        // deg
  roll?: number; pitch?: number;          // deg
  mode?: string; armed?: boolean;
  batt_v?: number | null; batt_a?: number | null;
  gps_fix?: number; sats?: number;
  home_lat?: number | null; home_lon?: number | null;
}

interface Stored { t: Telemetry; received_at: number }

const NUM_FIELDS = ["ts", "lat", "lon", "alt_msl", "height", "vn", "ve", "vd", "hdg", "roll", "pitch",
  "batt_v", "batt_a", "gps_fix", "sats", "home_lat", "home_lon"] as const;

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
  return out as unknown as Telemetry;
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
    attitude: { roll_deg: r1(t.roll), pitch_deg: r1(t.pitch) },
    battery: { voltage_v: r1(t.batt_v, 2), current_a: r1(t.batt_a), cell_v: t.batt_v == null ? null : r1(t.batt_v / 6, 2) },
    gps: { fix_type: t.gps_fix, satellites: t.sats },
  };
}

export class DroneState extends DurableObject<Env> {
  private latest: Stored | null = null;
  private inserts = 0;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(async () => {
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS latest (k INTEGER PRIMARY KEY CHECK (k = 1), json TEXT NOT NULL)`);
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS track (
        received_at INTEGER PRIMARY KEY, lat REAL, lon REAL, alt_msl REAL, height REAL,
        vn REAL, ve REAL, vd REAL, hdg REAL, mode TEXT, armed INTEGER, batt_v REAL)`);
      const row = ctx.storage.sql.exec<{ json: string }>("SELECT json FROM latest WHERE k = 1").toArray()[0];
      this.latest = row ? (JSON.parse(row.json) as Stored) : null;
    });
  }

  async ingest(id: string, t: Telemetry): Promise<void> {
    const now = Date.now();
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
    const msg = JSON.stringify({ type: "state", data: toState(id, s, now) });
    for (const ws of this.ctx.getWebSockets()) {
      try { ws.send(msg); } catch { /* socket closing */ }
    }
  }

  async position(id: string) { return toPosition(id, this.latest, Date.now()); }
  async state(id: string) { return toState(id, this.latest, Date.now()); }

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
    const id = new URL(request.url).searchParams.get("drone") ?? "";
    const pair = new WebSocketPair();
    this.ctx.acceptWebSocket(pair[1], [id]);
    pair[1].send(JSON.stringify({ type: "state", data: toState(id, this.latest, Date.now()) }));
    return new Response(null, { status: 101, webSocket: pair[0] });
  }

  async webSocketMessage(ws: WebSocket, message: string | ArrayBuffer) {
    if (message === "ping") ws.send("pong");  // read-only stream; clients may ping
  }

  async webSocketClose(ws: WebSocket, code: number) {
    try { ws.close(code, "bye"); } catch { /* already closed */ }
  }
}

/* ---------------- router ---------------- */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type",
  "Access-Control-Max-Age": "86400",
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
    const parts = url.pathname.split("/").filter(Boolean);  // v1 drones :id :what

    if (url.pathname === "/v1/health") return json({ ok: true, time: new Date().toISOString() });
    if (parts.length !== 4 || parts[0] !== "v1" || parts[1] !== "drones") return error(404, "not found");
    const [, , id, what] = parts;
    if (!DRONE_ID.test(id)) return error(400, "drone id must be 1-32 chars of a-z, 0-9 or -");
    const stub = env.DRONE.getByName(id);

    if (what === "telemetry") {
      if (request.method !== "POST") return error(405, "use POST");
      if (!(await safeEqual(bearer(request), env.INGEST_TOKEN))) return error(401, "bad ingest token");
      let body: unknown;
      try { body = await request.json(); } catch { return error(400, "invalid JSON"); }
      const t = cleanTelemetry(body);
      if (typeof t === "string") return error(400, t);
      await stub.ingest(id, t);
      return json({ ok: true });
    }

    if (request.method !== "GET") return error(405, "use GET");

    if (what === "stream") {
      if (request.headers.get("Upgrade") !== "websocket") return error(426, "WebSocket upgrade required");
      if (!(await safeEqual(url.searchParams.get("token") ?? "", env.READ_TOKEN))) return error(401, "bad read token");
      return stub.fetch(new Request(`https://do/stream?drone=${id}`, request));
    }

    if (!(await safeEqual(bearer(request), env.READ_TOKEN))) return error(401, "bad read token");
    if (what === "position") return json(await stub.position(id));
    if (what === "state") return json(await stub.state(id));
    if (what === "track") {
      const since = parseSince(url.searchParams.get("since"));
      if (!Number.isFinite(since)) return error(400, "since must be ms since epoch or an ISO time");
      const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 3600) || 3600, 1), 20000);
      return json(await stub.track(id, since, limit));
    }
    return error(404, "not found");
  },
} satisfies ExportedHandler<Env>;
