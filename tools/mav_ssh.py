#!/usr/bin/env python3
"""SSH to the Pi through the telemetry radio (laptop side): an SSH ProxyCommand.

  ssh -o ProxyCommand=".venv/bin/python tools/mav_ssh.py" packet@packet-cv

The bytes go in MAVLink TUNNEL messages: laptop -> radio -> FC TELEM1 -> FC routes
to TELEM3 -> Pi (companion/mav_tunnel.py) -> the Pi's sshd.

Link: by default through the ground-control server (ground_control/server.py
sends TUNNEL traffic to UDP 14560). Without the server, open the radio directly
with --link /dev/cu.usbserial-DU0E540E (57600).

The radio gives about 1-3 KB/s with telemetry running: fine for a shell and
small edits, too slow for video or large copies.
"""
import os
os.environ.setdefault("MAVLINK20", "1")   # TUNNEL is a MAVLink2-only message
import argparse
import random
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))
import tunnel_proto as tp                     # noqa: E402
from pymavlink import mavutil                 # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--link", default="udpin:127.0.0.1:14560")
ap.add_argument("--baud", type=int, default=57600)
ap.add_argument("--sysid", type=int, default=253, help="this end's MAVLink system id")
ap.add_argument("--target", default="1:191", help="Pi sysid:compid")
a = ap.parse_args()

def log(*x):
    print("mav_ssh:", *x, file=sys.stderr, flush=True)

tsys, tcomp = map(int, a.target.split(":"))
m = mavutil.mavlink_connection(a.link, baud=a.baud, source_system=a.sysid,
                               source_component=mavutil.mavlink.MAV_COMP_ID_TUNNEL_NODE)
sid = random.randint(1, 0xFFFE)


def send(payload):
    m.mav.tunnel_send(tsys, tcomp, tp.PAYLOAD_TYPE, len(payload),
                      list(payload) + [0] * (128 - len(payload)))


stream = tp.Stream(sid, send)
inbox, lock, eof = bytearray(), threading.Lock(), threading.Event()


def read_stdin():
    while True:
        data = os.read(0, 4096)
        if not data:
            eof.set()
            return
        with lock:
            inbox.extend(data)


# open the session
t0, next_syn, up = time.time(), 0.0, False
while not up:
    if time.time() - t0 > 20:
        log("no answer from the Pi (is the ground-control server or radio up, and mav_tunnel running?)")
        sys.exit(1)
    if time.time() >= next_syn:
        send(tp.pack(tp.SYN, sid))
        next_syn = time.time() + 1.0
    msg = m.recv_match(type="TUNNEL", blocking=True, timeout=0.2)
    if msg and msg.target_system == a.sysid and msg.payload_type == tp.PAYLOAD_TYPE:
        kind, s, *_ = tp.unpack(bytes(msg.payload[:msg.payload_length]))
        if s == sid and kind == tp.SYNACK:
            up = True
        elif s == sid and kind == tp.FIN:
            log("the Pi refused the session (sshd not reachable)")
            sys.exit(1)
log(f"tunnel up (session {sid}) in {time.time() - t0:.1f} s")

threading.Thread(target=read_stdin, daemon=True).start()
fin_sent = False
while True:
    busy = False
    while True:
        msg = m.recv_match(type="TUNNEL", blocking=False)
        if msg is None:
            break
        if msg.target_system != a.sysid or msg.payload_type != tp.PAYLOAD_TYPE:
            continue
        kind, s, seq, ack, data = tp.unpack(bytes(msg.payload[:msg.payload_length]))
        if s != sid:
            continue
        busy = True
        got = stream.handle(kind, seq, ack, data)
        if got:
            os.write(1, got)
        if stream.closed:
            sys.exit(0)
    with lock:
        if inbox:
            stream.write(bytes(inbox))
            inbox.clear()
            busy = True
    stream.poll()
    if eof.is_set() and stream.idle() and not fin_sent:
        send(tp.pack(tp.FIN, sid))
        fin_sent = True
        sys.exit(0)
    if not busy:
        time.sleep(0.005)
