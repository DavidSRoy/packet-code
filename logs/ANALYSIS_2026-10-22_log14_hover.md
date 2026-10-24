# Hover analysis: log 14 (flight of 2026-10-22)

Source: `logs/bin/00000014.BIN`. Parameters: `logs/params/params_2026-10-23_2036.parm`.
Script: `python tools/hover_analysis.py logs/bin/00000014.BIN`.

Stable hover is armed, height more than 2 m, climb less than 0.3 m/s, GPS
speed less than 0.7 m/s, and roll and pitch less than 6 deg. Log 14 has
29 s of stable hover in LOITER at 2.5 to 4 m.

## Summary

- Hover time on one 6S 6500 mAh battery is about **18 min** to a 20 % reserve
  at the current weight (about 2.9 kg, no shell).
- The largest problem is a **motor imbalance** (damaged props or twisted arms). The CW motors make about 1.7 times
  the thrust of the CCW motors. This decreases the usable takeoff weight by
  about 20 % and makes the yaw less steady.
- Vibration, position hold and battery health are good.

## Hover data

| Item | Value |
|---|---|
| Battery current | 17.7 A (p10 17.0, p90 18.4) |
| Battery voltage | 21.8 V (pack at about 50 %, 22.5 V at rest) |
| Power | 385 W |
| Hover thrust (`MOT_THST_HOVER`) | 0.29 learned, 0.32 in-flight estimate |
| Flight weight | about 2.92 kg (kit 2.0 kg + 19 g team parts + battery, estimated 900 g) |
| Efficiency | about 7.6 g/W |
| Max thrust (calculated) | about 9.5 kgf at 25.2 V, about 6.5 kgf at 19.8 V |

**The battery weight is an estimate.** Weigh the drone to make the numbers exact.

## Hover time estimate (6S 6500 mAh, 20 % reserve)

Hover power changes approximately as weight^1.5.

| Configuration | Weight | Hover time |
|---|---|---|
| Now, no shell | about 2.9 kg | about 18 min (about 22 min to empty: do not do this) |
| With the shell (+200 g) | about 3.1 kg | about 16 min |
| With the shell and a 1 kg payload | about 4.1 kg | about 11 min |

## Problems, largest first

### 1. Motor imbalance (damaged props or twisted arms)

Median motor output in hover (µs):

| Motor | Position | Direction | PWM |
|---|---|---|---|
| M1 | front-right | CCW | 1474 |
| M2 | rear-left | CCW | 1440 |
| M3 | front-left | CW | 1613 |
| M4 | rear-right | CW | 1592 |

- The CW motors run about 146 µs higher than the CCW motors.
- Mean yaw output is -0.146, and the yaw I-term is -0.129. The controller
  uses 15 % of its output only to hold the heading.
- The yaw-rate error is 0.29 rad/s (17 deg/s). Roll and pitch are
  0.10 to 0.11 rad/s.
- The power cost is small (about 3 %). But the busiest motors get to full
  power first. The usable max takeoff weight is about 20 % lower than with
  balanced motors.

Possible causes:

1. **Damaged CW props.** The props were damaged in the first tests. A damaged
   prop makes less thrust, so its motor must run faster. New props arrive on
   Monday (2026-10-26).
2. **Twisted arms or motor mounts.** The arm tubes can turn in the folding
   clamps. A tilt of a few degrees is sufficient to cause this.

Procedure:

1. Put a level on each motor bell. Turn each arm until its motor is level,
   then tighten the clamp.
2. Install the new props.
3. Fly a 1 min LOITER hover and run `tools/hover_analysis.py` on the new log.
4. Make sure that CW minus CCW is less than 30 µs.
5. If the difference stays large, examine the motors and the prop direction.

### 2. CG slightly to the front

The front motors run about 28 µs higher than the rear motors. The left-right
difference is -6 µs (good). Move the battery back by about 1 to 2 cm.

### 3. Roll and pitch slightly twitchy

The roll and pitch rates have a standard deviation of 9 to 13 deg/s in hover.
In an earlier review of this log, a 17 deg pitch command gave 27 deg.
Do an AutoTune after the motor fix. A tune done before the fix will be
incorrect.

## Good items

| Item | Value | Limit |
|---|---|---|
| Vibration X/Y/Z (median) | 4.6 / 3.0 / 4.2 m/s² | less than 30 |
| Vibration p95 | 5.7 / 3.6 / 6.5 m/s² | less than 30 |
| Accelerometer clipping | 0 | 0 |
| Position error, horizontal | 0.07 m median, 0.18 m p95 | |
| Position error, vertical | 0.07 m p95 | |
| Pack resistance (with wiring) | about 39 mΩ | 12 W loss in hover |

## Notes

- The battery started the flight at about 50 %. The flight controller
  showed 90 % at the end because it assumes a full pack at power-on.
  Use a full battery for the next flights.
- `MOTB.ThLimit` is a limit value, not a flag. It does not show a problem.
- The avionics power is in the 385 W total. The log does not show it
  separately.
