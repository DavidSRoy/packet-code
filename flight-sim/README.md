# flight-sim

A closed-loop flight simulator for camera and compute experiments. The flight controller is the real ArduPilot firmware in software-in-the-loop. Drone motion comes from the fitted physics model. Camera frames are rendered in Isaac Sim, run through the same lid detector as the companion code, and the estimated position is fed back to the controller. The result shows how a camera and a compute profile affect a hover over the lid.

## Setup (once)

1. Copy `cluster.example.toml` to `cluster.local.toml` and fill it in. The file is git-ignored. Fields:
   - `ssh_alias`: host alias from `~/.ssh/config`.
   - `account`: Slurm account to charge jobs to.
   - `gpu_partition`: Slurm partition for GPU jobs.
   - `cpu_partition`: Slurm partition for CPU-only jobs.
   - `scratch_dir`: remote directory for images, builds, job inputs and outputs.
2. Open an SSH connection to the cluster with connection sharing on (`ControlMaster`). The tool never asks for a password; it uses the open connection. You need `uv`, `rsync` and `ssh` on your machine.
3. Run `uv run python -m flightsim bootstrap`. It pushes the source and runs `cluster/bootstrap.sh` as a CPU job: it pulls the Isaac Sim image, builds ArduPilot SITL and creates the Python environment, using the versions in `versions.toml`. It is safe to run again; finished steps are skipped. Run it again after changing `versions.toml`, because a hover refuses to start when the build does not match.

Running a job accepts the Isaac Sim licence on your behalf: the job passes `ACCEPT_EULA=Y` to the container.

## Commands

Run from `flight-sim/` with `uv run python -m flightsim ...`.

Hover at a height above the start, hold, descend:

```
hover --camera ov9281 --compute pi-zero-2w --height 0.5 --hold 30 --seed 0 [--name NAME]
```

Camera profiles are in `profiles/cameras`, compute profiles in `profiles/compute`. The command pushes the source, submits one GPU job, waits and fetches the results. A 30 s hover takes about 45 minutes, plus queue time, because a frame costs about 3 s to render. The cluster account may limit concurrent GPU jobs, so runs can queue.

Compare two result folders (B minus A):

```
compare results/RUN_A results/RUN_B
```

It prints each run's status, `xy_rms_mm`, `xy_max_mm` and the detection rate. The detection rate counts frames in the hold window (true height within 0.05 m of the target). If no frame reached the hold, for example because the controller disarmed early, it counts all frames and says so. A run with no score (the controller disarmed) shows `nan` for the position errors.

## Results

Results land in `flight-sim/results/NAME/` (git-ignored):

| file | content |
|---|---|
| `result.json` | status, event times, and the score (`xy_rms_mm`, `xy_max_mm`, ...) when the flight completed |
| `frames.csv` | one row per frame: detected, tag count, estimated and true position, error |
| `camera.mp4` | the frames the detector saw |
| `overlay.mp4` | the same frames with the detected tag outlines |
| `versions.json` | image digests, ArduPilot tag and commit, repo commit, seed, height, hold, profile names |
| `pip-freeze.txt` | every Python package the job ran with, with versions |
| `slurm-<id>.log` | the job's own output |
| `*.log.tail` | last lines of the run, physics, SITL and render logs, with paths removed |

## Measured results

Hover at 0.5 m, 30 s hold, seed 0, OV9281 profile at 1280x800, Pi Zero 2 W compute profile.

| run | xy_rms_mm | xy_max_mm | detection in hold |
|---|---|---|---|
| gate run | 5.818 | 10.761 | 100% |
| repeat 1 | 5.514 | 9.265 | 100% (303/303) |
| repeat 2 | 5.570 | 9.476 | 100% |

Repeatability, two figures:

- Same code, same seed (repeat 1 and repeat 2): 0.056 mm rms, 0.211 mm max, 0 points of detection.
- Across two commits that differ only by a watchdog change (gate run and repeat 1): 0.3 mm rms, 0 points.

Treat 0.3 mm rms and 0 points as the tolerance between runs of different code; differences smaller than that are noise.

Worse camera: the same lens at 320x200 (`ov9281-quarter`, a test fixture) was clearly worse. This is one run, not repeated. The detector's own 0.4 downscale is applied on top of the 320x200 frame, so it sees 128x80 pixels: the result is quarter resolution plus the detector's downscale, not quarter resolution alone. The controller disarmed 2.5 s after handover to the vision position ("no position"), so the run ended with status "disarmed in the hold" and no score. Detection over all 328 frames was 94.2% (309 detected), against 100% at full resolution. The largest position error was 581 mm, and the estimated start position was 24 mm off, against about 2 mm at full resolution. Nothing was tuned to produce this.

## Known limits

- The pose fix uses the simulator's true attitude at the exposure instant. Attitude-estimator error is not modelled.
- No weather or lighting changes yet. No motion blur and no rolling shutter.
- One lid layout.
- Rendering costs about 3 s per frame, so a 30 s hover takes about 45 minutes.
- The lid sticker is placed under the camera lens at rest, not under the centre of the drone, because the modelled gripper hides a centred lid at every height up to 1 m.
- Estimated position shows a bias of a few mm that grows with height. It comes from the detector running at 0.4 downscale with part of the lid hidden.
- The detection rate in the compute profile was measured with a different camera than the OV9281.
- The detection rate excludes exposures the camera model drops (`model.json` `drop_frac` 0.04): about 4% of exposures get no row in `frames.csv`.
- Other camera keys in `model.json` (rate jitter) still apply on top of the profile.
- The image truth check was run with a different camera mount than the hover uses.
- The OV9281 lens has not been calibrated. The 70 degree field of view is an estimate.
- Position error is measured against the simulator's truth, not against a real flight.
