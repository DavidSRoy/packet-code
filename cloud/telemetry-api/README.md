# Packet telemetry API

Cloudflare Worker with one Durable Object per drone. The laptop ground control server pushes the drone state once each second. The app team reads it here.

```
drone ──radio──> laptop ground_control/server.py ──HTTPS POST 1 Hz──> Worker ──> app
```

## For the app team

Base URL: `https://packet-telemetry.<account>.workers.dev` (set after the first deploy).
Drone ID: `packet-v0`.
Auth: `Authorization: Bearer <READ_TOKEN>` on every read. CORS is open, so browser apps can call it directly.

### `GET /v1/drones/packet-v0/position`

```json
{
  "drone_id": "packet-v0",
  "online": true,
  "updated_at": "2026-10-22T17:12:30.901Z",
  "age_s": 0.7,
  "position": { "lat": 37.7749120, "lon": -122.4193010, "alt_msl_m": 21.7, "height_m": 1.2 },
  "velocity": { "north_ms": -0.01, "east_ms": 0.09, "down_ms": 0.03, "ground_speed_ms": 0.09 },
  "heading_deg": 317,
  "home": { "lat": 37.7748400, "lon": -122.4194010 }
}
```

- `online` is false when no update came for 5 s, or when the laptop lost the drone link.
- `position` is `null` before the first GPS fix.
- `height_m` is the height above the takeoff point (home). `alt_msl_m` is the height above sea level.

### `GET /v1/drones/packet-v0/state`

This has the same fields as `/position`, plus:

```json
{
  "mode": "GUIDED", "armed": true,
  "attitude": { "roll_deg": 0.5, "pitch_deg": -0.2 },
  "battery": { "voltage_v": 24.6, "current_a": 18.2, "cell_v": 4.1 },
  "gps": { "fix_type": 3, "satellites": 18 }
}
```

### `GET /v1/drones/packet-v0/track?since=<ms or ISO time>&limit=<n>`

- The track is kept for 24 h, with about 1 point each second.
- The default is the last hour. `limit` is 1–20000, default 3600.
- You get the newest points, oldest first.

```json
{ "drone_id": "packet-v0", "count": 2, "points": [
  { "time": "2026-10-22T17:12:29.9Z", "lat": 37.77491, "lon": -122.41930, "alt_msl_m": 21.7, "height_m": 1.2,
    "ground_speed_ms": 0.1, "heading_deg": 317, "mode": "GUIDED", "armed": true } ] }
```

### Live stream: `wss://<base>/v1/drones/packet-v0/stream?token=<READ_TOKEN>`

- When you connect, you get the current state. Then you get each update, about once each second, in the same shape as `/state`: `{"type": "state", "data": {...}}`.
- Send `ping` to get `pong`.
- Browsers cannot set headers on WebSockets, so the token goes in the query string.

### Errors

`401` for a bad token, `400` for bad input, `404` for an unknown route. The body is `{"error": "..."}`.

## Run and deploy

```bash
npm install
npm run check          # type check
npm run dev            # local at http://127.0.0.1:8787, tokens from .dev.vars
npm test               # end-to-end test against npm run dev
```

`.dev.vars` (local only, not in git):

```
INGEST_TOKEN=dev-ingest-token
READ_TOKEN=dev-read-token
```

Deploy:

```bash
npx wrangler login
npx wrangler secret put INGEST_TOKEN   # a long random string; the laptop uses it
npx wrangler secret put READ_TOKEN     # a different long random string; give it to the app team
npm run deploy
```

Then start the laptop server with the push on:

```bash
export PACKET_INGEST_TOKEN=<INGEST_TOKEN>
.venv/bin/python ground_control/server.py --cloud-url https://packet-telemetry.<account>.workers.dev
```

The top bar of the ground control page shows `Cloud OK` when the pushes succeed. If the push fails, flight control is not affected.
