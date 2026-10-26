#!/usr/bin/env python3
"""Live camera view in a browser: http://<pi>:8080/

Passes the camera's own MJPEG frames through without re-encoding, so the
Pi Zero 2 W uses very little CPU. Only one program can use the camera at a time.

/            page that loads /frame.jpg in a loop (works in Safari)
/frame.jpg   the latest frame
/stream      multipart MJPEG (works in Chrome, VLC, OpenCV)
/lid.json    the latest lid detection: box ID, tags, and where the camera and the
             drone are relative to the box (see lid_pose below)

Example:
  python3 cam_stream.py --width 1280 --height 800 --fps 15

Mount (drone body frame, metres): the camera is --mount-fwd ahead of the drone
centre (the bottom-plate underside), --mount-right to the right and --mount-down
below it. It looks straight down with the top of the image toward the drone nose;
--mount-rot turns the camera counter-clockwise (seen from above) from that.
"""
import argparse
import json
import math
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

from lid_tags import LidFinder, camera_matrix

HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("--dev", default="/dev/video0")
ap.add_argument("--width", type=int, default=1280)
ap.add_argument("--height", type=int, default=800)
ap.add_argument("--fps", type=int, default=15)
ap.add_argument("--port", type=int, default=8080)
ap.add_argument("--hfov", type=float, default=None,
                help="horizontal FOV, deg. Default: 48.8 for a Logitech C270, else 70 (OV9281)")
ap.add_argument("--layout", default=os.path.join(HERE, "lid_layout.json"))
ap.add_argument("--detect-hz", type=float, default=5.0)
ap.add_argument("--mount-fwd", type=float, default=0.134, help="m, under the GPS mast")
ap.add_argument("--mount-right", type=float, default=0.0)
ap.add_argument("--mount-down", type=float, default=0.02)
ap.add_argument("--mount-rot", type=float, default=0.0, help="deg")
ap.add_argument("--mav", default="udpout:127.0.0.1:14650",
                help="FC link for the pose over the radio (mav_tunnel.py bridge); 'none' to turn off")
ap.add_argument("--mav-hz", type=float, default=2.0)
a = ap.parse_args()

latest = {"jpg": None, "n": 0}
lid = {"t": 0.0, "frame": -1, "boxes": [], "hz": 0.0, "w": 0, "h": 0, "error": None}


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
        latest["at"] = time.time()
        data = buf.tobytes()
        if not data.startswith(b"\xff\xd8"):        # driver gave decoded pixels: encode
            ok, enc = cv2.imencode(".jpg", buf, [cv2.IMWRITE_JPEG_QUALITY, 80])
            data = enc.tobytes()
        data = add_dht(data)
        with cond:
            latest["jpg"], latest["n"] = data, latest["n"] + 1
            cond.notify_all()


NAME = camera_name(a.dev)
HFOV = a.hfov if a.hfov else (48.8 if "C270" in NAME.upper() else 70.0)


def lid_pose(r):
    """Camera and drone pose in the lid frame from one LidFinder result.

    Lid frame: origin at the sticker centre, +x along the long side (sticker
    right), +y along the short side (sticker top), +z up out of the lid.
    Camera frame: x image right, y image down, z out of the lens.
    """
    R = np.array(r["R"]); t = np.array(r["xyz_m"])
    Rt = R.T                                  # camera frame -> lid frame
    cam = -Rt @ t                             # camera position in the lid frame
    # Drone body axes in the camera frame (camera looks down, image top = nose),
    # then turned by the mount rotation about the down axis.
    c, s = math.cos(math.radians(a.mount_rot)), math.sin(math.radians(a.mount_rot))
    fwd_c = np.array([s, -c, 0.0])
    right_c = np.array([c, s, 0.0])
    down_c = np.array([0.0, 0.0, 1.0])
    to_centre_c = -(a.mount_fwd * fwd_c + a.mount_right * right_c + a.mount_down * down_c)
    centre = cam + Rt @ to_centre_c
    fwd_l = Rt @ fwd_c
    yaw = math.degrees(math.atan2(fwd_l[1], fwd_l[0]))   # nose direction from lid +x, CCW
    down_l = Rt @ down_c
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, -down_l[2]))))
    return {"box": r["box"], "tags": r["tags"], "px_per_cell": round(r["px_per_cell"], 1),
            "camera_m": [round(v, 4) for v in cam], "drone_m": [round(v, 4) for v in centre],
            "yaw_deg": round(yaw, 1), "tilt_deg": round(tilt, 1),
            "range_m": round(r["range_m"], 3), "outlines": r["outlines"]}


