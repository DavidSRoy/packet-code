#!/usr/bin/env python3
"""Check the MAVLink link from the Pi to the Pixhawk 6X (TELEM3 = SERIAL5).

Without --servo it only listens: it prints the heartbeat, mode and attitude.
With --servo N --pwm P it sends MAV_CMD_DO_SET_SERVO to output N.
The servo command is refused when the drone is armed.

CAUTION: remove the props before a servo test.

Examples:
  python3 fc_link.py
  python3 fc_link.py --servo 13 --pwm 1500
"""
import argparse
import time

from pymavlink import mavutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/serial0")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--servo", type=int, help="FC output number, e.g. 13 = AUX5")
    ap.add_argument("--pwm", type=int, help="pulse width in us (1000-2000)")
    ap.add_argument("--seconds", type=float, default=5.0)
    a = ap.parse_args()

    m = mavutil.mavlink_connection(
        a.port, baud=a.baud, source_system=1,
        source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER)
    print(f"waiting for a heartbeat on {a.port} at {a.baud} baud ...")
    hb = m.wait_heartbeat(timeout=10)
    if hb is None:
        raise SystemExit("no heartbeat: check wiring (TX->RX, RX->TX, GND) and SERIAL5_* params")
    armed = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print(f"FC sys {m.target_system} comp {m.target_component}  mode {m.flightmode}  armed {armed}")

    def companion_heartbeat():
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)

    if a.servo is not None:
        if a.pwm is None or not 800 <= a.pwm <= 2200:
            raise SystemExit("give --pwm between 800 and 2200")
        if armed:
            raise SystemExit("drone is armed: servo test refused")
        companion_heartbeat()
        m.mav.command_long_send(m.target_system, m.target_component,
                                mavutil.mavlink.MAV_CMD_DO_SET_SERVO, 0,
                                a.servo, a.pwm, 0, 0, 0, 0, 0)
        ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
        print(f"servo {a.servo} -> {a.pwm} us, ack: {ack.result if ack else 'none'}")

    end, last_hb = time.time() + a.seconds, 0.0
    while time.time() < end:
        if time.time() - last_hb > 1:
            companion_heartbeat()
            last_hb = time.time()
        msg = m.recv_match(type=["ATTITUDE", "SYS_STATUS"], blocking=True, timeout=1)
        if msg and msg.get_type() == "ATTITUDE":
            print(f"roll {msg.roll:+.2f}  pitch {msg.pitch:+.2f}  yaw {msg.yaw:+.2f} rad")
        elif msg:
            print(f"battery {msg.voltage_battery / 1000:.2f} V")


if __name__ == "__main__":
    main()
