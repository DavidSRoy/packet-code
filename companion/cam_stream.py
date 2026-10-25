#!/usr/bin/env python3
"""Live camera view in a browser: http://<pi>:8080/

Passes the camera's own MJPEG frames through without re-encoding, so the
Pi Zero 2 W uses very little CPU. Only one program can use the camera at a time.

Example:
  python3 cam_stream.py --width 1280 --height 800 --fps 15
"""
import argparse
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
        with cond:
            latest["jpg"], latest["n"] = data, latest["n"] + 1
            cond.notify_all()


PAGE = b"""<!doctype html><html><head><meta name=viewport content="width=device-width">
<title>Packet camera</title><style>body{margin:0;background:#000;color:#ccc;font:14px system-ui}
img{display:block;width:100vw;height:calc(100vh - 28px);object-fit:contain}p{margin:6px 10px}</style></head>
<body><p>packet-cv &middot; Arducam OV9281 &middot; live</p><img src="/stream"></body></html>"""


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
