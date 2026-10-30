"""Set FC parameters from a NAME,VALUE file and read each one back.

Usage: python tools/param_load.py PORT BAUD FILE
Example: python tools/param_load.py /dev/cu.usbserial-DU0E540E 57600 tools/perma_loiter.parm
Close QGroundControl and the ground control server first; only one program can use the radio.
"""
import sys

from pymavlink import mavutil


def read_parm(path):
    out = []
    for line in open(path):
        line = line.split("#", 1)[0].strip()
        if line:
            name, value = line.replace(",", " ").split()
            out.append((name, float(value)))
    return out


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    port, baud, path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    params = read_parm(path)
    m = mavutil.mavlink_connection(port, baud=baud, source_system=254)
    if not m.wait_heartbeat(timeout=15):
        sys.exit("no heartbeat")
    bad = 0
    for name, value in params:
        got = None
        for _ in range(3):  # the radio drops packets; retry
            m.param_set_send(name, value)
            msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=3,
                               condition=f"PARAM_VALUE.param_id=='{name}'")
            if msg is not None:
                got = msg.param_value
                break
        ok = got is not None and abs(got - value) < 1e-3
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name} = {got} (want {value:g})")
    if bad:
        sys.exit(f"{bad} parameter(s) not set")
    print("done. Reboot the FC: INITIAL_MODE only applies at boot.")


if __name__ == "__main__":
    main()
