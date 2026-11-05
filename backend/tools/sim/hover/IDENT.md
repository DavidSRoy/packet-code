# Hover simulator: identified model values

Source data: dataflash logs `logs/bin/2026-10-29 .. 2026-11-03` (00000018-00000045) and the Pi
recordings `logs/rec/2026110*/cv.jsonl`. Raw results: `ident_logs.json`. Values in `model.json`.
Analysis scripts that are not in the repo (one-off fits) are named below with what they did.

## Rotation (roll, pitch, yaw)

Model: angular acceleration = K x u(t - d), first-order lag tau, plus bias and disturbance.
u = RATE.ROut / POut / YOut, rate from RATE.R / P / Y (after the gyro filter).

| Axis | K (rad/s^2 per unit) | Total delay | Split (lag + pure delay) | Confidence |
|---|---|---|---|---|
| Roll | 77 (70-83) | 52 ms (45-55) | 10 ms + 35 ms (log 45) | high (K, total); medium (split) |
| Pitch | 73 (68-80) | 52 ms (48-57) | 30 ms + 23 ms (log 45) | high (K, total); medium (split) |
| Yaw | ~8 (4-14) | ~30 ms | - | low (R^2 <= 0.16) |

The delay includes the motor, ESC and propeller response, the 40 Hz gyro filter and notch, and
the loop timing. The model uses a 20 ms lag + 30 ms pure delay on all axes. Inertia in
`model.json` is set so that torque per unit output (0.4596 x thrust_full = 11.89 N m) / inertia = K.
The CAD inertia (0.068 / 0.070 / 0.110) does not agree with these K values; the sim uses K.
Direct frequency-domain fits gave K 146-188 with 16-26 ms; feedback biases them, so they are not used.

## Thrust, hover and ground effect

| Value | Result | Source |
|---|---|---|
| Hover throttle out of ground effect | 0.2769 | CTUN.ThO, hovers above 6 cm |
| MOT_THST_EXPO | 0.65 | flown parameter |
| Ground effect | k(h) = 1 + 0.038 exp(-h / 2.8 cm), h above the resting height | ThO vs height, 277 chunks; medium-low |
| Thrust axis trim | +0.84 to +0.87 deg pitch, ~0 deg roll | ATT and PIDN/PIDE I terms in the hovers of logs 43 and 45 |

The trim: in the hold, ArduPilot holds +0.8-0.9 deg nose-up with a velocity I term of
-0.15 m/s^2 north (yaw ~350 deg). The thrust has a forward part of about 1.5 % when the IMU is
level. Model: `thrust_axis_xy` [0.0153, 0.004].

## Geometry (CAD, Packet V0/05_viewer)

| Item | Relative to the CG (FRD, m) |
|---|---|
| Rotors | (+-0.23, +-0.23, -0.08) |
| Skids (bottom) | x +-0.163, y +-0.159, z +0.30 |
| IMU | (-0.007, -0.001, -0.058); z also from the logs: -0.058 (-0.063 to -0.049), x and y not identifiable from the logs |
| Box camera lens | (0.127, -0.001, +0.101) |

The Pi assumes the lens at `--mount-fwd 0.134 --mount-down 0.02` from its drone point. So the
point it reports is 8.1 cm below the CG (`camera.pi_cam_pos_err`).

## Disturbances

From the residual (measured angular / linear acceleration minus the model), by band:

| Band | Roll (rad/s^2) | Pitch (rad/s^2) | Horizontal (m/s^2) |
|---|---|---|---|
| 0.05-0.3 Hz | 0.22 | 0.16 | 0.006-0.012 |
| 0.3-1 Hz | 0.23 | 0.19-0.24 | 0.010-0.014 |
| 1-3 Hz | 0.23-0.25 | 0.26-0.30 | 0.03-0.05 |
| 3-6 Hz | 0.31-0.40 | 0.30-0.35 | 0.05-0.09 |

The sim uses sums of OU processes for these. The horizontal part is raised to 0.025 m/s^2
(tau 1 s) and the vertical to 0.06 m/s^2: with the identified 0.006-0.014 the sim held 2-3x
tighter than logs 43/45 with the same parameters. With 0.025 the sim FC position error (hold window,
`compare.py`) is 6.1 mm (log 43 parameters) and 6.5 mm (log 45) mean of N and E, against 7.2 and
11.0 mm real. The real East error is 2x the North error in both logs; the sim is symmetric.

