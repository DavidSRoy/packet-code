# Hover simulator results: tune_v6 (2026-11-03)

Goal: a 30 s box-camera hover at 1-3 cm (`hop.py` "Run test") with no visible wobble and
sub-cm position. Software and parameter changes only; no hardware changes.

All numbers are on the TRUE position of the simulated drone (not the FC estimate), 30 s hold at
2 cm, from 2 s after the target height. Model and calibration: `IDENT.md`.

## Result

| Metric | tune_v5 (flown now) | tune_v6 |
|---|---|---|
| Horizontal error rms | 9.8-12.5 mm | 4.1-4.9 mm |
| Horizontal error p95 | 17-24 mm | 7.0-7.9 mm |
| Horizontal error max (30 s) | 21-30 mm | 8.9-10.1 mm |
| Height error max | 4-8 mm | 5-8 mm |
| Tilt above 1 Hz, rms (wobble) | 0.62-0.69 deg | 0.34-0.37 deg |
| Tilt above 1 Hz, p99 | 1.2-1.6 deg | 0.8-0.9 deg |
| Error in the first 3 s after the hand-over, max | 29-44 mm | 6-7 mm |

Three seeds at nominal values. The sim tilt is 1.4-2x the real log-43 tilt with the same
parameters (IDENT.md), so the real wobble is probably lower than these numbers.

Not reached: a hard 10 mm limit in every second of every run. The max over 30 s is 8.9-10.1 mm at
nominal and 11-13 mm with 1.5x the disturbance or the camera noise. In the sim the remaining sway
(0.3-0.7 Hz) comes mostly from the camera noise in the loop: with zero camera noise the hold is
3.4 mm rms and 7.7-8.9 mm max; with zero disturbance it is 3.6 mm rms. The limit under it is the
52 ms motor and propeller delay: a velocity gain of 6 is unstable in the sim.

## Robustness (11 variants, max horizontal error in mm)

| Variant | tune_v5 | step A | tune_v6 |
|---|---|---|---|
| Nominal, seeds 1 / 2 / 3 | 30 / 22 / 21 | 26 / 41 / 40 | 10 / 10 / 9 |
| Roll/pitch authority K -20 % | tipped over | 28 | 10 |
| K +25 % | diverged (270) | 22 | 9 |
| Motor response all pure delay (52 ms) | tipped over | 25 | 10 |
| Slower motors (40 ms + 25 ms lag) | tipped over | 23 | 10 |
| Camera latency 30 ms (Pi assumes 60) | 26 | 22 | 8 |
| Camera latency 90 ms | diverged (222) | 35 | 12 |
| Disturbance x1.5 | 41 | 38 | 12 |
| Camera noise x1.5 | 34 | 28 | 13 |

tune_v5 sits close to instability: that is the growing 4.4 Hz ring of log 45.

## What changed and why (each one was a separate sim test)

| Change | Where | Effect in the sim |
|---|---|---|
| Pi uses the attitude at the exposure, not at t_cap (`--imu-lag 0.053`) | `companion/systemd/packet-cam.service` | 4 Hz wobble about -25 % |
| Pi reports the CG, not a point 8.1 cm below it (`--mount-fwd 0.127 --mount-down 0.101`) | same | removes a 0.08 m x tilt position error |
| INS_POS1/2 = (-0.007, -0.001, -0.058) | `tools/tune_v6_stepA.parm` | removes the lever-arm drive of the 4.4 Hz ring |
| PSC_NE_VEL_D 0 | same | REQUIRED with INS_POS: with VEL_D 1.0 the sim tipped over in 2 s |
| VISO_DELAY_MS 60 -> 110 | same | fixes dated at the real exposure time (117 ms before arrival) |
| Takeoff script hover trim HTO_TRIM_P 0.85 | `lua/hop_takeoff.lua` (new HTO_TRIM_R/P, default 0) + parm | hand-over slide 21 mm -> 10 mm |
| Start point = mean FC position over the settled second | `ground_control/hop.py` | one sample carried 1-2 mm of camera noise into the whole hover |
| Rate P 0.22, I 0.3, D 0.006, FLTT 20 (roll, pitch) | `tools/tune_v6.parm` | angle-loop resonance +4.2 dB -> +0.1 dB; wobble -40 % |
| ATC_INPUT_TC 0.02, PSC_NE_VEL_FLTE 10 | same | about 40 ms less lag in the velocity loop |
| PSC_NE_POS_P 2.5, VEL_P 5, VEL_I 4 | same | hold rms 11 -> 5 mm |
| EK3_ACC_P_NSE 0.15, EK3_TAU_OUTPUT 40 | same | less camera noise into the controller: max -10 % |

Tried, no gain: higher camera rate (20, 30 Hz) in the sim; no camera velocity (EK3_SRC2_VELXY 0);
VISO_POS_M_NSE 0.03; EK3_TAU_OUTPUT 10 (worse); VEL_I 6; acceleration feed-forward through the
Lua position offset (ArduPilot shapes the offset as a trajectory, so it moves the target).

## The camera latency (exposure -> FC)

About 117 ms: exposure -> t_cap 60 ms (+-15) and t_cap -> FC 57 ms. Fitted from the attitude-match
error in logs 41-45 and checked against the ring in the sim (IDENT.md). The FC dated the fixes
45 ms late. A light-toggle test on the Pi would measure the 60 ms directly; it is not done.

## Test plan (not loaded on the drone)

CAUTION: INS_POS and PSC_NE_VEL_D 0 must be loaded together. INS_POS with VEL_D 0.75-1.0 tipped the
sim drone over.

1. Deploy: `lua/hop_takeoff.lua` to the FC SD card (APM/scripts), reboot the FC. The Pi service
   file, then `systemctl daemon-reload` and restart packet-cam. Restart the ground control server
   (new `hop.py`).
2. Bench, disarmed, on the box: the camera height goes up by about 8 cm (the CG, not 8.1 cm below
   it). Tilt the drone by hand about 10 deg: the reported x/y moves by less than 3 mm (before:
   about 14 mm). Check that HTO_TRIM_P and HTO_TRIM_R exist.
3. Load `tools/tune_v6_stepA.parm`. Fly the 2 cm, 30 s test. Expect: no 4 Hz ring, no 2-2.5 Hz growth,
   "slid" in the HTO message under 1 cm. The hold may not be tighter than tune_v5.
4. Load `tools/tune_v6.parm`. Fly the same test. Expect: hold about 5 mm rms, under 10 mm most of
   the time. Listen for a fast (8-10 Hz) buzz: the rate D gain is 3x tune_v5. Check the motor
   temperatures after the flight.
5. Compare the logs with the sim: `python tools/sim/hover/compare.py LOG.BIN` and the runs
   `r2_v6_nom1..3` (same hold window).

## Reproduce

```bash
python tools/sim/hover/batch.py tools/sim/hover/configs/r2.json --jobs 11
```

Configs: `configs/c*.json` calibration, `b*.json` / `d*.json` / `f1.json` tuning steps,
`r1.json` (tune_v5, v6a, v6b x 11 variants), `r2.json` (tune_v6), `r3.json` (step A).
Tools: `errsplit.py` (estimate vs control error), `bands.py` (error by frequency).
