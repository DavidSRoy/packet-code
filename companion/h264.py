"""Hardware H.264 video for the Wi-Fi view (Pi Zero 2 W VideoCore encoder).

The camera gives raw YUYV frames. While at least one viewer is connected, an
ffmpeg process sends them to the hardware encoder (h264_v4l2m2m,
/dev/video11), which takes YUYV directly: no decode and no colour conversion
on the CPU. With no viewer for IDLE_S, ffmpeg stops.

Measured 2026-10-25 on this Pi, YUYV 1280x720 at 10 fps: 10 fps out at
1.5 Mbit/s, about 0.16 CPU cores for ffmpeg.

Stream format for /h264 (one record for each frame):
  4 bytes  length of the data, big-endian
  1 byte   flags: 1 = keyframe (SPS and PPS are in front of it)
  8 bytes  capture time, ms since epoch, big-endian double
  data     H.264 Annex B access unit (start codes, single slice)
"""
import collections
import struct
import subprocess
import threading
import time

IDLE_S = 10.0
REC = struct.Struct(">IBd")


def nal_units(buf):
    """Split an Annex B buffer. Returns (list of (start, nal_type)), offset of the last start code."""
    out, i, n = [], 0, len(buf)
    while True:
        j = buf.find(b"\x00\x00\x01", i)
        if j < 0 or j + 3 >= n:
            break
        out.append((j - 1 if j > 0 and buf[j - 1] == 0 else j, buf[j + 3] & 0x1F))
        i = j + 3
    return out


class WifiH264:
    def __init__(self, width, height, fps, bitrate_k=1500):
        self.w, self.h, self.fps, self.bitrate_k = width, height, fps, bitrate_k
        self.proc = None
        self.lock = threading.Lock()
        self.cond = threading.Condition()
        self.frames = []          # recent (seq, key, t_ms, data), newest last
        self.seq = 0
        self.viewers = 0
        self.last_viewer = 0.0
        self.pending_t = []       # capture times of frames sent to ffmpeg, in order
        self.stats = {"fps": 0.0, "kbps": 0.0, "running": False}
        self.inq = collections.deque(maxlen=2)   # newest camera frames for the encoder
        self.inq_cond = threading.Condition()
        threading.Thread(target=self._idle_watch, daemon=True).start()
        threading.Thread(target=self._write, daemon=True).start()

    # ---- viewers ----
    def add_viewer(self):
        with self.lock:
            self.viewers += 1
            self.last_viewer = time.time()
            if self.proc is None:
                self._start()

    def remove_viewer(self):
        with self.lock:
            self.viewers -= 1
            self.last_viewer = time.time()

    def _idle_watch(self):
        while True:
            time.sleep(1)
            with self.lock:
                if self.proc and self.viewers <= 0 and time.time() - self.last_viewer > IDLE_S:
                    self._stop()

    # ---- encoder ----
    def _start(self):
        g = max(1, int(round(self.fps)))      # a keyframe each second: a new viewer starts within 1 s
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
               "-fflags", "nobuffer", "-probesize", "32", "-analyzeduration", "0",
               "-f", "rawvideo", "-pix_fmt", "yuyv422", "-s", f"{self.w}x{self.h}",
               "-framerate", str(self.fps), "-i", "pipe:0",
               "-c:v", "h264_v4l2m2m", "-b:v", f"{self.bitrate_k}k", "-g", str(g), "-bf", "0",
               "-pix_fmt", "yuyv422", "-bsf:v", "dump_extra=freq=keyframe",
               "-flush_packets", "1", "-f", "h264", "pipe:1"]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        self.pending_t = []
        self.stats["running"] = True
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        print("h264: encoder started", flush=True)

    def _stop(self):
        p, self.proc = self.proc, None
        self.stats["running"] = False
        if p:
            try:
                p.stdin.close()
            except OSError:
                pass
            p.kill()
            print("h264: encoder stopped (no viewer)", flush=True)

    def feed(self, yuyv, t):
        """Give one camera frame (numpy YUYV, shape (h, w, 2)). Called from the camera thread; never blocks."""
        if self.proc is None:
            return
        with self.inq_cond:
            self.inq.append((yuyv, t))             # an old frame falls out when the encoder is behind
            self.inq_cond.notify()

    def _write(self):
        while True:
            with self.inq_cond:
                self.inq_cond.wait_for(lambda: self.inq, timeout=1)
                if not self.inq:
                    continue
                yuyv, t = self.inq.popleft()
            p = self.proc
            if p is None or len(self.pending_t) > 4:    # encoder behind: skip, keep the delay low
                continue
            try:
                self.pending_t.append(t)
                p.stdin.write(memoryview(yuyv).cast("B") if yuyv.flags.c_contiguous else yuyv.tobytes())
            except (BrokenPipeError, OSError, ValueError):
                with self.lock:
                    if self.proc is p:
                        self.proc = None
                        self.stats["running"] = False

    def _read(self, p):
        buf = b""
        n_t0, n, nbytes = time.time(), 0, 0
        while True:
            chunk = p.stdout.read(65536) if p.stdout else b""
            if not chunk:
                break
            buf += chunk
            nals = nal_units(buf)
            # a frame ends where the next frame's first NAL starts; group SPS/PPS/SEI with the slice
            start = 0
            au_start = None
            for k, (pos, t) in enumerate(nals):
                if au_start is None:
                    au_start = pos
                if t in (1, 5):                    # slice: the frame is complete at the next start code
                    if k + 1 < len(nals):
                        end = nals[k + 1][0]
                        data = buf[au_start:end]
                        key = any(tt == 5 for pp, tt in nals if au_start <= pp < end)
                        self._emit(data, key)
                        n += 1
                        nbytes += len(data)
                        au_start = None
                        start = end
            buf = buf[start:]
            if time.time() - n_t0 >= 2:
                dt = time.time() - n_t0
                self.stats["fps"], self.stats["kbps"] = round(n / dt, 1), round(nbytes * 8 / dt / 1000)
                n_t0, n, nbytes = time.time(), 0, 0

    def _emit(self, data, key):
        t = self.pending_t.pop(0) if self.pending_t else time.time()
        with self.cond:
            self.seq += 1
            self.frames.append((self.seq, key, t * 1000.0, data))
            del self.frames[:-60]
            self.cond.notify_all()

    # ---- one viewer (HTTP handler thread) ----
    def serve(self, write):
        """Write frames to one viewer, starting at the next keyframe, until the viewer leaves."""
        self.add_viewer()
        try:
            with self.cond:
                seen = self.seq
            started = False
            while True:
                with self.cond:
                    self.cond.wait_for(lambda: self.seq != seen, timeout=3)
                    new = [f for f in self.frames if f[0] > seen]
                    if new:
                        seen = new[-1][0]
                for _, key, t_ms, data in new:
                    if not started and not key:
                        continue                   # the decoder needs a keyframe first
                    started = True
                    write(REC.pack(len(data), 1 if key else 0, t_ms) + data)
                with self.lock:
                    self.last_viewer = time.time()
                    if self.proc is None:
                        self._start()
        finally:
            self.remove_viewer()
