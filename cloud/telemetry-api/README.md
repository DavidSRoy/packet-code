# Packet telemetry API

Cloudflare Worker with one Durable Object per drone. The laptop ground control server pushes the drone state once each second. The app team reads it here.

```
drone ──radio──> laptop ground_control/server.py ──HTTPS POST 1 Hz──> Worker ──> app
```

## Reliability: read this first

| Data | Path | Reliable? |
|---|---|---|
| Everything in `/position`, `/state`, `/track`, `/messages`, the `/stream` WebSocket, and commands | Drone → telemetry radio → laptop → API | **Yes.** This is the data to build on. |
| `box_camera` (box pose from the drone's camera) | Pi → FC → telemetry radio → laptop → API | **Yes**, while the camera sees the box tags. |
| Radio snapshots: `/snapshot` (small box camera pictures) | Pi → FC → telemetry radio → laptop → API | **Yes, but slow**: a few seconds per picture, only while the Pi is not on Wi-Fi. |
| `/routes`, `/airspace/*` (files from the laptop) | laptop → API | **Yes**, the laptop uploads them when they change. |
| Camera video: `/camera.h264`, `/camera/stream` | Pi → **Wi-Fi** → laptop → API | **No. Best effort only.** |

The camera frames come only while the laptop reaches the drone's Pi over Wi-Fi. They drop out often: Wi-Fi range, a laptop off the network, a slow upload. The API marks this in the `camera` block (`best_effort: true`, `live`). Never make a flight decision, a trip step or an alarm depend on the camera frames. Show them as a "when available" view only. For the box position, use `box_camera`.

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
  "gps": { "fix_type": 3, "satellites": 18 },
  "pilot_radio": { "link_ok": true, "rssi": 200, "kill_switch_on": false, "backend_switch_on": true },
  "fence": { "enabled": true, "radius_m": 50 },
  "box_camera": {
    "source": "radio", "age_s": 0.4,
    "box": { "id": 1, "tags": null, "ntags": 2, "px_per_cell": 28.7,
             "drone_m": [0.224, -0.011, 0.267], "camera_m": [null, null, 0.241],
             "yaw_deg": 178.9, "tilt_deg": 3.5 }
  },
  "camera": { "best_effort": true, "live": false, "laptop_forwarding": false,
              "last_frame_at": "2026-10-26T04:23:58.119Z", "frame_age_s": 13.9,
              "format": "H.264 (Annex B), 1280x720, about 10 fps",
              "frame_url": "/v1/drones/packet-v0/camera.h264", "stream_url": "/v1/drones/packet-v0/camera/stream",
              "note": "Best effort: ..." },
  "messages": [ { "time": "2026-10-26T04:23:46.590Z", "severity": 2, "text": "PreArm: Radio failsafe on" } ]
}
```

`gps` also has the GPS quality:

| Field | Meaning |
|---|---|
| `quality` | `good`, `poor` or `bad`. `bad` is normal indoors and near tall buildings. Do not trust the position to a few metres unless it is `good`. |
| `reasons` | Why, for example `"6 sats"`, `"±12 m"`, `"FC: GPS glitch"`, `"jump filtered"`. |
| `accuracy_m` | The GPS horizontal accuracy (1 sigma, m). Draw it as a circle around the drone. |
| `position_filtered` | `true` when the laptop holds the position because the FC position made a jump that is physically impossible. `position` is then the held, plausible position. |
| `fc_position` | The FC's own position, not filtered. |

How the laptop filters `position` (ground_control/gps_guard.py): on the ground, when the gyros show the drone does not move, it ignores GPS jumps and keeps a steady position. When the drone is carried, it follows at walking speed at most. In flight, it follows the FC and hides only single jumps larger than the speed allows. With a `good` GPS, it uses the FC position directly.

`attitude` also has `yaw_deg` (the nose direction, 0–360). `battery` also has `capacity_mah` and `time_left_basis` (`flight`, `last flight` or `hover estimate`).

| Block | Meaning |
|---|---|
| `pilot_radio` | The pilot's RC link. `kill_switch_on` is the SD switch (motor stop). `backend_switch_on` is the SA switch (backend trips allowed). |
| `fence` | The FC geofence: on or off, and the circle radius. |
| `box_camera` | The full box camera telemetry. See below. |
| `camera` | Status of the best-effort camera frames. See below. |
| `radio_snapshot` | The last box camera picture that came over the telemetry radio: `available`, `frame`, `captured_at`, `age_s`, `bytes`, `content_type`, `url` (`GET` it), and `radio` (the snapshot link: `state` `wifi` / `on` / `telemetry first`, `rate_pps`, `loss_pct`, `period_s`, `rx_bps`, the frame being received). |
| `lights` | The arm lights: `mode` is `status`, `aviation`, `landing` or `off`; `sb_pwm` is the SB switch value. |
| `ceiling` | The legal ceiling and no-fly guard from the laptop: `status`, `target_m` (height limit above home), `fallback_m`, `nofly`, `edge` (nearest no-fly edge: `lat`, `lon`, `dist_m`, `inside`), `home_amsl` and `home_src`, `here` (the airspace answer at the drone: class, limits, reasons), `fc` (what `ceil_guard.lua` on the FC reports), `map` (age of the airspace data). |
| `laptop` | The laptop side: `taking_off`, `takeoff_target_m`, `speed_limits` (the page sliders, m/s and deg/s), `camera_forwarding`, `pi_url`, `log_file`, `sa_channel`, `sa_pwm`, `gps_positions_rejected`. |
| `files` | When the laptop last uploaded the routes and the airspace map, with their URLs. `null` before the first upload. |
| `messages` | The last 10 FC text messages (pre-arm checks, fence, failsafes). Severity: 0 emergency … 2 critical … 4 warning … 6 info. |

`gps` also has `positions_rejected` (GPS jumps the laptop filter threw away since it started).

`box_camera` comes over the telemetry radio (`source: "radio"`, about 2 per second), or over Wi-Fi with more detail (`source: "wifi"`). Both have the full pose.

| Field | Meaning |
|---|---|
| `source`, `age_s`, `detection_hz` | Where it came from, its age, and the detections per second. |
| `box` | The first box in view, `null` when no box tag is in view. Same as `boxes[0]`. |
| `boxes` | Every box in view (the radio sends one, Wi-Fi all). |
| `box.drone_m` | The drone centre in the lid frame: origin at the lid centre, x along the long side, y along the short side, z up, m. |
| `box.camera_m` | The camera in the lid frame, m. |
| `box.yaw_deg`, `box.tilt_deg` | The drone nose direction from the lid +x axis (counter-clockwise), and the drone tilt. |
| `box.rvec`, `box.tvec` | The full lid → camera pose (OpenCV Rodrigues rotation vector, and the lid origin in the camera frame, m). With these an app can draw the tags on the picture. |
| `box.range_m` | Camera to lid distance, m. |
| `box.id`, `box.ntags`, `box.px_per_cell` | Box number, tags seen, tag size in the picture. |
| `box.tags`, `box.outlines` | Tag names and their outlines in the picture (px). Wi-Fi only, `null` over the radio. |
| `camera` | Camera details: `name`, `hfov_deg`, `width`, `height`, `frames`, `mount`, `error`. Wi-Fi only. |
| `messages` | The last 10 FC text messages (pre-arm checks, fence, failsafes). Severity: 0 emergency … 2 critical … 4 warning … 6 info. |

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

### `GET /v1/drones/packet-v0/messages?since=<ms or ISO time>&limit=<n>`

The FC text messages, kept for 24 h. The default is the last hour. `limit` is 1–2000, default 200.

```json
{ "drone_id": "packet-v0", "count": 1, "messages": [
  { "time": "2026-10-26T04:23:46.590Z", "severity": 2, "text": "PreArm: Vehicle breaching Circle fence" } ] }