## IMU noise

Gyro 0.004-0.006 rad/s/sqrt(Hz) in hover; accel 0.010-0.034 m/s^2/sqrt(Hz), raw RMS 2-4 m/s^2
(motor harmonics 56-62, 119, 175, 238 Hz). Sim: SIM_ACC1/2_RND 0.8, SIM_GYR1/2_RND 0.3.
Accel noise has no measurable effect on the hold in the sim.

## Box camera

| Value | Result | Source |
|---|---|---|
| Rate | 10 Hz (1280x720 YUYV, C920 limit); arrival dt p99 104-136 ms, gaps to 300-400 ms | VISP |
| Static noise | 0.2-0.4 mm | still sets |
| Hover frame jitter | median 1.3 mm, p90 3.5-5 mm (includes real motion) | cv.jsonl |
| Sim noise | 1.0 mm xy, 0.6 mm z, 10 % of frames x4 | matches the VISION_SPEED spread of log 43 (sim 19-20 mm/s, real 23-25) |
| t_cap -> detection done | 52 ms (49-56) | cv.jsonl |
| t_cap -> FC arrival | 57 ms (55-66), jitter 4-5 ms | VISP, IMU-attitude clock match |
| FC dating | arrival - 71.5 ms (jitter correction 11.5 ms + VISO_DELAY_MS 60) | VISP.TimeUS vs CTimeMS |
| **Exposure -> t_cap (L)** | **60 ms (+-15)** | attitude-match fit, below |

### The exposure -> t_cap latency L

The Pi turns the tag pose into a drone position with the FC attitude at t_cap (`--imu-lag 0`),
but the image was taken at t_cap - L. When the drone rotates, the reported position has an
error H x (tilt(t_cap - delta) - tilt(t_cap - L)), with H = height of the Pi's drone point over
the sticker (|VISP.PZ|, 0.24-0.29 m) and delta = age of the FC attitude when the Pi gets it (~7 ms).
The 4 Hz ring in logs 41-45 makes this error large enough to fit.

Fit (`scratchpad latfit3.py`): VISP position (10 Hz, high-passed) against the tilt integrated
from the 400 Hz RATE log, at t_cap = arrival - 57 ms; the rotation lever fixed to H, an in-phase
lever free; grid over L. On sim logs with known L the method reads 10-20 ms low (true 30 / 50 / 70
/ 90 ms -> 20 / 30-40 / 50-60 / 80-90 ms). Real logs:

| Log | Best L | Corrected |
|---|---|---|
| 41 | 50 ms | ~62 ms |
| 42 | 50 ms | ~62 ms |
| 43 | 50 ms | ~62 ms |
| 44 | 40 ms | ~52 ms |
| 45 | 60 ms | ~72 ms |

L moves by less than 5 ms when the assumed t_cap -> arrival time changes by +-5 ms.
Independent check: the sim with the flown parameters reproduces the log-43 ring at L 50-70 ms,
and grows like log 45 at L 90 ms. Total exposure -> FC arrival: about 117 ms. The FC now dates
each fix 45 ms late. A light-toggle test on the Pi would measure L directly.

## What the calibrated sim reproduces (flown parameters, L 60 ms)

| Metric (hold window) | Real 43 | Sim (log 43 set) | Real 45 | Sim (log 45 set) |
|---|---|---|---|---|
| FC position error N / E rms | 4.3 / 10.1 mm | 6.7-7.4 / 4.9-5.5 mm | 6.8 / 15.2 mm | 7.0-7.8 / 5.1-6.1 mm |
| Roll / pitch rms | 0.25 / 0.22 deg | 0.30-0.36 / 0.42-0.46 deg | 0.40 / 1.08 deg | 0.33-0.41 / 0.49-0.51 deg |
| Velocity D-loop gain (roll) | 1.23 @ 4.0 Hz | 0.78-0.97 @ 3.6-3.7 Hz | 2.24 @ 4.5 Hz | 1.14-1.29 @ 3.7 Hz |

Known gaps: the sim ring is at 3.6-3.8 Hz (real 4.0-4.5 Hz), so the sim attitude response is a
little slow; the real 4 Hz ring in log 45 grew, the sim one at L 60 ms does not (it grows at L 90 ms);
the sim has no East/North difference.
