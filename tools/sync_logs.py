"""Copy the Pixhawk's full flight logs (.BIN dataflash logs) to the laptop.

Usage: python tools/sync_logs.py PORT [BAUD] [--latest N]
  USB (fast, about 1 MB/s):    python tools/sync_logs.py /dev/cu.usbmodem2101
  Radio (slow, about 4 KB/s):  python tools/sync_logs.py /dev/cu.usbserial-DU0E540E 57600 --latest 1

Logs go to packethw/logs/bin/ (committed, so the team can analyse them). Files already there with the same
size are skipped, so you can run it after every flight day.
Close QGroundControl and the ground control server first.
"""
import argparse
import logging
import time
from pathlib import Path

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP

OUT = Path(__file__).resolve().parent.parent / "logs" / "bin"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port")
    ap.add_argument("baud", nargs="?", type=int, default=115200)
    ap.add_argument("--latest", type=int, default=0, help="only the newest N logs (0 = all)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    m = mavutil.mavlink_connection(args.port, baud=args.baud, source_system=254)
    if not m.wait_heartbeat(timeout=15):
        raise SystemExit("no heartbeat")
    hb = m.messages["HEARTBEAT"]
    if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
        raise SystemExit("drone is armed; sync logs only on the ground, disarmed")

    ftp = MAVFTP(m, m.target_system, m.target_component)
    ret = ftp.cmd_list(["/APM/LOGS"])
    if ret.error_code != 0:
        raise SystemExit(f"cannot list /APM/LOGS: {ret.error_code}")
    logs = sorted((e for e in ftp.list_result if not e.is_dir and e.name.upper().endswith(".BIN")),
                  key=lambda e: e.name)
    if args.latest:
        logs = logs[-args.latest:]
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{len(logs)} log(s) on the drone -> {OUT}")

    for e in logs:
        dest = OUT / e.name
        if dest.exists() and dest.stat().st_size == e.size_b:
            print(f"  {e.name}: already here ({e.size_b / 1e6:.1f} MB)")
            continue
        t0 = time.time()
        ftp.cmd_get([f"/APM/LOGS/{e.name}", str(dest)])
        # wait for the whole transfer: timeout=0 gave up at once (error 73, RemoteReplyTimeout)
        ret = ftp.process_ftp_reply("OpenFileRO", timeout=max(60, e.size_b / 2000))
        dt = time.time() - t0
        ok = ret.error_code == 0 and dest.exists() and dest.stat().st_size == e.size_b
        print(f"  {e.name}: {'ok' if ok else 'FAILED ' + str(ret.error_code)} "
              f"{e.size_b / 1e6:.1f} MB in {dt:.0f} s")


if __name__ == "__main__":
    main()
