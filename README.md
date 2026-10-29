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

Box camera video in the field: the Mac makes a Wi-Fi network with Internet Sharing and the Pi joins it (see [companion/README.md](companion/README.md#video-in-the-field-the-macs-wi-fi-network)).

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

## Automatic legal ceiling (`airspace/`, `ground_control/ceiling.py`, `lua/ceil_guard.lua`)

Ground control finds the legal maximum height at the drone and sets the FC altitude fence (FENCE_ALT_MAX) to it, 2 times per second.

| Rule | Source |
|---|---|
| 400 ft above the ground, or 400 ft above the top of a building within 400 ft (14 CFR 107.51(b)) | USGS 3DEP ground, OpenStreetMap building heights |
| 100 ft under a Class B / C shelf floor | FAA Class_Airspace |
| NO-FLY in a Class B/C/D or E2 surface area without a stored ATC authorization (14 CFR 107.41) | FAA Class_Airspace, page **Events** |
| NO-FLY in an active TFR (also 10 min before it starts) | tfr.faa.gov, refreshed every 5 min |
| NO-FLY 3 NM around a stadium, 1 h before to 1 h after a game (FDC 4/3621) | game times entered on the page |

- The ceiling at a point is the lowest value within 60 m, so the fence comes down before the drone gets to a lower area. A NO-FLY area starts at its exact edge; the horizontal guard (below) stops the drone before it.
- **Keep-out zones**: circles the operator adds on the page (**Events**). They are NO-FLY until removed.
- The fence is in m above home (FENCE_ALT_MAX_TP = 1): ceiling - home height - 10 m margin. Home height is the ground, plus the roof when home is inside a building outline, plus `--home-offset`.
- The laptop refuses a takeoff, and the backend refuses a trip, in a NO-FLY area, on a route within 50 m of one, or on a route above the ceiling.
- The page shows the ceiling, the fence sent and the fence on the FC. **Layers** shows the ceiling map, airspace, TFRs and stadiums. **Probe** shows the ceiling at a clicked point. **Events** adds stadium games and ATC authorizations.
- First start downloads about 30 MB to `airspace/cache/` (about 2 min). Later starts use the cache.

On the FC, `lua/ceil_guard.lua` applies the value:

- It sets FENCE_ALT_MAX in RAM (not saved), so the flash is not written all the time.
- It never puts the fence under the drone. When the drone is above a new, lower ceiling, the fence stays 6 m (plus 3 s of climb) above the drone and follows it down. There is no sudden breach and RTL.
- Above the ceiling by more than 1 m in flight, the FC changes to GUIDED, holds position and descends to 2 m under the ceiling, then holds there (CEIL_DESCEND = 1). It takes over STABILIZE, ALT_HOLD, AUTO, GUIDED, LOITER, POSHOLD, BRAKE and an RTL that the altitude fence started. It does not stop a failsafe RTL, SMART_RTL or LAND. When the pilot changes the mode during the descent, it stops for 30 s and the pilot flies.
- Link lost for 5 s: it uses the fallback (400 ft above the lowest ground within 3 km, under any Class B floor), or the last value if that is lower. With no data since boot: CEIL_DEF_M (100 m).
- **Horizontal NO-FLY guard** (CEIL_NF_ENABLE = 1): ground control also sends the nearest NO-FLY edge within 2 km (CEIL_NFD distance, CEIL_NLA / CEIL_NLO edge point). The FC keeps a safe lower bound of the distance (distance sent, less the distance flown since then, less 1 s at the present speed). When the stop distance toward the edge (v² / (2 × CEIL_NF_DECEL) + 0.5 s × v) would end within CEIL_NF_BUF (20 m) of the edge, it stops the drone: GUIDED holds the position; STABILIZE, ALT_HOLD, AUTO, LOITER and POSHOLD change to BRAKE. It does not stop RTL, SMART_RTL or LAND. Flight away from the edge is free. With no fresh edge data, the guard is not active.
- Params: CEIL_ENABLE, CEIL_DEF_M, CEIL_TOUT_S, CEIL_MARGIN, CEIL_GCS (254 = this server), CEIL_DESCEND, CEIL_NF_ENABLE, CEIL_NF_BUF, CEIL_NF_DECEL. The CEIL_NF_ params need one FC reboot after an update from the 6-param script; until then the guard uses the defaults.

`--ceiling off` stops the sending; the FC then uses the fallback. Set CEIL_ENABLE = 0 to turn the script off.

Tests: `python -m airspace.test_ceiling` (22 checks) and `python tools/sim/ceiling_test.py --ardupilot ~/ardupilot-x650/ardupilot` (SITL, 26 checks). The SITL test flies `tools/sim/x650.json`, a model of the real drone from the flight logs (2.92 kg, 6S, hover throttle 0.26; SITL gives 0.27).

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
