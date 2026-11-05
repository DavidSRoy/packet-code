# 2026-10-25 log 16: altitude fence breach → RTL

Logs: `logs/bin/2026-10-25/log16.bin` (flight, starts 18:15 PDT), `log17.bin` (next boot, on the ground).
The laptop tlog for today ends at 15:26 and does not cover this flight.

## What happened

| Time (s) | Event |
|---|---|
| 118.9 | Armed in STABILIZE (flight-mode switch CH7 at 999 → FLTMODE1 = STABILIZE) |
| 125 | Full throttle (CH3 2011): climb 6.4 m/s to about 23 m |
| 130–150 | Flying at 22–27 m in STABILIZE |
| 150–156 | Height drops from 23.7 m to 14.7 m |
| 156–158 | Throttle up to 1749 → climb 8.2 m/s, height 14.7 → 29.5 m |
| 158.1 | **"Max Alt fence breached"** (FENCE_ALT_MAX 30 m). FC switches to **RTL** (mode reason 10 = FENCE_BREACHED) |
| 158.1 | "Manual recovery started": printed by ArduPilot on any mode change during a breach, also the automatic RTL switch (AC_Fence.cpp, mode.cpp). Not a pilot action |
| 159.1 | Peak height 32.7 m |
| 160–168 | Roll and throttle stick inputs: no effect, because RTL ignores the sticks |
| 170.7 | Breached again at about 30 m during the RTL return at height |
| 175–210 | RTL descends at home, then lands at 0.5 m/s |
| 210.1 | SD kill switch at 0.4 m (`SD KILL: h 0.4 m tilt 1`) |
| 215.0 | Disarmed |

GPS was good (20 satellites, HDOP 0.62). No radio, GCS or battery failsafe in the flight.

## Why the sticks did nothing

- In RTL the FC flies itself. Stick inputs do not move the drone.
- To take control back, the pilot must change the flight mode with the CH7 switch. That gives 10 s of manual recovery in which the fence does not trigger again.
- FLTMODE1–3 and FLTMODE5 are all STABILIZE, FLTMODE4 = ALT_HOLD, FLTMODE6 = LOITER. With the switch in its first position, move it to a different position (ALT_HOLD or LOITER) to take control.

## Settings that caused it (not changed)

| Param | Value |
|---|---|
| FENCE_ENABLE | 1 |
| FENCE_TYPE | 3 (max altitude + circle) |
| FENCE_ALT_MAX | 30 m |
| FENCE_RADIUS | 50 m |
| FENCE_ACTION | 1 (RTL, then land) |
| RTL_ALT_M | 15 m |

## Options (need Jason's OK before any change)

- Fly below about 25 m, or fly in ALT_HOLD / LOITER, which hold height so the throttle does not overshoot.
- Raise FENCE_ALT_MAX if the flights need more height.
- Teach the pilot: on a fence RTL, flip CH7 to another mode to take control.

## Why it would not arm after the landing (source: ArduCopter 4.7.2, fb773567)

| Time (s) | Message | Cause |
|---|---|---|
| 216.9 | PreArm: Motors Emergency Stopped | SD (CH8) was still at kill (2000). sd_guard.lua keeps the E-stop on until SD goes back to run |
| 233–248 | Arm: RTL mode not armable ×5 | The FC stays in RTL after it lands. `ModeRTL::allows_arming()` returns false (mode.h). The mode switch acts only when its position changes (RC_Channel.cpp `read_6pos_switch` / `debounce_completed`), and CH7 stayed at 999 |
| 258.9 | PreArm: Compasses inconsistent, EKF compass variance | Separate compass problem (check after the crash-free landing; gear near the drone can cause it) |
| log17 | Gyros not calibrated, Radio failsafe | After the reboot: the drone moved during boot, and the radio was not linked |

## Control during RTL

CH7 is a 2-position switch in logs 14–15: 999 = FLTMODE1 STABILIZE, 2000 = FLTMODE6 LOITER. In log16 it stayed at 999 for the whole flight.

| RTL phase | Roll/pitch sticks | Source |
|---|---|---|
| Climb and return (158–175 s) | Ignored | mode_rtl.cpp `climb_return_run`, `loiterathome_run` |
| Final descent and land (175–210 s) | Move the drone (LAND_REPOSITION = 1) | mode_rtl.cpp `descent_run`, `land_run` → mode.cpp `land_run_horizontal_control` |
| Any phase | Flip CH7 → full control at once | RC_Channel_Copter.cpp `mode_switch_changed` |

The roll inputs at 160–166 s were in the return phase, so the FC ignored them. In 175–210 s C1/C2 stayed at 1500, so no reposition was tried.
High throttle does not cancel the landing now: PILOT_THR_BHV = 0. Bit 1 (value 2) makes throttle above 700/1000 switch to LOITER (config.h LAND_CANCEL_TRIGGER_THR).
