# Log 45 (2026-11-03 14:32): growing 4.4 Hz roll/pitch oscillation

Log: `logs/bin/2026-11-03/00000045.BIN`. Compared with logs 43 and 44 (same day).
Tools: `tools/tuning/oscillation.py`, plus the band and loop-gain checks below.

## What happened

- Mode GUIDED. The HTO script took off (liftoff 2827.5 s) and gave control to the FC
  position controller at 2827.7 s. Position and velocity come from the camera
  (EK3 source set 2 = ExternalNav, VISO at 10 Hz).
- Roll and pitch oscillated at 4.3-4.4 Hz from about 3 s after liftoff. The
  oscillation grew during the 15 s flight:

| Time | Max roll / pitch | Max rate roll / pitch | Max ROut |
|---|---|---|---|
| 2828-2835 s | 1.4 / 2.3 deg | 17 / 22 deg/s | 0.12 |
| 2835-2840 s | 0.9 / 1.7 deg | 19 / 12 deg/s | 0.12 |
| 2840-2843 s | 8.6 / 10.6 deg | 126 / 189 deg/s | 0.45 |

- 2842.2 s: EKF3 lane switch (ERR 24). 2842.9 s: forced disarm over MAVLink
  (ARM Forced 1, Method 1).
- No vibration clipping (max 8 m/s^2 at the end). No parameter change between logs 44 and 45.

## Cause: the horizontal velocity D term (PSC_NE_VEL_D)

1. The rate demand (RATE.RDes) has the same 4.4 Hz motion as the measured rate.
   So the command comes from above the rate loop. The rate loop only follows it.
2. The Pi attitude commands (GUIA) stop at the hand-over and have almost no 4.4 Hz content.
3. In the velocity controller (PIDN/PIDE, 400 Hz) the D term is the largest term
   at 4-5 Hz, about 5x the P term:

| Log | PSC_NE_VEL_D | D term 4-5 Hz RMS | P term | Roll rate at 4.4 Hz |
|---|---|---|---|---|
| 43 | 0.75 | 0.03 m/s^2 | 0.008 | 3.3 deg/s (steady) |
| 44 | 1.0 | 0.03-0.04 m/s^2 | 0.006 | 3.1 deg/s (7 s flight) |
| 45 | 1.0 | 0.10 m/s^2 | 0.018 | 8.4 deg/s (growing) |

4. Loop gain through the D term: tilt commanded by the D term divided by the actual
   tilt, at the oscillation frequency:

| Log | Roll | Pitch |
|---|---|---|
| 43 | 1.28, -64 deg | 1.70, -63 deg |
| 44 | 2.72, -103 deg | 3.24, -107 deg |
| 45 | 2.25, -70 deg | 2.27, -68 deg |

   With correct kinematics (horizontal acceleration = g x tilt) this ratio is about
   PSC_NE_VEL_D x the FLTD filter gain, about 0.75 at VEL_D 1.0. The measured ratio is
   about 3x larger. So the EKF velocity has about 3x more 4.4 Hz motion than the tilt can make.

5. Probable source of the extra motion: IMU lever arm. INS_POS1_* and INS_POS2_*
   are all 0. When the IMU is not at the centre of gravity, a fast rotation gives a
   false linear acceleration (r x angular acceleration). At 4.4 Hz the angular
   acceleration is about 760 x the tilt, so a few cm of offset is enough. This is
   not yet measured on the drone.

The loop: tilt -> (true + lever-arm) acceleration -> EKF velocity -> D term -> tilt
command. With a gain above 1 and about 180 deg total phase at 4.4 Hz (this D path
plus the attitude response delay), the loop oscillates and grows. At VEL_D 0.75 (log 43)
it rang at about 3 deg/s and did not grow; tune_v5 (VEL_D 1.0) made it grow.

tune_v2..v5 were designed with a low-frequency position model
(tools/tuning/position_margins.py, 0.1-1 Hz). That model does not include this
high-frequency path, so its margins did not show this problem.

## Suggested next steps (not applied)

- Lower PSC_NE_VEL_D (back to 0.25, or 0 for a test), and/or lower PSC_NE_VEL_FLTD
  from 5 Hz to about 1-2 Hz, so the D term has little gain at 4 Hz.
- Measure the IMU position relative to the centre of gravity and set INS_POS1_X/Y/Z
  and INS_POS2_X/Y/Z (metres, body frame).
- Add the D-term path (acceleration feedback with the attitude response delay) to
  position_margins.py before the next position-loop change.

## Follow-up (hover simulator, same day)

`tools/sim/hover/RESULTS.md`: the sim reproduces this ring. INS_POS alone (with VEL_D 1.0) makes it
worse: the true acceleration at 2-2.5 Hz then reaches the D term and the sim drone tipped over.
INS_POS must go with PSC_NE_VEL_D 0 (`tools/tune_v6_stepA.parm`, full set `tools/tune_v6.parm`).
