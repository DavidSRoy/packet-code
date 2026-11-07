# Imperceptible-hover requirement: not met

**V7 remains an experimental baseline. The 20.3% band-RMS improvement is not acceptance of the user’s still-hover requirement. No new tune has been deployed.**

Provisional engineering target: at least 20 s of settled hold, under 0.1° peak-to-peak on each roll/pitch/yaw axis and under 2 mm peak-to-peak on each XYZ axis. This is not a validated human-perception threshold; viewing distance and visual validation still matter.

## Diagnostic results

All 27 diagnostic and feedback-search hovers completed, but **0/27 passed the absolute-motion gate**. Measurements use the full settled hold window, approximately 28 s, including slow sway and vertical bobbing. Counterfactual noise-free cases are diagnostic experiments, not predictions achievable by changing a flight parameter.

| Exploratory case | Max roll/pitch peak-to-peak (°) | Max XYZ peak-to-peak (mm) | Pass |
|---|---:|---:|---|
| baseline | 1.611 | 14.92 | no |
| quiet_camera | 1.565 | 12.79 | no |
| no_torque | 1.188 | 13.71 | no |
| no_force | 1.213 | 9.47 | no |
| no_disturbance | 0.627 | 11.44 | no |
| quiet_imu | 1.609 | 14.60 | no |
| ideal_camera | 1.530 | 11.81 | no |
| ideal_all | 0.063 | 4.70 | no |
| gentler_position | 1.431 | 37.15 | no |

The ideal-all case passes the angular and horizontal subtargets, but its vertical range remains 4.70 mm over this window. It removes all modeled external disturbances and sensor noise, so it must not be sold as realistic performance.

## Additional-seed confirmation

These runs retain the disturbance processes and set selected amplitudes to zero, preserving their random-number draws. The first exploratory runs removed processes; differences from those runs are not exact paired causal contributions.

| Case | Max roll/pitch peak-to-peak across seed 2 / seed 3 (°) |
|---|---:|
| baseline | 1.438 / 1.585 |
| quiet_camera | 1.357 / 1.570 |
| no_torque | 1.000 / 1.201 |
| no_force | 1.089 / 1.093 |
| no_disturbance | 0.704 / 0.679 |

## What this establishes

- Eliminating camera noise alone is insufficient in the current model; eliminating IMU noise alone also barely changes the exploratory outcome.
- Gentler position gains do not solve stillness: the exploratory XY RMS grows from 4.39 mm to 12.03 mm while substantial rocking remains.
- Modeled force/torque disturbances and feedback noise both contribute. Their effects are nonlinear and cannot be added as independent percentages.
- This is not evidence of a specific hardware fault. Disturbance amplitudes are inherited assumptions partly fitted to older flights, and the latest model identification remains uncertain. The results do not prove that gain tuning alone is mathematically incapable of meeting the target.
- A scalar percentage improvement or merely staying airborne is insufficient. The absolute gate must pass before claiming the stillness objective has been achieved.

## Remaining work

Identify the real source of persistent motion with synchronized high-rate attitude/rate/motor logs and an independent visual reference. A controlled height comparison can help test the ground-effect/propwash hypothesis; motor/prop/frame checks can test mechanical forcing. Neither cause is established by these simulations. Distinguish commanded corrections from actual attitude tracking error before selecting another controller change.

Position holding and attitude holding interact through the motor controller; see [ArduPilot attitude-control architecture](https://ardupilot.org/dev/docs/apmcopter-programming-attitude-control-2.html). Filtering pose measurements or weakening position gains can reduce one symptom while worsening position hold, so both absolute metrics remain acceptance criteria.

No physical test was commanded and no FC/Pi configuration changed. The next physical measurement must establish the remaining cause and demonstrate visual stillness; the simulator is not independent proof of real position accuracy.

## Verification

27/27 simulated diagnostic and feedback-search hovers produced metrics; 0/27 meet the full target. Three acceptance-function tests pass, including thresholds, short windows, missing axes and nonfinite data. `measure.py ... --require-target` correctly exits 1 for the current results. Python compilation passes. Reproduction commands and caveats are in `README.md`.

## Further feedback search — still in progress

Eight additional cases adjusted velocity measurement noise, removed velocity fusion, changed velocity-error filtering, reduced integral/position gains, or increased velocity gain. None met the absolute target. Lowering the velocity filter to 2 Hz worsened rocking to 2.16° roll / 1.94° pitch peak-to-peak. These are rejected experiments, not a revised flight tune. Exact inputs and outcomes are in `feedback.json` and `feedback_metrics.json`.

The latest real fixed-target window itself commands 1.249° roll and 0.917° pitch peak-to-peak, versus actual 1.440° / 1.240°. Rate tracking error is about 0.181° RMS per axis. Both commanded corrections and tracking error need work. Velocity-loop P contributes most of the 1–3 Hz commanded correction; this does not distinguish actual motion from estimation noise. `real_loops.py` reproduces those measurements from log49.

**V7 work remains open.** No current candidate meets the requirement, and no physical qualification is claimed.