def watchdog():
    """The webcam can stop sending frames (seen 2026-10-25: cap.read() blocked
    after about 9 min). Then exit, and systemd restarts the program (Restart=always)."""
    time.sleep(15)                             # time to open the camera
    while True:
        time.sleep(1)
        if time.time() - latest.get("at", 0) > 5:
            print("no camera frame for 5 s: exiting so systemd restarts the camera", flush=True)
            os._exit(3)


def detect():
    finder = LidFinder(a.layout)
    seen, n, t0 = -1, 0, time.time()
    while True:
        with cond:
            cond.wait_for(lambda: latest["n"] != seen, timeout=2)
            if latest["n"] == seen:              # no new frame: do not report an old pose as new
                continue
            jpg, seen = latest["jpg"], latest["n"]
        if jpg is None:
            continue
        start = time.time()
        try:
            gray = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_GRAYSCALE)
            K = camera_matrix(gray.shape[1], gray.shape[0], HFOV)
            boxes = [lid_pose(r) for r in finder.find(gray, K)]
            err = None
        except Exception as e:                  # keep the stream running if one frame fails
            boxes, err = [], f"{type(e).__name__}: {e}"
        n += 1
        if time.time() - t0 > 2:
            lid["hz"], n, t0 = round(n / (time.time() - t0), 1), 0, time.time()
        lid.update(t=time.time(), frame=seen, boxes=boxes, w=gray.shape[1], h=gray.shape[0], error=err)
        time.sleep(max(0.0, 1.0 / a.detect_hz - (time.time() - start)))


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

    def end_headers(self):
        # The ground-control page on the laptop reads these from another origin.
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/lid.json"):
            body = json.dumps(dict(lid, camera=NAME, hfov_deg=HFOV, now=time.time(),
                                   mount={"fwd": a.mount_fwd, "right": a.mount_right,
                                          "down": a.mount_down, "rot": a.mount_rot})).encode()
            self.send_response(200)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
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


