# Flight data through the Pi

The Pi is the primary recorder. `packet-flight-recorder` subscribes to position,
position target, battery, vibration, servo outputs and attitude target on its
own FC link while disarmed. It never arms, changes modes, or changes parameters.
Existing camera attitude traffic remains at its configured rate.

While armed it writes a standard timestamped `telemetry.tlog` under
`~/flight-data/telemetry/<flight>/`, including five seconds before arm. On the
first FC disarmed heartbeat it atomically publishes `summary.json`: voltage,
FC-estimated tracking, and camera-derived tracking if the matching camera
recording and takeoff handover are available. Missing inputs produce an explicit
unavailable result, never zero error. Heartbeat loss is not treated as landing.
The camera comparison covers handover +1 second through disarm, including
moves and landing; this is not the simulator's fixed-height hold metric.
The camera is the control sensor, not independent position ground truth.

Run on the laptop:

```
python tools/flight_sync.py --out logs/pi
# macOS: install it as a persistent login service, including JPEG archiving
python tools/install_flight_sync.py
```

This mirrors telemetry, CV JSON and summaries over Wi-Fi every two seconds,
while a separate worker copies completed onboard logs. JPEG transfer is optional
(`--frames`) and follows the onboard logs in that worker. Disconnection is retried; the Pi keeps the original files. These are target
latencies, not a real-flight latency qualification. Bulk file copies do not block the summary polling loop. Camera retention is still the existing ten recordings;
keep the laptop synchronizer connected to archive those recordings.

`packet-log-download.timer` retries the newest five onboard logs after boot and
every 30 seconds after its previous download completes. MAVFTP uses at most four
239-byte reads outstanding, stops issuing requests on arming or a stale heartbeat,
and resumes its durable contiguous prefix after disarm. DataFlash downloads are
supplemental: high-rate IMU/controller analysis is not promised at landing.
The normal MAVLink log protocol remains available in `tools/log_download.py`.

`--bench-burst` is a manual maintenance accelerator, never used by the timer. It uses pymavlink burst/gap recovery; the normal background
mode uses acknowledged session resets and four bounded reads.
An FC burst already queued can continue for up to 478 KB after arm is observed;
do not use this option for concurrent flight testing. The transfer checks file
size, byte coverage and the FC's CRC32 before publishing a `.BIN`, then records
its SHA256 for laptop integrity checks. Partial transfers never masquerade as
complete `.BIN` files. Do not run two downloaders with the same MAVLink identity.

The tunnel routes bulk log/file replies only to their requesting local client;
camera and recorder processes no longer parse those bulk packets. Its receive
loops are bounded so neither FC traffic nor local traffic can starve the other.

Install the recorder script, both downloader scripts and the three systemd files
from `companion/systemd/`, then enable the recorder and download timer. Restart
the tunnel only when disarmed. No firmware or battery failsafes are changed.

Verification: `uv run --with pymavlink python tools/test_flight_pipeline.py`.
Tests use isolated local UDP endpoints and synthetic heartbeats, never the drone.
