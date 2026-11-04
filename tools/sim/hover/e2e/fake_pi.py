#!/usr/bin/env python3
"""physics.py plus the parts of the Pi (companion/cam_stream.py) that ground control talks to.

Runs physics.main() unchanged, with its Camera replaced by PiCamera, which also:
  - answers the "zero on the box" TUNNEL (39003) like cam_stream.vision(): the next
    VISION_POSITION_ESTIMATE carries a new reset counter, then the TUNNEL answer goes back
    to the sender with that counter,
  - sends PIIP (DEBUG_VECT) every 5 s so ground control finds the Pi page (127.0.0.1:<port>),
  - serves /lid.json with the same pose it sent to the FC: drone_m = [x, -y, -z] of the
    VISION_POSITION_ESTIMATE (cam_stream sends x, -y, -z of drone_m), "t" = the wall time it
    was sent, "now" = the wall time of the request.

  python fake_pi.py --http-port 28620 <physics.py arguments>
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import physics  # noqa: E402

ZERO_PAYLOAD_TYPE = 39003
LID = {"t": 0.0, "boxes": []}
LOCK = threading.Lock()


def take_port(argv):
    i = argv.index("--http-port")
    port = int(argv[i + 1])
    del argv[i:i + 2]
    return port


HTTP_PORT = take_port(sys.argv)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if not self.path.startswith("/lid.json"):
            self.send_response(404)
            self.end_headers()
            return
        with LOCK:
            body = json.dumps(dict(LID, now=time.time())).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PiCamera(physics.Camera):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.zero_want, self.zero_done, self.zero_peer = 0, 0, None
        self.next_piip = 0.0
        self.zero_log = []

    def poll(self):
        while self.link is not None:
            try:
                msg = self.link.recv_msg()
            except Exception:
                return
            if msg is None:
                return
            if (msg.get_type() == "TUNNEL" and msg.target_system == 1 and msg.target_component == 191
                    and msg.payload_type == ZERO_PAYLOAD_TYPE):
                self.zero_want += 1
                self.zero_peer = (msg.get_srcSystem(), msg.get_srcComponent())

    def step(self, t):
        self.poll()
        due = bool(self.pending and self.pending[0][0] <= t)
        zero_now = due and self.zero_want != self.zero_done
        if zero_now and not os.environ.get("E2E_NO_RESET"):     # diagnostic: answer without a reset
            self.reset_counter = (self.reset_counter + 1) % 256
        n0 = len(self.sent)
        super().step(t)
        pos = [s for s in self.sent[n0:] if s[1] == "pos"]
        if pos:
            x, y, z = pos[-1][3:6]
            with LOCK:
                LID.update(t=time.time(), boxes=[{"box": 1, "drone_m": [round(x, 5), round(-y, 5), round(-z, 5)]}])
        if self.link is None:
            return
        try:
            if zero_now and pos and self.zero_peer:
                self.link.mav.tunnel_send(self.zero_peer[0], self.zero_peer[1], ZERO_PAYLOAD_TYPE, 1,
                                          [self.reset_counter] + [0] * 127)
                self.zero_done = self.zero_want
                self.zero_log.append((t, time.time(), self.reset_counter))
                print(f"fake_pi: zero answered at sim {t:.2f} s, reset counter {self.reset_counter}", flush=True)
            if time.time() >= self.next_piip:
                self.next_piip = time.time() + 5.0
                self.link.mav.debug_vect_send(b"PIIP", int(time.time() * 1e6), float(127 * 256 + 0),
                                              float(0 * 256 + 1), float(HTTP_PORT))
        except Exception:
            pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    physics.Camera = PiCamera
    os.environ.setdefault("MAVLINK20", "1")
    physics.main()
