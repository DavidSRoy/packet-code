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
  "battery": { "percent": 72, "voltage_v": 24.6, "current_a": 18.2, "cell_v": 4.1,
               "used_mah": 1820, "time_left_min": 8.4 },
  "gps": { "fix_type": 3, "satellites": 18 }
}
```

Battery fields:

| Field | Meaning |
|---|---|
| `percent` | Charge left, 0–100. The Pixhawk counts the mAh used against the pack size (6500 mAh). It is correct only if the pack was full at power-up. |
| `voltage_v`, `cell_v` | Pack voltage, and the voltage of one cell (6S). Full is 4.20 V per cell. Land at about 3.5 V per cell under load. |
| `current_a` | Current now. Hover is about 25 A. |
| `used_mah` | mAh used since power-up. |
| `time_left_min` | Estimated flight minutes until 20% charge (the landing reserve). In flight it uses the average current. On the ground it uses the last flight, or 25 A. |

Any battery field can be `null` when the drone does not send it.

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

### Autonomy block in `/state` and the stream

```json
"autonomy": {
  "backend_control_allowed": true,
  "current_pad": "qfc",
  "pads": { "qfc": { "name": "QFC", "lat": 47.6625238, "lon": -122.2950755 },
            "uplace": { "name": "UPLACE", "lat": 47.664, "lon": -122.299 } },
  "can_goto": ["uplace"],
  "trip": { "state": "enroute", "from": "qfc", "to": "uplace", "progress": 60,
            "reason": null, "command_id": "cmd_mh2k3x9a1b2c3" }
}
```

- `backend_control_allowed` is the SA switch on the pilot's radio. When it is false, every trip command is rejected.
- `current_pad` is null while the drone flies or when it is not on a known pad.
- `can_goto` lists the pads that have an approved route from the current pad.
- `trip.state`: `idle`, `starting`, `uploading`, `enroute`, `landing`, `arrived`, `holding`, `returning`, `failed`, `pilot` (the pilot took control).

## For the backend team: trip commands

Auth: `Authorization: Bearer <COMMAND_TOKEN>`. This token is separate from `READ_TOKEN`. Give it only to the backend service, not to app clients.

### `POST /v1/drones/packet-v0/commands`

| Body | What the drone does |
|---|---|
| `{"action": "goto", "pad": "uplace"}` | Takes off from its pad, flies the approved route, lands on the pad. |
| `{"action": "hold"}` | Stops and hovers where it is (LOITER). |
| `{"action": "resume"}` | Continues the trip after a hold. |
| `{"action": "return"}` | Flies back to the pad it took off from and lands (RTL). |

The reply is `202` with the command:

```json
{ "command": { "id": "cmd_mh2k3x9a1b2c3", "action": "goto", "pad": "uplace", "status": "queued",
               "reason": null, "created_at": "...", "updated_at": "..." } }
```

`409` means the drone is offline: no data from the laptop, or the laptop has no radio link to the drone.

### `GET /v1/drones/packet-v0/commands/<id>` and `GET /v1/drones/packet-v0/commands`

Read one command, or the last 20. `READ_TOKEN` or `COMMAND_TOKEN`.

Command `status`:

| Status | Meaning |
|---|---|
| `queued` | Waiting for the laptop (it picks up commands about once a second). |
| `delivered` | The laptop has it. |
| `rejected` | The drone side refused it. `reason` tells why: SA off, not on a pad, no approved route, battery under 60%, GPS, already flying. |
| `accepted` | Accepted (hold, resume, return). |
| `in_progress` | The trip is running. |
| `holding`, `returning` | After a hold or return command. |
| `done` | Landed on the destination pad. |
| `failed` | The trip stopped. See `reason`. |
| `stopped_by_pilot` | The pilot took control (SA off or mode switch). |
| `superseded` | A newer command replaced it before the laptop picked it up. |
| `expired` | The laptop did not pick it up in 15 s. |

### How a trip works

1. A pilot teaches each route once: the laptop records a hand flight from pad to pad, then builds the route and its reverse.
2. A person checks the route on the ground control map and approves it.
3. With SA on, the backend sends `goto`. The laptop checks the rules, uploads the route to the Pixhawk, and starts it.
4. The pilot can take control at any time: turn SA off, or move the mode switch. If the laptop link is lost, the drone continues the trip and lands.

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
COMMAND_TOKEN=dev-command-token
```

### Deploy (Cloudflare Workers Builds, from GitHub)

Each push to `main` deploys the Worker. Set it up one time in the Cloudflare dashboard:

1. **Workers & Pages** → **Create application** → **GitHub**. Authorize the Cloudflare GitHub app for `sanjanas18/packethw`. The repo owner, or a repo admin, must approve this.
2. Select the `packethw` repository and set these build settings:

   | Field | Value |
   |---|---|
   | Project / Worker name | `packet-telemetry`. It must be the same as `name` in `wrangler.jsonc`, or the build fails. |
   | Git branch | `main` |
   | Root directory | `cloud/telemetry-api` |
   | Build command | empty |
   | Deploy command | `npx wrangler deploy` (default) |
   | Build watch paths, if shown | include `cloud/telemetry-api/*`, so changes to other folders do not redeploy |

3. Select **Save and Deploy**.
4. Go to the Worker → **Settings** → **Variables & Secrets**. Add three values of type **Secret**:
   - `INGEST_TOKEN`: a long random string. The laptop uses it.
   - `READ_TOKEN`: a different long random string. Give it to the app team.
   - `COMMAND_TOKEN`: a third long random string. Give it only to the backend service that sends trip commands.

   Do not put these in **Build variables and secrets**. Those values exist only during the build, not when the Worker runs. Until you set the secrets, every request gets `401`.
5. Check the deploy: `curl https://packet-telemetry.<account>.workers.dev/v1/health`

To make a random token: `openssl rand -hex 32`

Manual deploy, if you need it: `npx wrangler login`, then `npm run deploy`.

Then start the laptop server with the push on:

```bash
export PACKET_INGEST_TOKEN=<INGEST_TOKEN>
.venv/bin/python ground_control/server.py --cloud-url https://packet-telemetry.<account>.workers.dev
```

The top bar of the ground control page shows `Cloud OK` when the pushes succeed. If the push fails, flight control is not affected.
