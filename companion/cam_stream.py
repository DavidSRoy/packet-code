#!/usr/bin/env python3
"""Live camera view in a browser: http://<pi>:8080/

Passes the camera's own MJPEG frames through without re-encoding, so the
Pi Zero 2 W uses very little CPU. Only one program can use the camera at a time.

/            page that loads /frame.jpg in a loop (works in Safari)
/frame.jpg   the latest frame
/stream      multipart MJPEG (works in Chrome, VLC, OpenCV)

Example:
  python3 cam_stream.py --width 1280 --height 800 --fps 15
"""
import argparse
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--dev", default="/dev/video0")
ap.add_argument("--width", type=int, default=1280)
ap.add_argument("--height", type=int, default=800)
ap.add_argument("--fps", type=int, default=15)
ap.add_argument("--port", type=int, default=8080)
a = ap.parse_args()

latest = {"jpg": None, "n": 0}


def _std_dht():
    """The standard JPEG Huffman tables (DHT segments), taken from an OpenCV JPEG."""
    import numpy as np
    ok, enc = cv2.imencode(".jpg", np.zeros((16, 16, 3), np.uint8))
    d, i, out = enc.tobytes(), 2, b""
    while i < len(d) and d[i] == 0xFF and d[i + 1] != 0xDA:
        n = int.from_bytes(d[i + 2:i + 4], "big")
        if d[i + 1] == 0xC4:
            out += d[i:i + 2 + n]
        i += 2 + n
    return out


DHT = _std_dht()


def add_dht(jpg):
    """Many UVC cameras leave the Huffman tables out of MJPEG frames.
    Chrome and OpenCV do not care, but Safari cannot show such a frame."""
    head = jpg[:4096]
    if b"\xff\xc4" in head:
        return jpg
    sos = head.find(b"\xff\xda")
    return jpg if sos < 0 else jpg[:sos] + DHT + jpg[sos:]


def camera_name(dev):
    try:
        with open(f"/sys/class/video4linux/{os.path.basename(os.path.realpath(dev))}/name") as f:
            return f.read().strip()
    except OSError:
        return dev
cond = threading.Condition()


def grab():
    cap = cv2.VideoCapture(a.dev, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
    cap.set(cv2.CAP_PROP_FPS, a.fps)
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)          # keep the raw JPEG bytes
    while True:
        ok, buf = cap.read()
        if not ok or buf is None:
            time.sleep(0.05)
            continue
        data = buf.tobytes()
        if not data.startswith(b"\xff\xd8"):        # driver gave decoded pixels: encode
            ok, enc = cv2.imencode(".jpg", buf, [cv2.IMWRITE_JPEG_QUALITY, 80])
            data = enc.tobytes()
        data = add_dht(data)
        with cond:
            latest["jpg"], latest["n"] = data, latest["n"] + 1
            cond.notify_all()


PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width">
<title>Packet camera</title><style>body{margin:0;background:#000;color:#ccc;font:14px system-ui}
img{display:block;width:100vw;height:calc(100vh - 28px);object-fit:contain}p{margin:6px 10px}</style></head>
<body><p>packet-cv &middot; CAMERA &middot; <span id=fps>connecting</span></p><img id=v>
<script>
const v = document.getElementById("v"), fps = document.getElementById("fps");
let n = 0, t0 = performance.now();
function next() { v.src = "/frame.jpg?" + Date.now(); }
v.onload = () => { n++; const dt = (performance.now() - t0) / 1000;
  if (dt > 2) { fps.textContent = (n / dt).toFixed(1) + " fps"; n = 0; t0 = performance.now(); }
  next(); };
v.onerror = () => { fps.textContent = "no frame"; setTimeout(next, 500); };
next();
</script></body></html>""".replace("CAMERA", camera_name(a.dev)).encode()


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(PAGE)
            return
        if self.path.startswith("/frame.jpg"):
            with cond:
                cond.wait_for(lambda: latest["jpg"] is not None, timeout=3)
                jpg = latest["jpg"]
            if jpg is None:
                self.send_error(503, "no frame yet")
                return
            self.send_response(200)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpg)))
            self.end_headers()
            self.wfile.write(jpg)
            return
        if self.path != "/stream":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        seen = -1
        try:
            while True:
                with cond:
                    cond.wait_for(lambda: latest["n"] != seen, timeout=2)
                    jpg, seen = latest["jpg"], latest["n"]
                if jpg is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                 + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass


threading.Thread(target=grab, daemon=True).start()
print(f"streaming on http://0.0.0.0:{a.port}/", flush=True)
ThreadingHTTPServer(("", a.port), H).serve_forever()