def wifi_ip():
    """This Pi's IPv4 address on the default route (no packet is sent)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
            u.connect(("192.0.2.1", 9))
            ip = u.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def snapshots(m, send_lock):
    """Answer snapshot requests from ground control (snap_proto.py).

    Sends only the pieces that ground control asked for; ground control asks
    only while the telemetry arrives at its full rate (telemetry first)."""
    import snap_proto as sp
    frame_id, chunks, queue = 0, [], []
    while True:
        try:
            msg = m.recv_match(type="TUNNEL", blocking=True, timeout=0.05)
        except OSError:
            msg = None
        if msg is not None and msg.target_system == 1 and msg.target_component == 191 \
                and msg.payload_type == sp.PAYLOAD_TYPE:
            r = sp.unpack(bytes(msg.payload[:msg.payload_length]))
            if r and r[0] == "req":
                _, frame, first, count, quality, width = r
                peer = (msg.get_srcSystem(), msg.get_srcComponent())
                if frame == 0 or frame != frame_id or not chunks:
                    jpg = latest["jpg"]
                    if jpg is None or time.time() - latest.get("at", 0) > 2:
                        continue                          # no fresh camera frame: say nothing
                    gray = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_GRAYSCALE)
                    w = max(64, min(width or 320, 640))
                    h = int(round(gray.shape[0] * w / gray.shape[1]))
                    # WebP: 2.4x smaller than JPEG at the same quality (measured 2026-10-25:
                    # 320x180 grey, WebP q30 1446 B / 36.5 dB against JPEG q30 3504 B / 36.0 dB)
                    ok, enc = cv2.imencode(".webp", cv2.resize(gray, (w, h), interpolation=cv2.INTER_AREA),
                                           [cv2.IMWRITE_WEBP_QUALITY, max(1, min(quality or 20, 100))])
                    data = enc.tobytes()
                    frame_id = frame_id % 65535 + 1
                    chunks = [data[i:i + sp.CHUNK] for i in range(0, len(data), sp.CHUNK)]
                    first = 0
                queue = [(peer, i) for i in range(first, min(first + count, len(chunks)))]
        # send the asked pieces, spaced so the FC can mix in its telemetry
        if queue:
            peer, i = queue.pop(0)
            payload = sp.pack_data(frame_id, i, len(chunks), chunks[i])
            try:
                with send_lock:
                    m.mav.tunnel_send(peer[0], peer[1], sp.PAYLOAD_TYPE, len(payload),
                                      list(payload) + [0] * (128 - len(payload)))
            except OSError:
                pass
            time.sleep(0.02)


def radio():
    """Send the pose to the ground station over the radio, without Wi-Fi.

    Three DEBUG_VECT messages with no target, so the FC forwards them to the
    radio (about 250 B/s at 2 Hz):
      LIDATT  x = box id (-1 = no box in view), y = yaw deg, z = tilt deg
      LIDPOS  x, y, z = drone centre in the lid frame, m
      LIDCAM  x = camera height m, y = px per tag cell, z = number of tags
    time_usec = the detection time.
    Every 5 s also PIIP: x = a*256+b, y = c*256+d of the Wi-Fi IP a.b.c.d,
    z = the HTTP port, so ground control finds this page when the name
    packet-cv.local does not resolve (other subnet) or the DHCP address changes.
    """
    os.environ.setdefault("MAVLINK20", "1")
    from pymavlink import mavutil
    m = mavutil.mavlink_connection(a.mav, source_system=1, source_component=191)
    send_lock = threading.Lock()
    threading.Thread(target=snapshots, args=(m, send_lock), daemon=True).start()
    next_ip = 0.0
    while True:
        time.sleep(1.0 / a.mav_hz)
        if time.time() >= next_ip:
            next_ip = time.time() + 5
            ip = wifi_ip()
            if ip:
                o = [int(v) for v in ip.split(".")]
                try:
                  with send_lock:
                    m.mav.debug_vect_send(b"PIIP", int(time.time() * 1e6), float(o[0] * 256 + o[1]),
                                          float(o[2] * 256 + o[3]), float(a.port))
                except OSError:
                    pass
        if time.time() - lid["t"] > 1.5:        # detection stopped: send nothing
            continue
        us = int(lid["t"] * 1e6)
        b = lid["boxes"][0] if lid["boxes"] else None
        try:
          with send_lock:
            if b is None:
                m.mav.debug_vect_send(b"LIDATT", us, -1.0, 0.0, 0.0)
                continue
            m.mav.debug_vect_send(b"LIDATT", us, float(b["box"]), b["yaw_deg"], b["tilt_deg"])
            m.mav.debug_vect_send(b"LIDPOS", us, *map(float, b["drone_m"]))
            m.mav.debug_vect_send(b"LIDCAM", us, float(b["camera_m"][2]), float(b["px_per_cell"]),
                                  float(len(b["tags"])))
        except OSError:
            time.sleep(1)


threading.Thread(target=grab, daemon=True).start()
threading.Thread(target=watchdog, daemon=True).start()
if a.mav != "none":
    threading.Thread(target=radio, daemon=True).start()
threading.Thread(target=detect, daemon=True).start()
print(f"streaming on http://0.0.0.0:{a.port}/  camera {NAME}, HFOV {HFOV} deg", flush=True)
ThreadingHTTPServer(("", a.port), H).serve_forever()