```

### Camera (best effort, not reliable)

The video is H.264 from the Pi's hardware encoder (1280×720, about 10 fps, about 1.5 Mbit/s, a keyframe each second). The API does not re-encode it.

- `GET /v1/drones/packet-v0/camera.h264`: the video from the last keyframe to now, as raw H.264 Annex B (`video/h264`). It always starts with a keyframe, so any H.264 decoder shows the latest picture (for example `ffplay camera.h264`, or decode the last frame). Auth: Bearer `READ_TOKEN`, or `?token=READ_TOKEN`. Headers: `X-Frame-Time` (time of the last POST), `X-Frames`. It gives `503` when no video came in the last 5 s. Expect `503` often.
- `wss://<base>/v1/drones/packet-v0/camera/stream?token=<READ_TOKEN>`: live video, one binary message per frame. The first message is a keyframe. Each message is one frame record:

  | Bytes | Content |
  |---|---|
  | 4 | data length, big-endian |
  | 1 | flags: 1 = keyframe (SPS and PPS in front of it) |
  | 8 | capture time, ms since epoch, big-endian float64 |
  | rest | one H.264 Annex B access unit |

  In a browser, decode with WebCodecs: `new VideoDecoder(...)`, `configure({ codec: "avc1.PPCCLL" from the SPS, optimizeForLatency: true })` with no `description` (Annex B), then one `EncodedVideoChunk` per message. `ground_control/static/index.html` (`play()`) does this. Nothing comes while the camera is down. The socket stays open.
