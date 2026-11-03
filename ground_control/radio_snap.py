"""Box camera snapshots over the telemetry radio, ground side (protocol: companion/snap_proto.py).

Telemetry first. The telemetry radio carries the FC data the pilot and the
autopilot logic need; a snapshot is extra. So:

- Snapshots run only while the laptop cannot reach the Pi over Wi-Fi (with
  Wi-Fi, the page shows the real video).
- Every CYCLE it checks the telemetry: ATTITUDE and GLOBAL_POSITION_INT must
  arrive at 85% or more of their requested rates over the last 2 s, and the
  drone heartbeat must be fresh. Only then does it send CTRL (and the Pi
  sends pieces only while CTRL keeps coming).
- The Pi sends the pieces evenly spaced at RATE pieces/s. Each second the rate
  goes up by RATE_STEP while the telemetry is at full rate and the piece loss
  (gaps in the sequence numbers) is low. It goes down by RATE_CUT when the
  loss is high, and the Pi stops (2 s pause, rate halved) when the telemetry
  drops. ArduPilot lowers its own telemetry rates when the radio buffer fills,
  so a telemetry drop means the snapshots use too much of the link.
"""
import sys
import threading
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))
import snap_proto as sp                    # noqa: E402

CYCLE = 0.1             # s between CTRL messages (ground to drone: no telemetry bandwidth; a fast
                        # "complete" lets the Pi start the next picture with little idle time)
HEALTH_WINDOW = 2.0     # s
HEALTH_MIN = 0.85       # of the requested rate
EXPECT = {"ATTITUDE": 10.0, "GLOBAL_POSITION_INT": 5.0}   # Hz, as requested in Link.request_streams
RATE_START, RATE_MIN, RATE_MAX = 8.0, 2.0, 80.0           # pieces/s (one piece: about 145 B on the radio)
RATE_STEP = 2.0         # pieces/s added each second while healthy and the loss is low
RATE_CUT = 0.75         # rate factor each second while the loss is high
LOSS_HIGH, LOSS_LOW = 0.05, 0.02
WIDTH, QUALITY = 320, 20     # colour WebP q20: about 2.1 KB for 320x180


class RadioSnap:
    def __init__(self, link, pi_url_fn):
        self.link = link
        self.pi_url_fn = pi_url_fn          # returns the Pi URL or None
        self.seen = {k: deque() for k in EXPECT}
        self.rate = RATE_START
        self.pause_until = 0.0
        self.frame = 0                      # frame being received (0 = none yet)
        self.parts = {}
        self.nchunks = 0
        self.done_frame = 0                 # last complete frame: tell the Pi (CTRL complete flag)
        self.jpg = None                     # last complete picture (WebP)
        self.jpg_t = 0.0
        self.jpg_frame = 0
        self.period = None                  # smoothed seconds between complete pictures
        self.wifi_ok = False
        self.wifi_checked = 0.0
        self.rx = deque()                   # (t, seq, bytes) of received pieces, last 5 s
        self.last_seq = None
        self.lost = deque()                 # (t, n) pieces lost (sequence gaps), last 5 s
        self.next_rate_t = 0.0
        self.lock = threading.Lock()
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
            _, seq, frame, chunk, nchunks, data = r
            now = time.time()
            with self.lock:
                if self.last_seq is not None:
                    gap = (seq - self.last_seq) & 0xFFFF
                    if 1 < gap < 1000:
                        self.lost.append((now, gap - 1))
                self.last_seq = seq
                self.rx.append((now, seq, 12 + 133))       # one TUNNEL message on the radio: MAVLink2 header + payload
                if frame == self.done_frame:
                    return                          # a resent piece of a finished picture
                if frame != self.frame:
                    self.frame, self.parts, self.nchunks = frame, {}, nchunks   # the Pi moved on
                self.parts[chunk] = data
                if len(self.parts) == self.nchunks:
                    self.jpg = b"".join(self.parts[i] for i in range(self.nchunks))
                    if self.jpg_t:
                        gap_t = now - self.jpg_t
                        self.period = gap_t if self.period is None else self.period + 0.3 * (gap_t - self.period)
                    self.jpg_t, self.jpg_frame, self.done_frame = now, frame, frame
                    self.parts, self.nchunks = {}, 0

    # ---- decide and send CTRL (own thread) ----
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

    def loss(self, now, window=2.0):
        got = sum(1 for t, _, _ in list(self.rx) if now - t <= window)
        lost = sum(n for t, n in list(self.lost) if now - t <= window)
        return lost / (got + lost) if got + lost >= 8 else 0.0

    def send_ctrl(self):
        L = self.link
        if L.sysid is None:
            return
        with self.lock:
            if self.frame and self.frame != self.done_frame:
                payload = sp.pack_ctrl(self.frame, False, self.rate, QUALITY, WIDTH, set(self.parts), self.nchunks)
            else:
                payload = sp.pack_ctrl(self.done_frame, True, self.rate, QUALITY, WIDTH, set(), 0)
        L.send(L.m.mav.tunnel_send, 1, 191, sp.PAYLOAD_TYPE, len(payload),
               list(payload) + [0] * (128 - len(payload)))

    def loop(self):
        while self.link.running:
            time.sleep(CYCLE)
            now = time.time()
            s = self.link.state
            for q in self.seen.values():                  # keep only the last HEALTH_WINDOW
                while q and now - q[0] > HEALTH_WINDOW:
                    q.popleft()
            with self.lock:
                while self.rx and now - self.rx[0][0] > 5:
                    self.rx.popleft()
                while self.lost and now - self.lost[0][0] > 5:
                    self.lost.popleft()
            loss = self.loss(now)
            state = "wifi" if self.wifi(now) else None
            if state is None:
                if not self.healthy(now):
                    if now >= self.pause_until:
                        self.rate = max(RATE_MIN, self.rate / 2)
                        self.pause_until = now + 2.0
                    state = "telemetry first"                 # no CTRL: the Pi stops within 1.5 s
                elif now < self.pause_until:
                    state = "telemetry first"
                else:
                    state = "on"
                    if now >= self.next_rate_t:               # rate step once each second
                        self.next_rate_t = now + 1.0
                        if loss > LOSS_HIGH:
                            self.rate = max(RATE_MIN, self.rate * RATE_CUT)
                        elif loss < LOSS_LOW:
                            # grow, but stay near what arrives: a rate far above the link
                            # only fills the radio buffer, then the loss and the telemetry drop
                            got = sum(1 for t, _, _ in list(self.rx) if now - t <= 2.0) / 2.0
                            cap = max(RATE_START, 1.25 * got)
                            self.rate = min(RATE_MAX, cap, self.rate + RATE_STEP)
                    self.send_ctrl()
            s["radio_snap"] = {
                "state": state,                      # wifi | on | telemetry first
                "frame": self.jpg_frame if self.jpg else None,
                "age_s": round(now - self.jpg_t, 1) if self.jpg else None,
                "bytes": len(self.jpg) if self.jpg else None,
                "rate_pps": round(self.rate, 1),
                "loss_pct": round(loss * 100, 1),
                "period_s": round(self.period, 2) if self.period else None,
                "rx_bps": round(sum(b for _, _, b in list(self.rx)) / 5),
                "receiving": f"{len(self.parts)}/{self.nchunks}" if self.parts else None,
                "telemetry_hz": {k: round(len(q) / HEALTH_WINDOW, 1) for k, q in self.seen.items()},
            }
