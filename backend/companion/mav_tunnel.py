#!/usr/bin/env python3
"""SSH to the Pi through the telemetry radio (Pi side).

Owns /dev/serial0 (Pixhawk TELEM3, MAVLink2). It:
- sends a heartbeat as the onboard computer (sysid 1, compid 191), so the FC
  learns the route to the Pi and forwards TUNNEL messages for it;
- turns each tunnel session (tunnel_proto.py) into a TCP connection to the Pi's
  own sshd (127.0.0.1:22);
- shares the FC link with other programs on the Pi: they connect with
  pymavlink to udpout:127.0.0.1:14650 (send a heartbeat first).

Laptop side: tools/mav_ssh.py (an SSH ProxyCommand).
"""
import os
os.environ.setdefault("MAVLINK20", "1")   # TUNNEL is a MAVLink2-only message
import argparse
import select
import socket
import time

from pymavlink import mavutil

import tunnel_proto as tp

ap = argparse.ArgumentParser()
ap.add_argument("--dev", default="/dev/serial0")
ap.add_argument("--baud", type=int, default=2000000)   # FC SERIAL5_BAUD 2000
ap.add_argument("--ssh", default="127.0.0.1:22")
ap.add_argument("--local", default="udpin:127.0.0.1:14650", help="'none' to turn off")
a = ap.parse_args()

COMP = mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER   # 191
fc = mavutil.mavlink_connection(a.dev, baud=a.baud, source_system=1, source_component=COMP)
fc.mav.srcSystem, fc.mav.srcComponent = 1, COMP
local = None if a.local == "none" else mavutil.mavlink_connection(a.local, source_system=1, source_component=COMP)

sessions = {}   # (sysid, compid, session) -> {"stream", "sock", "peer"}
next_hb = 0.0


def sender(peer):
    def send(payload):
        fc.mav.tunnel_send(peer[0], peer[1], tp.PAYLOAD_TYPE, len(payload),
                           list(payload) + [0] * (128 - len(payload)))
    return send


def open_session(peer, sid):
    key = (peer[0], peer[1], sid)
    if key in sessions:
        return sessions[key]
    host, port = a.ssh.split(":")
    sock = socket.create_connection((host, int(port)), timeout=3)
    sock.setblocking(False)
    s = {"stream": tp.Stream(sid, sender(peer)), "sock": sock, "peer": peer, "t": time.time()}
    sessions[key] = s
    print(f"session {sid} from {peer} open", flush=True)
    return s


def close(key, why):
    s = sessions.pop(key, None)
    if s:
        try:
            s["stream"].send(tp.pack(tp.FIN, key[2]))
            s["sock"].close()
        except OSError:
            pass
        print(f"session {key[2]} closed: {why}", flush=True)


print("mav_tunnel running", flush=True)
while True:
    now = time.time()
    if now >= next_hb:
        fc.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                              mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, mavutil.mavlink.MAV_STATE_ACTIVE)
        next_hb = now + 1.0

    busy = False
    while True:
        m = fc.recv_msg()
        if m is None:
            break
        busy = True
        t = m.get_type()
        if t == "TUNNEL" and m.target_system == 1 and m.target_component == COMP \
                and m.payload_type == tp.PAYLOAD_TYPE:
            peer = (m.get_srcSystem(), m.get_srcComponent())
            kind, sid, seq, ack, data = tp.unpack(bytes(m.payload[:m.payload_length]))
            key = (peer[0], peer[1], sid)
            if kind == tp.SYN:
                try:
                    s = open_session(peer, sid)
                    s["stream"].send(tp.pack(tp.SYNACK, sid))
                except OSError as e:
                    sender(peer)(tp.pack(tp.FIN, sid))
                    print(f"ssh connect failed: {e}", flush=True)
            elif key in sessions:
                s = sessions[key]
                s["t"] = now
                got = s["stream"].handle(kind, seq, ack, data)
                if got:
                    try:
                        s["sock"].sendall(got)
                    except OSError:
                        close(key, "ssh socket error")
                if s["stream"].closed:
                    close(key, "peer closed")
        elif local is not None and t != "BAD_DATA":
            try:
                local.write(m.get_msgbuf())
            except OSError:
                pass

    if local is not None:
        while True:
            q = local.recv_msg()
            if q is None or q.get_type() == "BAD_DATA":
                break
            fc.write(q.get_msgbuf())

    socks = {s["sock"]: k for k, s in sessions.items()}
    if socks:
        r, _, _ = select.select(list(socks), [], [], 0)
        for sock in r:
            key = socks[sock]
            try:
                data = sock.recv(4096)
            except OSError:
                data = b""
            if not data:
                close(key, "ssh ended")
            else:
                sessions[key]["stream"].write(data)
    for key, s in list(sessions.items()):
        s["stream"].poll()
        if now - s["t"] > 300:
            close(key, "no packets for 300 s")
    if not busy:
        time.sleep(0.005)