- The `camera` block in `/state` says if video comes now (`live`) and the age of the last frame.
- The API keeps only the frames since the last keyframe, in memory. There is no recording.

### Radio snapshots: `GET /v1/drones/packet-v0/snapshot`

The last box camera picture that came over the telemetry radio (WebP, about 320×180, about 2 KB). The Pi sends them while it is not on Wi-Fi, a few seconds per picture, and only while the telemetry has room. Auth: Bearer `READ_TOKEN`, or `?token=READ_TOKEN` (for `<img src>`). Headers: `X-Frame` (picture number), `X-Frame-Time` (capture time). `404` before the first picture. The stream sends `{"type": "snapshot", "data": {...}}` when a new one is there: fetch it then.

### Routes and pads: `GET /v1/drones/packet-v0/routes`

What the laptop has: `pads` (id, name, lat, lon), `routes` (each with `from`, `to`, `approved`, `problems`, `length_m`, `est_time_s`, `max_alt`, `takeoff_alt`, and `path` as `[lat, lon]` points), `recording` (a route recording in progress) and `sa_channel`. The laptop uploads it when it changes.

### Airspace map

- `GET /v1/drones/packet-v0/airspace/layers`: the airspace data the laptop's map shows, as JSON: `status` (data ages), `bounds`, `classes` and `uasfm` (airspace class and UAS facility map areas), `tfrs`, `stadiums`, `auths`, `events`, `zones`.
- `GET /v1/drones/packet-v0/airspace/overlay.png`: the ceiling map picture. `X-Bounds` gives its corners (`[[south, west], [north, east]]`). `?token=` works.

The laptop uploads these when its map changes (it checks each minute). The airspace answer for the drone's position is in `ceiling.here` in `/state`.

### Live stream: `wss://<base>/v1/drones/packet-v0/stream?token=<READ_TOKEN>`

- When you connect, you get the current state. Then you get each update, about once each second, in the same shape as `/state`: `{"type": "state", "data": {...}}`. New radio snapshots come as `{"type": "snapshot", "data": {...}}`.
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
- `recording` is the route recording in progress (`from`, `to`, `phase`, `samples`), or `null`. The full routes are at `GET /routes`.

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

The server also forwards the Pi's H.264 video when it reaches the Pi over Wi-Fi: `--pi-url` (default `auto`, the address the Pi sends over the radio; `none` to turn off) and `--cloud-cam` (default 1, 0 to turn off). It POSTs the Pi's frame records to `/camera` unchanged, about every 0.5 s: about 190 KB/s of upload. The camera has its own thread, so a lost camera does not delay the telemetry.
