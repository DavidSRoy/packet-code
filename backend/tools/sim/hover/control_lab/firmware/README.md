# Experimental predictive attitude controller — SITL only

This overlay is AI-assisted experimental code for an isolated ArduPilot source
copy at `fb773567896014da007bca58358704d4a0d8516f`. It does not constitute a
flight-qualified controller. The header deliberately rejects non-SITL builds.
It occupies the existing empty custom-controller backend; no hardware parameter
file enables it.

The controller runs at 400 Hz and uses AHRS angles, measured gyro rates, its own
command history, and the ordinary ArduPilot attitude reference. Each axis has a
Kalman observer with delayed motor response and two torque-disturbance states.
The motor command is limited before propagating the observer. Roll/pitch use
K=73.5; yaw uses K=8, with the simulator's respective disturbance amplitudes.
These are model assumptions, not newly identified physical parameters. The
observer also models the measured simulated gyro-path delay with three 400 Hz
history states (7.5 ms); physics and disturbances are unchanged.

Three fixed effort weights are selected with `CC1_PARAM1`: 0 = 0.01, 1 = 0.001,
2 = 0.0001. `CC1_PARAM2` limits each axis's output, default 0.15. `CC_TYPE=1` and
`CC_AXIS_MASK=7` select this experimental backend in the copied simulator.
The local driver activates it explicitly and requires both acknowledgment and
activation text before attempting its simulated takeoff. `PKLQ` records the bank
and outputs at 10 Hz; the scorer checks its presence throughout the hold.

The matrices use simplified independent angle/gyro noise and a first-order gyro
filter plus the explicit observation delay. Actual ArduPilot filtering and AHRS correlations differ. Euler/body-rate
coupling is approximated for small-angle hover. `CC1_PARAM3=1` enables feedforward from the shaped attitude-rate reference;
reference acceleration preview is not implemented. The observer tracks its clipped command,
but not downstream mixer allocation or motor saturation. These limitations must
be evaluated; do not assume the isolated linear gains transfer to full flight.

## Reproduce

1. Create a separate local copy of the pinned ArduPilot source, including its
   submodules. Preserve the original simulator build.
2. From Packet's `backend`:

```sh
uv run --with-requirements requirements.txt --with scipy python tools/sim/hover/control_lab/firmware/generate.py
python3 tools/sim/hover/control_lab/firmware/install_overlay.py /absolute/path/to/source-copy
```

3. Build from the source copy with the ArduPilot Python environment:

```sh
LDFLAGS=-Wl,-no_fixup_chains python ./waf configure --board sitl
python ./waf copter -j 8
```

The `LDFLAGS` setting is for this Mac's linker, matching the original simulator
build's workaround for unaligned packed firmware-version metadata; omit on
other platforms.

4. From Packet's `backend`:

```sh
ARDUPILOT=/absolute/path/to/source-copy uv run --with-requirements requirements.txt python tools/sim/hover/batch.py tools/sim/hover/control_lab/full_sitl.json --jobs 4
uv run --with-requirements requirements.txt python tools/sim/hover/control_lab/score_full_sitl.py tools/sim/hover/control_lab/full_sitl.json --require-target
```

The target command must fail unless every required absolute-motion gate passes.
The direct harness force-disarms after descent; it does **not** qualify normal
FC-controlled landing. These runs do not connect to the drone or ground control.
