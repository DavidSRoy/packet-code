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
 *   POST /v1/drones/:id/commands    Bearer COMMAND_TOKEN  {"action":"goto","pad":"qfc"} | hold | resume | return
 *   GET  /v1/drones/:id/commands    Bearer READ_TOKEN or COMMAND_TOKEN (last 20)
 *   GET  /v1/drones/:id/commands/:c Bearer READ_TOKEN or COMMAND_TOKEN
 *   GET  /v1/health                 no auth
 *
 * Commands reach the drone through the laptop: the reply to each telemetry
 * POST carries the next queued command. The laptop answers in a later POST
 * (acks), and the trip progress comes in the "autonomy" block.
 */
import { DurableObject } from "cloudflare:workers";

export interface Env {
  DRONE: DurableObjectNamespace<DroneState>;
  INGEST_TOKEN: string;
  READ_TOKEN: string;
  COMMAND_TOKEN: string;
}

const COMMAND_EXPIRE_MS = 15_000;      // a command the laptop did not pick up in this time expires
const ACTIONS = ["goto", "hold", "resume", "return"] as const;
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
  batt_pct?: number | null;   // % charge left, from the Pixhawk (mAh used vs BATT_CAPACITY)
  batt_mah?: number | null;   // mAh used since power-up
  batt_min?: number | null;   // estimated flight minutes left to the 20% reserve
  gps_fix?: number; sats?: number;
  home_lat?: number | null; home_lon?: number | null;
  autonomy?: Autonomy | null;
  acks?: Ack[];
}

interface Stored { t: Telemetry; received_at: number }

const NUM_FIELDS = ["ts", "lat", "lon", "alt_msl", "height", "vn", "ve", "vd", "hdg", "roll", "pitch",
  "batt_v", "batt_a", "batt_pct", "batt_mah", "batt_min", "gps_fix", "sats", "home_lat", "home_lon"] as const;

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
  out.autonomy = cleanAutonomy(b.autonomy);
  out.acks = Array.isArray(b.acks)
    ? b.acks.filter((a): a is Ack => !!a && typeof a === "object" && typeof (a as Ack).id === "string")
        .slice(0, 10).map(a => ({ id: a.id.slice(0, 40), status: a.status === "accepted" ? "accepted" : "rejected",
                                 reason: typeof a.reason === "string" ? a.reason.slice(0, 200) : null }))
    : [];
  return out as unknown as Telemetry;
}

const str = (v: unknown, n = 64) => (typeof v === "string" ? v.slice(0, n) : null);
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
    attitude: { roll_deg: r1(t.roll), pitch_deg: r1(t.pitch) },
    battery: {
      percent: t.batt_pct ?? null,
      voltage_v: r1(t.batt_v, 2), current_a: r1(t.batt_a), cell_v: t.batt_v == null ? null : r1(t.batt_v / 6, 2),
      used_mah: t.batt_mah ?? null,
      time_left_min: r1(t.batt_min),
    },
    gps: { fix_type: t.gps_fix, satellites: t.sats },
    autonomy: toAutonomy(t.autonomy),
  };
}

function toAutonomy(a: Autonomy | null | undefined) {
  if (!a) return null;
  const m = a.mission;
  return {
    backend_control_allowed: a.sa_on,       // SA switch on the pilot's radio
    current_pad: a.pad,                      // null when flying or not on a known pad
    pads: a.pads,
    can_goto: a.can_goto,                    // pads with an approved route from the current pad
    trip: {
      state: m.state, from: m.from, to: m.to,
      progress: m.items ? Math.round((Math.min(m.item, m.items) / m.items) * 100) : 0,
      reason: m.reason, command_id: m.cmd_id,
    },
  };
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
  created_at: number; updated_at: number;
};
function commandOut(c: CommandRow) {
  return { id: c.id, action: c.action, pad: c.pad, status: c.status, reason: c.reason,
           created_at: new Date(c.created_at).toISOString(), updated_at: new Date(c.updated_at).toISOString() };
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
      ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS commands (
        id TEXT PRIMARY KEY, action TEXT NOT NULL, pad TEXT, status TEXT NOT NULL, reason TEXT,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)`);
      const row = ctx.storage.sql.exec<{ json: string }>("SELECT json FROM latest WHERE k = 1").toArray()[0];
      this.latest = row ? (JSON.parse(row.json) as Stored) : null;
    });
  }

  private setStatus(cid: string, status: string, reason: string | null, now: number) {
    this.ctx.storage.sql.exec("UPDATE commands SET status = ?, reason = ?, updated_at = ? WHERE id = ?",
      status, reason, now, cid);
  }

  /** Commands: apply the laptop's acks and trip state; return the next queued command, if any. */
  private exchange(t: Telemetry, now: number): { id: string; action: string; pad: string | null } | null {
    const sql = this.ctx.storage.sql;
    for (const a of t.acks ?? []) this.setStatus(a.id, a.status, a.reason, now);
    const m = t.autonomy?.mission;
    if (m?.cmd_id) {
      const st = tripStatus(m.state);
      const row = sql.exec<CommandRow>("SELECT * FROM commands WHERE id = ?", m.cmd_id).toArray()[0];
      if (st && row && row.status !== st && !["rejected", "superseded", "expired"].includes(row.status))
        this.setStatus(m.cmd_id, st, m.reason, now);
    }
    sql.exec("UPDATE commands SET status = 'expired', reason = 'the laptop did not pick it up', updated_at = ? " +
             "WHERE status = 'queued' AND created_at < ?", now, now - COMMAND_EXPIRE_MS);
    const next = sql.exec<CommandRow>("SELECT * FROM commands WHERE status = 'queued' ORDER BY created_at LIMIT 1").toArray()[0];
    if (!next) return null;
    this.setStatus(next.id, "delivered", null, now);
    return { id: next.id, action: next.action, pad: next.pad };
  }

  async command(id: string, action: Action, pad: string | null) {
    const now = Date.now();
    const s = this.latest;
    if (!s || now - s.received_at > ONLINE_S * 1000 || s.t.link === false)
      return { error: "drone offline: no data from the laptop, or the laptop has no link to the drone", status: 409 };
    const sql = this.ctx.storage.sql;
    // a newer command replaces one the laptop has not picked up yet
    sql.exec("UPDATE commands SET status = 'superseded', updated_at = ? WHERE status = 'queued'", now);
    const cid = `cmd_${now.toString(36)}${crypto.randomUUID().slice(0, 6)}`;
    sql.exec("INSERT INTO commands VALUES (?,?,?,?,?,?,?)", cid, action, pad, "queued", null, now, now);
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

  async ingest(id: string, t: Telemetry): Promise<{ id: string; action: string; pad: string | null } | null> {
    const now = Date.now();
    const next = this.exchange(t, now);
    delete t.acks;
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
    return next;
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
    const parts = url.pathname.split("/").filter(Boolean);  // v1 drones :id :what [:cid]

    if (url.pathname === "/v1/health") return json({ ok: true, time: new Date().toISOString() });
    if (parts.length < 4 || parts.length > 5 || parts[0] !== "v1" || parts[1] !== "drones") return error(404, "not found");
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
        const r = await stub.command(id, action, pad as string | null);
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
    if (what === "track") {
      const since = parseSince(url.searchParams.get("since"));
      if (!Number.isFinite(since)) return error(400, "since must be ms since epoch or an ISO time");
      const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 3600) || 3600, 1), 20000);
      return json(await stub.track(id, since, limit));
    }
    return error(404, "not found");
  },
} satisfies ExportedHandler<Env>;
