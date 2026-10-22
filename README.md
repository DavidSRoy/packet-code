# packethw

Software for the Packet V0 test drone: Holybro X650, Pixhawk 6X, ArduCopter 4.7.2.

## Setup (one time)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

All commands below run from this folder. Only one program can use the telemetry radio at a time.

## Laptop flight control (`ground_control/`)

```bash
.venv/bin/python ground_control/server.py
```

Open http://localhost:8650. QGroundControl can stay open: the server forwards all MAVLink to UDP 14550, and QGC connects to it by itself.

| Key / button | Action |
|---|---|
| W / S | Fly north / south |
| A / D | Fly west / east |
| Q / E | Turn left / right (does not change where W/A/S/D go) |
| Z / X | Up / down |
| Space or HOLD | Stop and hover |
| AUTO TAKEOFF | GUIDED, arm, climb to the set height (0.5–10 m) |
| AUTO LAND | LAND mode |
| RETURN HOME | RTL mode |
| KILL (hold 1 s) | Force disarm. The drone falls if it is in the air. |

- The keys are earth-fixed (compass), not nose-fixed.
- The keys work only when armed in GUIDED, after the takeoff height is reached.
- Releasing all keys brakes to a hover. If the page closes or loses focus, the drone brakes.
- Speed limits: 3 m/s horizontal, 1 m/s vertical, 45 °/s yaw. The sliders set lower values.
- Takeoff needs a 3D GPS fix with 8+ satellites, the Boxer on, and SD on run.
- Flick SC on the Boxer to take manual control at any time.

Options: `--port`, `--baud`, `--http`, `--qgc none`, `--cloud-url` (see below).

The page shows a satellite map with the drone, its heading, home, the geofence ring, the flown track and a 5 s lead line. The map tiles need internet. The rest of the page works offline.

## Cloud telemetry API (`cloud/telemetry-api/`)

This is a Cloudflare Worker that the app team reads for the drone position, state, track and live stream. The laptop server pushes to it once each second when it starts with `--cloud-url` and the env `PACKET_INGEST_TOKEN`. See [cloud/telemetry-api/README.md](cloud/telemetry-api/README.md).

## Logs (`logs/`, not in git)

| What | Where | How |
|---|---|---|
| Live telemetry, every MAVLink message | `logs/tlog/<date_time>.tlog` | Written by the server. Opens in QGC, Mission Planner or pymavlink. |
| GPS track (lat, lon, height, speed, mode, battery) | `logs/track/<date_time>.csv` | Written by the server |
| Full onboard flight logs (.BIN, all sensors at full rate) | `logs/bin/` | `tools/sync_logs.py`, after landing |

```bash
# USB, fast:
.venv/bin/python tools/sync_logs.py /dev/cu.usbmodem2101
# Telemetry radio, slow (about 4 KB/s), newest log only:
.venv/bin/python tools/sync_logs.py /dev/cu.usbserial-DU0E540E 57600 --latest 1
```

## SD kill switch guard (`lua/sd_guard.lua`)

This guard gates the SD motor kill by height, so a flick of SD by mistake at height does not drop the drone.

| Condition | SD to stop |
|---|---|
| Disarmed | E-stop on (blocks arming) |
| Height under `SDG_ALT` (2 m) | Motors cut |
| Tilt over `SDG_TILT` (60°) | Motors cut, at any height |
| SE also on (`SDG_SE_CH`) | Motors cut, at any height |
| Otherwise | Blocked. A warning goes to the GCS. Put SD back to run before it can work again. |

If the script stops with an error, it sets `RC8_OPTION = 31`, and SD becomes the plain kill switch again.

Test on the laptop: `lua lua/test/sd_guard_test.lua`

Install:

1. Upload the script:
   ```bash
   .venv/bin/python tools/mavftp_put.py /dev/cu.usbserial-DU0E540E 57600 lua/sd_guard.lua /APM/scripts/sd_guard.lua
   ```
2. Set `RC8_OPTION = 0`, then reboot.
3. Make sure that "SD guard on" shows in the messages.
4. Set `SDG_SE_CH` to the channel of SE on the Boxer.

## Motor map

The motor signal plugs are wired 180° from the ArduPilot Quad X order. The fix is in software: `SERVO1..4_FUNCTION = 34, 33, 36, 35`. If the parameters are reset, set these values again, or swap the plugs MAIN 1↔2 and MAIN 3↔4. The motor test and the props-off tilt test passed on 2026-10-22.
