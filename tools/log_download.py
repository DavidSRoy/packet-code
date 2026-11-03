"""Download dataflash logs (.BIN) from the FC with the MAVLink log protocol.

LOG_REQUEST_LIST, then LOG_REQUEST_DATA for the whole log: the FC streams LOG_DATA
(90 bytes each); missing pieces are asked for again. MAVFTP listed the logs but its
transfers timed out on this setup (2026-11-03); this protocol does not use MAVFTP.

Usage: python tools/log_download.py PORT BAUD OUT_DIR [--latest N]
Fast: on the Pi over its serial link to the FC (stop packet-cam and packet-tunnel first):
  python log_download.py /dev/serial0 2000000 /tmp/logs --latest 2
At 2 Mbaud (SERIAL5_BAUD 2000) about 85 KB/s: ArduPilot sends one LOG_DATA per loop on a port
without RTS/CTS flow control, so the baud alone does not reach the line rate.
"""
import argparse
import os
import time

from pymavlink import mavutil

CHUNK = 90


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port")
    ap.add_argument("baud", type=int)
    ap.add_argument("out")
    ap.add_argument("--latest", type=int, default=1)
    a = ap.parse_args()
    m = mavutil.mavlink_connection(a.port, baud=a.baud, source_system=254)
    hb = m.wait_heartbeat(timeout=15)
    if not hb:
        raise SystemExit("no heartbeat")
    if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
        raise SystemExit("armed: download logs only on the ground")
    sysid, compid = m.target_system, m.target_component

    m.mav.log_request_list_send(sysid, compid, 0, 0xFFFF)
    entries, end = {}, time.time() + 5
    while time.time() < end:
        e = m.recv_match(type="LOG_ENTRY", blocking=True, timeout=1)
        if e and e.size > 0:
            entries[e.id] = e.size
            if len(entries) >= e.num_logs:
                break
    if not entries:
        raise SystemExit("no logs listed")
    os.makedirs(a.out, exist_ok=True)

    for lid in sorted(entries)[-a.latest:]:
        size = entries[lid]
        buf = bytearray(size)
        have = set()
        need = (size + CHUNK - 1) // CHUNK
        t0 = time.time()
        m.mav.log_request_data_send(sysid, compid, lid, 0, 0xFFFFFFFF)
        last_rx, asks = time.time(), 0
        while len(have) < need and time.time() - t0 < 600:
            d = m.recv_match(type="LOG_DATA", blocking=True, timeout=0.5)
            if d and d.id == lid and d.count > 0:
                buf[d.ofs:d.ofs + d.count] = bytes(d.data[:d.count])
                have.add(d.ofs // CHUNK)
                last_rx, asks = time.time(), 0
            elif time.time() - last_rx > 0.5:            # stream stopped: ask for the first gap onward
                if asks >= 10:                           # the FC sends nothing more: the log it is still writing
                    print(f"log {lid}: the FC stopped sending at {len(have) * CHUNK / 1e6:.1f} of {size / 1e6:.1f} MB "
                          "(the open log? set LOG_FILE_DSRMROT 1, or reboot to close it)")
                    break
                gap = next(i for i in range(need) if i not in have)
                m.mav.log_request_data_send(sysid, compid, lid, gap * CHUNK, 0xFFFFFFFF)
                last_rx, asks = time.time(), asks + 1
        m.mav.log_request_end_send(sysid, compid)
        path = os.path.join(a.out, f"{lid:08d}.BIN")
        with open(path, "wb") as f:
            f.write(buf)
        done = len(have) == need
        print(f"log {lid}: {'ok' if done else 'INCOMPLETE'} {size / 1e6:.1f} MB in {time.time() - t0:.0f} s -> {path}")


if __name__ == "__main__":
    main()
