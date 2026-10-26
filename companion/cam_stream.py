#!/usr/bin/env python3
"""Box camera on the Pi: lid detection, H.264 video and the pose over the radio.

The camera gives raw YUYV frames. Each user takes what it needs from them,
with no JPEG step:
  detection       the Y plane (grey), full frame, every frame (10 Hz)
  /h264           hardware H.264 (h264.py), started on demand; the ground-control
                  page decodes it with WebCodecs, ground control forwards it to the API
  radio pictures  WebP q20 from the Y plane, on request (snap_proto.py)

/lid.json    the latest lid detection: box ID, tags, and where the camera and the
             drone are relative to the box (see lid_pose below)
/h264        the video stream (record format in h264.py)

Example:
  python3 cam_stream.py --width 1280 --height 720 --fps 10

A Logitech C270 gives YUYV 1280x720 at 10 fps (USB 2 bandwidth limit).

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

from h264 import WifiH264
from lid_tags import LidFinder, camera_matrix

HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("--dev", default="/dev/video0")
ap.add_argument("--width", type=int, default=1280)
ap.add_argument("--height", type=int, default=720)
ap.add_argument("--fps", type=int, default=10)
ap.add_argument("--port", type=int, default=8080)
ap.add_argument("--hfov", type=float, default=None,
                help="horizontal FOV, deg. Default: 48.8 for a Logitech C270, else 70 (OV9281)")
ap.add_argument("--layout", default=os.path.join(HERE, "lid_layout.json"))
ap.add_argument("--mount-fwd", type=float, default=0.134, help="m, under the GPS mast")
ap.add_argument("--mount-right", type=float, default=0.0)
ap.add_argument("--mount-down", type=float, default=0.02)
ap.add_argument("--mount-rot", type=float, default=0.0, help="deg")
ap.add_argument("--mav", default="udpout:127.0.0.1:14650",
                help="FC link for the pose over the radio (mav_tunnel.py bridge); 'none' to turn off")
ap.add_argument("--mav-hz", type=float, default=2.0)
a = ap.parse_args()

latest = {"y": None, "yuyv": None, "n": 0, "at": 0.0}
lid = {"t": 0.0, "frame": -1, "boxes": [], "hz": 0.0, "w": 0, "h": 0, "error": None}


def camera_name(dev):
    try:
        with open(f"/sys/class/video4linux/{os.path.basename(os.path.realpath(dev))}/name") as f:
            return f.read().strip()
    except OSError:
        return dev
cond = threading.Condition()


def grab():
    cap = cv2.VideoCapture(a.dev, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
    cap.set(cv2.CAP_PROP_FPS, a.fps)
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)          # keep the raw YUYV bytes
    while True:
        ok, buf = cap.read()
        if not ok or buf is None:
            time.sleep(0.05)
            continue
        t = time.time()
        if buf.ndim == 3 and buf.shape[2] == 2:     # YUYV: (h, w, 2), Y in channel 0
            # copy: in raw mode the array can point into the driver's capture buffer,
            # which the next capture overwrites while the encoder and detection read it
            # (seen 2026-10-25: torn, smeared H.264 frames and missed tags)
            yuyv = buf.copy()
        else:                                       # the driver gave another layout: skip it
            print(f"unexpected frame shape {buf.shape}", flush=True)
            time.sleep(1)
            continue
        vid.feed(yuyv, t)
        with cond:
            latest.update(yuyv=yuyv, y=yuyv[:, :, 0], n=latest["n"] + 1, at=t)
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
            "range_m": round(r["range_m"], 3), "outlines": r["outlines"],
            "rvec": [round(float(v), 5) for v in cv2.Rodrigues(R)[0].ravel()],   # lid -> camera rotation
            "tvec": [round(float(v), 4) for v in t]}                            # lid origin in the camera frame, m


def watchdog():
    """The webcam can stop sending frames (seen 2026-10-25: cap.read() blocked
    after about 9 min). Then exit, and systemd restarts the program (Restart=always)."""
    time.sleep(15)                             # time to open the camera
    while True:
        time.sleep(1)
        if time.time() - latest["at"] > 5:
            print("no camera frame for 5 s: exiting so systemd restarts the camera", flush=True)
            os._exit(3)


def detect():
    """Full frame, full size, every frame, never an old frame twice. One search takes
    about 57 ms on the Pi Zero 2 (lid_tags.py, one pass for both dictionaries), so one
    worker keeps up with the camera (10 fps)."""
    finder = LidFinder(a.layout)
    seen, n, t0 = -1, 0, time.time()
    while True:
        with cond:
            cond.wait_for(lambda: latest["n"] != seen and latest["y"] is not None, timeout=2)
            if latest["n"] == seen or latest["y"] is None:
                continue                         # no new frame: do not report an old pose as new
            y, seen, t_cap = latest["y"], latest["n"], latest["at"]
        gray = np.ascontiguousarray(y)
        try:
            K = camera_matrix(gray.shape[1], gray.shape[0], HFOV)
            boxes = [lid_pose(r) for r in finder.find(gray, K)]
            err = None
        except Exception as e:                  # keep the stream running if one frame fails
            boxes, err = [], f"{type(e).__name__}: {e}"
        n += 1
        if time.time() - t0 > 2:
            lid["hz"], n, t0 = round(n / (time.time() - t0), 1), 0, time.time()
        lid.update(t=time.time(), frame=seen, boxes=boxes, w=gray.shape[1], h=gray.shape[0],
                   error=err, latency_ms=round((time.time() - t_cap) * 1000))


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        # The ground-control page on the laptop reads these from another origin.
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/lid.json"):
            body = json.dumps(dict(lid, frames=latest["n"], camera=NAME, hfov_deg=HFOV, now=time.time(), h264=vid.stats,
                                   mount={"fwd": a.mount_fwd, "right": a.mount_right,
                                          "down": a.mount_down, "rot": a.mount_rot})).encode()
            self.send_response(200)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/h264"):
            self.send_response(200)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            try:
                vid.serve(lambda b: (self.wfile.write(b), self.wfile.flush()))
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            return
        self.send_error(404)


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
    """Send radio snapshots to ground control (push protocol, snap_proto.py).

    The pieces go out evenly spaced at the rate ground control allows, and only
    while its CTRL messages keep coming (it stops them when the telemetry is not
    at full rate): telemetry first."""
    import snap_proto as sp
    ctrl_t, rate, quality, width, peer = 0.0, 0.0, 20, 320, None
    frame_id, chunks, queue, seq = 0, [], [], 0
    pass_done = False          # first pass of the current picture sent
    last_sent, frame_t = 0.0, 0.0
    next_t = 0.0
    while True:
        now = time.time()
        wait = max(0.002, min(0.05, next_t - now)) if queue and rate > 0 else 0.05
        try:
            msg = m.recv_match(type="TUNNEL", blocking=True, timeout=wait)
        except OSError:
            msg = None
        now = time.time()
        if msg is not None and msg.target_system == 1 and msg.target_component == 191 \
                and msg.payload_type == sp.PAYLOAD_TYPE:
            r = sp.unpack(bytes(msg.payload[:msg.payload_length]))
            if r and r[0] == "ctrl":
                _, frame, complete, rate, quality, width, have, nbits = r
                ctrl_t, peer = now, (msg.get_srcSystem(), msg.get_srcComponent())
                if chunks and frame == frame_id:
                    if complete:
                        chunks, queue = [], []                    # ground has it: next picture
                    elif pass_done and not queue and now - last_sent > 0.3:
                        queue = [i for i in range(len(chunks)) if i not in have]   # send the missing again
        if now - ctrl_t > sp.CTRL_TIMEOUT or rate <= 0 or peer is None:
            continue                                              # nobody asks: send nothing
        if chunks and now - frame_t > 6:                          # stuck picture: give up, take a new one
            chunks, queue = [], []
        if not chunks:
            yuyv = latest["yuyv"]                                 # the page draws the box from the live pose on top
            if yuyv is None or now - latest["at"] > 2:
                continue                                          # no fresh camera frame: say nothing
            w = max(64, min(width or 320, 640))
            h = int(round(yuyv.shape[0] * w / yuyv.shape[1]))
            # colour: about 19% more bytes than grey (measured 2026-10-25, 320x180 q20: 2076 B / 1738 B)
            small = cv2.resize(cv2.cvtColor(yuyv, cv2.COLOR_YUV2BGR_YUYV), (w, h), interpolation=cv2.INTER_AREA)
            ok, enc = cv2.imencode(".webp", small, [cv2.IMWRITE_WEBP_QUALITY, max(1, min(quality or 20, 100))])
            data = enc.tobytes()
            frame_id = frame_id % 65535 + 1
            chunks = [data[i:i + sp.CHUNK] for i in range(0, len(data), sp.CHUNK)]
            queue, pass_done, frame_t = list(range(len(chunks))), False, now
            next_t = max(next_t, now)
        if queue and now >= next_t:
            i = queue.pop(0)
            seq = (seq + 1) & 0xFFFF
            payload = sp.pack_data(seq, frame_id, i, len(chunks), chunks[i])
            try:
                with send_lock:
                    m.mav.tunnel_send(peer[0], peer[1], sp.PAYLOAD_TYPE, len(payload),
                                      list(payload) + [0] * (128 - len(payload)))
            except OSError:
                pass
            last_sent = now
            next_t = max(next_t, now - 0.5 / rate) + 1.0 / rate   # even spacing; no catch-up burst
            if not queue:
                pass_done = True


def radio():
    """Send the pose to the ground station over the radio, without Wi-Fi.

    DEBUG_VECT messages with no target, so the FC forwards them to the
    radio (about 420 B/s at 2 Hz). LIDATT comes last: ground control puts the
    parts with the same time_usec (the detection time) together when it arrives.
      LIDRV   x, y, z = camera rotation (Rodrigues vector, lid -> camera)
      LIDTV   x, y, z = lid origin in the camera frame, m
              (with LIDRV, ground control draws the tags on the radio snapshot)
      LIDPOS  x, y, z = drone centre in the lid frame, m
      LIDCAM  x = camera height m, y = px per tag cell, z = number of tags
      LIDATT  x = box id (-1 = no box in view), y = yaw deg, z = tilt deg
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
            m.mav.debug_vect_send(b"LIDRV", us, *map(float, b["rvec"]))
            m.mav.debug_vect_send(b"LIDTV", us, *map(float, b["tvec"]))
            m.mav.debug_vect_send(b"LIDPOS", us, *map(float, b["drone_m"]))
            m.mav.debug_vect_send(b"LIDCAM", us, float(b["camera_m"][2]), float(b["px_per_cell"]),
                                  float(len(b["tags"])))
            m.mav.debug_vect_send(b"LIDATT", us, float(b["box"]), b["yaw_deg"], b["tilt_deg"])
        except OSError:
            time.sleep(1)


vid = WifiH264(a.width, a.height, a.fps)
threading.Thread(target=grab, daemon=True).start()
threading.Thread(target=watchdog, daemon=True).start()
if a.mav != "none":
    threading.Thread(target=radio, daemon=True).start()
threading.Thread(target=detect, daemon=True).start()
print(f"streaming on http://0.0.0.0:{a.port}/  camera {NAME}, HFOV {HFOV} deg", flush=True)
ThreadingHTTPServer(("", a.port), H).serve_forever()
