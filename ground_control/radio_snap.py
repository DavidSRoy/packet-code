"""Box camera snapshots over the telemetry radio, ground side (protocol: companion/snap_proto.py).

Telemetry first. The telemetry radio carries the FC data the pilot and the
autopilot logic need; a snapshot is extra. So:

- Snapshots run only while the laptop cannot reach the Pi over Wi-Fi (with
  Wi-Fi, the page shows the real video).
- Each cycle (0.5 s), it checks the telemetry: ATTITUDE and
  GLOBAL_POSITION_INT must arrive at 85% or more of their requested rates
  over the last 2 s, and the drone heartbeat must be fresh. Only then does it
  ask the Pi for picture pieces.
- The number of pieces per cycle grows by 1 while the telemetry stays at full
  rate, and halves (with a 2 s pause) when it drops. ArduPilot lowers its own
  telemetry rates when the radio buffer fills, so a drop in the received
  telemetry is the signal that the snapshots use too much of the link.
"""
import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))
import snap_proto as sp                    # noqa: E402

CYCLE = 0.5             # s
HEALTH_WINDOW = 2.0     # s
HEALTH_MIN = 0.85       # of the requested rate
EXPECT = {"ATTITUDE": 10.0, "GLOBAL_POSITION_INT": 5.0}   # Hz, as requested in Link.request_streams
W_START, W_MAX = 2, 16  # pieces per cycle
MIN_GAP = 1.0           # s between pictures
FRAME_TIMEOUT = 10.0    # s to finish one picture
PIECE_TIMEOUT = 1.5     # s before a piece is asked for again
WIDTH, QUALITY = 320, 30


class RadioSnap:
    def __init__(self, link, pi_url_fn):
        self.link = link
        self.pi_url_fn = pi_url_fn          # returns the Pi URL or None
        self.seen = {k: deque() for k in EXPECT}
        self.w = W_START
        self.pause_until = 0.0
        self.frame = 0                      # frame being received
        self.parts = {}
        self.nchunks = 0
        self.started = 0.0
        self.asked = {}                     # piece -> time asked, for the current picture
        self.n_asked = self.n_got = 0       # pieces asked / received (all pictures)
        self.jpg = None                     # last complete picture
        self.jpg_t = 0.0
        self.jpg_frame = 0
        self.wifi_ok = False
        self.wifi_checked = 0.0
        self.sent_bytes = deque()           # (t, bytes) of received pieces
        link.hooks.append(self.on_msg)
        link.state["radio_snap"] = None

    # ---- receive (Link thread) ----
    def on_msg(self, msg):
        t = msg.get_type()
        if t in self.seen:
            self.seen[t].append(time.time())
        elif t == "TUNNEL" and msg.payload_type == sp.PAYLOAD_TYPE and msg.target_system == 254:
            r = sp.unpack(bytes(msg.payload[:msg.payload_length]))
            if not r or r[0] != "data":
                return
            _, frame, chunk, nchunks, data = r
            self.sent_bytes.append((time.time(), len(data) + 12 + 128))
            if frame != self.frame:
                if self.frame != -1:
                    return                          # a late piece of an old picture
                self.frame, self.parts, self.nchunks = frame, {}, nchunks
            self.parts[chunk] = data
            self.n_got += 1
            if len(self.parts) == self.nchunks:
                self.jpg = b"".join(self.parts[i] for i in range(self.nchunks))
                self.jpg_t, self.jpg_frame = time.time(), frame
                self.parts, self.nchunks, self.asked = {}, 0, {}
                self.w = min(W_MAX, self.w + 1)         # finished while healthy: allow more next time

    # ---- decide and ask (own thread) ----
    def healthy(self, now):
        if not self.link.state.get("link"):
            return False
        for k, q in self.seen.items():
            while q and now - q[0] > HEALTH_WINDOW:
                q.popleft()
            if len(q) < EXPECT[k] * HEALTH_WINDOW * HEALTH_MIN:
                return False
        return True

    def wifi(self, now):
        """True when the laptop reaches the Pi over Wi-Fi (checked every 3 s)."""
        if now - self.wifi_checked > 3:
            self.wifi_checked = now
            url = self.pi_url_fn()
            ok = False
            if url:
                import urllib.request
                try:
                    with urllib.request.urlopen(f"{url}/lid.json", timeout=1) as r:
                        ok = r.status == 200
                except Exception:
                    ok = False
            self.wifi_ok = ok
        return self.wifi_ok

    def ask(self, frame, first, count):
        L = self.link
        if L.sysid is None:
            return
        payload = sp.pack_req(frame, first, count, QUALITY, WIDTH)
        L.send(L.m.mav.tunnel_send, 1, 191, sp.PAYLOAD_TYPE, len(payload),
               list(payload) + [0] * (128 - len(payload)))

    def request(self, now):
        """Ask for up to w pieces: the rest of this picture, or a new picture."""
        busy = self.frame == -1 or self.parts or self.nchunks
        if busy and now - self.started > FRAME_TIMEOUT:
            busy = False                                    # give up on this picture
        if not busy:
            if now - self.jpg_t < MIN_GAP:
                return
            self.frame, self.parts, self.nchunks, self.started = -1, {}, 0, now
            self.asked = {i: now for i in range(self.w)}
            self.n_asked += self.w
            self.ask(0, 0, self.w)
            return
        if self.frame == -1:                                # no piece yet
            if now - self.started > 2:
                self.started = now
                self.asked = {i: now for i in range(self.w)}
                self.ask(0, 0, self.w)
            return
        todo = [i for i in range(self.nchunks)
                if i not in self.parts and now - self.asked.get(i, 0) > PIECE_TIMEOUT]
        in_flight = sum(1 for i, t in self.asked.items() if i not in self.parts and now - t <= PIECE_TIMEOUT)
        room = self.w - in_flight
        if not todo or room <= 0:
            return
        first, n = todo[0], 1
        while n < room and first + n in todo:
            n += 1
        for i in range(first, first + n):
            self.asked[i] = now
        self.n_asked += n
        self.ask(self.frame, first, n)

    def loop(self):
        while self.link.running:
            time.sleep(CYCLE)
            now = time.time()
            s = self.link.state
            for q in self.seen.values():                  # keep only the last HEALTH_WINDOW
                while q and now - q[0] > HEALTH_WINDOW:
                    q.popleft()
            state = "wifi" if self.wifi(now) else None
            if state is None:
                if not self.healthy(now):
                    if self.w > 1 or now >= self.pause_until:
                        self.w = max(1, self.w // 2)
                        self.pause_until = now + 2.0
                    state = "telemetry first"
                elif now < self.pause_until:
                    state = "telemetry first"
                else:
                    state = "on"
                    self.request(now)
                    self.w = min(W_MAX, self.w + 1)     # telemetry at full rate: allow one more piece
            while self.sent_bytes and now - self.sent_bytes[0][0] > 5:
                self.sent_bytes.popleft()
            s["radio_snap"] = {
                "state": state,                      # wifi | on | telemetry first
                "frame": self.jpg_frame if self.jpg else None,
                "age_s": round(now - self.jpg_t, 1) if self.jpg else None,
                "bytes": len(self.jpg) if self.jpg else None,
                "pieces_per_cycle": self.w,
                "rx_bps": round(sum(b for _, b in self.sent_bytes) / 5),
                "receiving": f"{len(self.parts)}/{self.nchunks}" if self.parts else None,
                "asked_got": [self.n_asked, self.n_got],
                "telemetry_hz": {k: round(len(q) / HEALTH_WINDOW, 1) for k, q in self.seen.items()},
            }
