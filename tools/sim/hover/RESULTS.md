# Hover simulator results: tune_v6 (2026-11-03)

Goal: a 30 s box-camera hover at 1-3 cm (`hop.py` "Run test") with no visible wobble and
sub-cm position. Software and parameter changes only; no hardware changes.

All numbers are on the TRUE position of the simulated drone (not the FC estimate), 30 s hold at
2 cm. Model and calibration: `IDENT.md`. Everything below uses the shipped files as they are:
`tools/tune_v6.parm` (loaded with run.py `--parm`), the new `lua/hop_takeoff.lua`, and the Pi
settings of `companion/systemd/packet-cam.service` (sim: `camera.tilt_attitude_lag_s=0.06`, which is
the Pi's 0.053 s plus the 7 ms age of its attitude, and `camera.pi_cam_pos_err=[0,0,0]`).

## Result

| Metric | tune_v5 (flown now) | tune_v6 (shipped) |
|---|---|---|
| Horizontal error rms | 9.8-12.5 mm | 4.0-5.7 mm |
| Horizontal error p95 | 17-24 mm | 6.8-10.1 mm |
| Horizontal error max (30 s) | 21-30 mm | 7.9-12.5 mm |
| Tilt above 1 Hz, rms (wobble) | 0.62-0.69 deg | 0.30-0.33 deg |
| Hand-over slide | 1.4-2.8 cm (real logs 33-45) | 0-0.5 cm |

run.py, 12 seeds. The sim tilt is 1.4-2x the real log-43 tilt with the same parameters (IDENT.md),
so the real wobble is probably lower.

**Real ground-control code, end to end** (`e2e/run_e2e.py`: the real `server.py` + `hop.py` drive
SITL, a fake Pi serves the camera; 6 seeds): 6 of 6 runs take off, hold and land. Hold 4.0-5.4 mm
rms, 6.7-8.9 mm p95, 7.6-12.2 mm max; start point 0.1-1.4 mm from the true position. tune_v5 on the
same harness: 10.2-12.7 mm rms, 20-29 mm max.

Not reached: a hard 10 mm limit in every second of every run. The 30 s max is about 10 mm (8-12.5).
The remaining sway (0.3-0.7 Hz) comes mostly from the camera noise in the loop; the limit under it
is the 52 ms motor and propeller delay.

## Robustness (shipped tune_v6, max horizontal error in mm)

| Variant | max | Note |
|---|---|---|
| Roll/pitch authority K -20 % | 11.5 | |
| K +25 % | 10.8 | |
| Motors all pure delay (52 ms) | 9.6 | |
| Slower motors (40 ms + 25 ms lag) | 11.4 | |
| Camera latency 90 ms (Pi assumes 60) | 12.9 | |
| K -20 % + slower motors | 10.7 | VEL_P 5 here: 42 mm, 4.8 deg wobble |
| K -20 % + slower motors + latency 90 ms | 14.2 | VEL_P 5 here: tipped over |
| K -20 % + latency 90 + noise and disturbance x1.5 | 18.6 | VEL_P 5 here: tipped over |
| K -10 % + slower motors + latency 90 + noise/dist x1.5 | 19.8 | VEL_P 5 here: tipped over |
| All four slow-side errors at once, K -20 % | 23-44 | rocks 1.3-3.1 deg, does not tip (VEL_P 5 tipped) |
| K +25 % + all-pure-delay motors | 12-14 | 3.2 Hz roll limit cycle, 1.5 deg: see below |
| Hover at 1 cm / 3 cm | 9.7 / 9.5 | |
| East disturbance x2 (real logs: East 2x North) | 13.2 | |
| Gyro noise on (SIM_VIB_MOT_MASK 15, SIM_GYR_RND 3) | 11.3 | no 8-12 Hz component |
| 1 s camera blackout mid-hold | 11.8 | EKF height steps +4.5 cm, drone dips onto the box |
| Gust 0.3 m/s^2 for 1 s | 24 peak | under 10 mm again after 2-5 s |
| IMU position +-1 cm z, +-2 cm x; Pi mount +-1 cm; thrust axis +-0.5 deg; hover thrust +-5 % | 9.8-10.4 | (VEL_P 5 runs) |
| Camera frame drops 15 % / 30 % | 11.9 / 11.1 | (VEL_P 5 runs) |

The fast-plant corner (K +25 % with all the delay as pure delay) gives a 3.2 Hz roll rocking with the
rate D 0.006. Rate D 0.004 removes it but makes the slow-plant corners much worse, so D stays 0.006.
Both corners are outside the identified ranges (K 70-83, delay 45-55 ms). On the first flight, look
for a steady 3 Hz roll rocking and a fast buzz.

## What changed and why (each one was a separate sim test)

| Change | Where | Effect in the sim |
|---|---|---|
| Pi uses the attitude at the exposure, not at t_cap (`--imu-lag 0.053`) | `companion/systemd/packet-cam.service` | 4 Hz wobble about -25 % |
| Pi reports the CG, not a point 8.1 cm below it (`--mount-fwd 0.127 --mount-down 0.101`) | same | removes a 0.08 m x tilt position error |
| INS_POS1/2 = (-0.007, -0.001, -0.058) | `tools/tune_v6.parm` | removes the lever-arm drive of the 4.4 Hz ring |
| PSC_NE_VEL_D 0 | same | REQUIRED with INS_POS: with VEL_D 1.0 the sim tipped over in 2 s |
| VISO_DELAY_MS 60 -> 110 | same | fixes dated at the exposure time (about 117 ms before arrival). The hold does not change between 100 and 135 in the sim |
| Takeoff hover trim HTO_TRIM_P 0.85, HTO_TRIM_R 0 | `lua/hop_takeoff.lua` (new params) + parm | hand-over slide 2-3 cm -> under 0.5 cm. TRIM_R -0.23 gave no difference |
| Rate P 0.22, I 0.3, D 0.006, FLTT 20 (roll, pitch) | `tools/tune_v6.parm` | angle-loop resonance +4.2 dB -> +0.1 dB; wobble -50 % |
| ATC_INPUT_TC 0.02, PSC_NE_VEL_FLTE 10 | same | about 40 ms less lag in the velocity loop |
| PSC_NE_POS_P 2.5, VEL_P 4, VEL_I 4 | same | hold rms 11 -> 5 mm. VEL_P 5 is 1 mm tighter at nominal but tipped over on combined slow-plant errors |
| EK3_ACC_P_NSE 0.15, EK3_TAU_OUTPUT 40 | same | less camera noise into the controller: max -10 % |
| Start point x, y = mean tag position over the last still second; the FC must stay inside 4 mm for that second; settle limit 6 -> 10 s | `ground_control/hop.py` | with the real hop.py the start was 3-6 mm off (the EKF still walks after the zero) and the whole hold sat there; now 0.1-1.4 mm |
| Liftoff hover estimate floored at 0.97 T/W; climb timeout 3 -> 4 s | `lua/hop_takeoff.lua` | 2-6 of 9 takeoffs aborted "lifted but no climb" after a 0.95 estimate (real logs: 0.96-1.02); now 0 of 12 |

Tried, no gain: higher camera rate (20, 30 Hz); no camera velocity (EK3_SRC2_VELXY 0);
VISO_POS_M_NSE 0.03; EK3_TAU_OUTPUT 10 (worse); VEL_I 6; VEL_P 6 (unstable); acceleration
feed-forward through the Lua position offset (ArduPilot shapes the offset as a trajectory).

## The camera latency (exposure -> FC)

About 117 ms: exposure -> t_cap 60 ms (+-15) and t_cap -> FC 57 ms. Fitted from the attitude-match
error in logs 41-45 and checked against the ring in the sim (IDENT.md). The FC dated the fixes
45 ms late. A light-toggle test on the Pi would measure the 60 ms directly; it is not done.

## Known limits (not fixed here)

- A camera outage of 0.5 s or more makes EKF3 step its height by about 4.5 cm (it falls back to the
  baro) and the drone dips onto the box. Real gaps of 300-400 ms are in the logs.
- The sim has no frame or motor vibration: the buzz risk of the 3x rate D can only be checked in
  flight. With the JSON backend, SIM_ACC/GYR_RND act only with SIM_VIB_MOT_MASK set.
- run.py's landing is not scored and differs from hop.py's stop rule; the e2e harness runs the real one.

## Test plan (not loaded on the drone)

CAUTION: INS_POS and PSC_NE_VEL_D 0 must be loaded together. INS_POS with VEL_D 0.75-1.0 tipped the
sim drone over. `tune_v6.parm` has VEL_D first.

1. Deploy: `lua/hop_takeoff.lua` to the FC SD card (APM/scripts), then REBOOT the FC (the HTO_ table
   grows from 9 to 11; a scripting restart alone stops the script). Check that HTO_TRIM_P and
   HTO_TRIM_R exist. Copy the Pi service file, `systemctl daemon-reload`, restart packet-cam. Restart
   the ground control server (new `hop.py`).
2. Load `tools/tune_v6.parm`. REBOOT the FC again (EKF3 sizes its buffer from VISO_DELAY_MS at boot).
   Read back every value in the file.
3. Bench, disarmed, on the box: the page's "Above lid" (drone_m z) goes up by about 8 cm (79-81 mm)
   against before; "Cam height" (camera_m z) does not change.
4. Fly the 2 cm, 30 s test. Expect: hand-over slide under 1 cm in the HTO message, hold about 5 mm
   rms, about 10 mm max, no visible wobble. Watch for a fast buzz or a steady 1-3 Hz rocking; check
   the motor temperatures after the flight.
5. Compare the log with the sim: `python tools/sim/hover/compare.py LOG.BIN` and the `fin_nom*` runs.

## Reproduce

```bash
python tools/sim/hover/batch.py tools/sim/hover/configs/fin.json --jobs 10
```

```bash
python tools/sim/hover/e2e/run_e2e.py --name e2e1 --seed 1 --out /tmp/e2e --parm tools/tune_v6.parm --set camera.tilt_attitude_lag_s=0.06 --set 'camera.pi_cam_pos_err=[0,0,0]'
```

Configs: `configs/c*.json` calibration, `b*.json` / `d*.json` / `f1.json` tuning steps, `r1-r3.json`
first robustness set (r3 used the removed step-A file), `s1-s7.json` stress tests (VEL_P 5),
`fin.json` / `fin2.json` the shipped tune. Tools: `errsplit.py`, `bands.py`.
New model options (off unless set): `gust`, `thrust_ramp`, `camera.blackout` (physics.py).
