# Hover simulator (box-camera hover, ArduCopter 4.7.2 SITL)

A software-in-the-loop copy of the `ground_control/hop.py` "Run test" hover: the real
ArduCopter 4.7.2 firmware (SITL), the real Lua scripts (`lua/hop_takeoff.lua`,
`lua/hop_guard.lua`, ...), the flown parameter set, and a physics model of the Packet V0
drone (X650, 6S) identified from the flight logs. The box camera is simulated as the Pi
sends it: VISION_POSITION_ESTIMATE + VISION_SPEED_ESTIMATE at 10 Hz with the measured
latency, jitter, drops and noise.

The score is on the TRUE trajectory of the simulated drone, not on the FC estimate.

## Files

| File | What it is |
|---|---|
| `physics.py` | Rigid body, motors (delay + lag, thrust expo), ground effect, skid contact, disturbances, IMU lever arm, camera model. ArduPilot JSON backend (UDP 9002 + 10 x instance). |
| `model.json` | Model values. Every identified value has a `_doc` line. Details: `IDENT.md`. |
| `run.py` | One run: starts SITL + physics, flies the hop.py sequence over MAVLink, scores the hold. Writes `runs/<name>/result.json` (+ `truth.npz`, the dataflash log path). |
| `batch.py` | Many runs in parallel from a JSON list, one table at the end. |
| `compare.py` | The same FC-side measurements on real and sim dataflash logs (position error, 4 Hz ring, velocity D-loop gain). |
| `extract_parm.py` | A flown parameter set out of a real `.BIN`. |
| `sim_base.parm` | Sim-only settings, loaded after the flown set (SITL sensors, no GPS, scripting). |
| `flown_log43.parm`, `flown_log45.parm` | Parameters flown in logs 43 and 45 (tune_v4, tune_v5). |
| `IDENT.md` | How each model value was identified, with the confidence. |
| `RESULTS.md` | tune_v6: results, robustness, test plan. |
| `errsplit.py`, `bands.py` | Split a run's error into estimate / control, and by frequency. |
| `e2e/run_e2e.py`, `e2e/fake_pi.py` | End-to-end test: the real `ground_control` server and `hop.py` fly SITL; a fake Pi serves the camera (instances 20-25, speedup 1). |
| `configs/` | Batch lists used for the calibration and the tuning. |

## Run

Needs the ArduPilot tree at `~/ardupilot-x650/ardupilot` (or `$ARDUPILOT`) with
`build/sitl/bin/arducopter` built, and a Python with `pymavlink` and `numpy`.

```bash
python tools/sim/hover/run.py --name test1 --height 0.02 --hold 30 --seed 1
```

```bash
python tools/sim/hover/batch.py tools/sim/hover/configs/c3.json --jobs 10 --compare
```

Options: `--flown FILE` (flown set), `--parm FILE` (extra parameter file, loaded last),
`--p NAME=VALUE` (one parameter), `--set key=json` (model value, e.g.
`--set camera.exposure_to_readout_s=0.03`), `--seed N`, `--instance N` (ports), `--speedup N`.
One 30 s hold takes about 45 s of wall time; 10 runs in parallel work on this Mac.
