"""Upload files to the Pixhawk SD card over MAVLink FTP (radio or USB).

Usage: python tools/mavftp_put.py PORT BAUD LOCAL_FILE REMOTE_PATH [LOCAL_FILE REMOTE_PATH ...]
Example: python tools/mavftp_put.py /dev/cu.usbserial-DU0E540E 57600 lua/sd_guard.lua /APM/scripts/sd_guard.lua
Close QGroundControl and the ground control server first; only one program can use the radio.
"""
import logging
import sys

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP


def main():
    if len(sys.argv) < 5 or len(sys.argv) % 2 == 0:
        sys.exit(__doc__)
    port, baud, pairs = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
    logging.basicConfig(level=logging.WARNING)
    m = mavutil.mavlink_connection(port, baud=baud, source_system=254)
    if not m.wait_heartbeat(timeout=15):
        sys.exit("no heartbeat")
    ftp = MAVFTP(m, m.target_system, m.target_component)
    ftp.cmd_mkdir(["/APM/scripts"])  # fails harmlessly if it already exists
    for local, remote in zip(pairs[0::2], pairs[1::2]):
        ftp.cmd_put([local, remote])
        ret = ftp.process_ftp_reply("CreateFile", timeout=60)
        print(f"{local} -> {remote}: {'ok' if ret.error_code == 0 else ret.error_code}")
        if ret.error_code != 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
