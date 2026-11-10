#!/usr/bin/env python3
"""Box camera on the Pi: lid detection, H.264 video and the pose over the radio.

The camera gives raw YUYV frames. Each user takes what it needs from them,
with no JPEG step:
  detection       the Y plane (grey), full frame, newest frame each time (about 5 Hz)
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
import collections
import json
import math
import os
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

from h264 import WifiH264
from imu_pose import ImuPose, wrap
from lid_pose import Mount, imu_fix as _imu_fix, lid_pose as _lid_pose
from lid_tags import LidFinder, camera_matrix

HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("--dev", default="/dev/video0")
ap.add_argument("--width", type=int, default=1280)
ap.add_argument("--height", type=int, default=720)
ap.add_argument("--fps", type=int, default=10)
ap.add_argument("--port", type=int, default=8080)
ap.add_argument("--hfov", type=float, default=None,
                help="horizontal FOV, deg. Default: 48.8 for a Logitech C270, 70.4 for a C920 (78 deg diagonal, 16:9), else 70 (OV9281)")
ap.add_argument("--layout", default=os.path.join(HERE, "lid_layout.json"))
ap.add_argument("--mount-fwd", type=float, default=0.134, help="m, under the GPS mast")
ap.add_argument("--mount-right", type=float, default=0.0)
ap.add_argument("--mount-down", type=float, default=0.02)
ap.add_argument("--mount-rot", type=float, default=0.0, help="deg")
ap.add_argument("--mav", default="udpout:127.0.0.1:14650",
                help="FC link for the pose over the radio (mav_tunnel.py bridge); 'none' to turn off")
ap.add_argument("--mav-hz", type=float, default=2.0)
ap.add_argument("--detect-scale", type=float, default=0.4,
                help="shrink each frame by this before the tag search (0.4 = 512x288 from 1280x720). Measured "
                     "2026-11-02 on the Pi Zero 2 W: 1.0 = 3.4 Hz, 0.5 = 9.3 Hz. Fine for hovers and pickups "
                     "(tags about 9 px/cell at 0.25 m); the far range shrinks with it")
ap.add_argument("--exposure", type=int, default=40,
                help="fixed exposure, 100 us units (40 = 4 ms); 0 = the camera's auto exposure. Auto ran 33 ms "
                     "indoors: the motor vibration at spin-up smeared the tags out of detection (2026-11-02). "
                     "4 ms with gain 200 still found both tags at 10 Hz")
ap.add_argument("--gain", type=int, default=200, help="camera gain with --exposure (C920: 0-255)")
ap.add_argument("--imu-tilt", type=int, default=1,
                help="1 = the tilt from the FC attitude (zeroed with the tags while still and disarmed), the "
                     "heading and position from the tags (imu_pose.py); 0 = everything from the tags")
ap.add_argument("--imu-lag", type=float, default=0.0,
                help="s: the camera frame is this much older than its capture time (t_cap) for the attitude match")
ap.add_argument("--rec-dir", default=os.path.expanduser("~/rec"),
                help="while the FC is armed (and REC_PRE_S before): every searched frame (JPEG, as the CV saw it) "
                     "and its full CV result (cv.jsonl), one folder per arming; 'none' to turn off")
ap.add_argument("--rec-keep", type=int, default=10, help="recordings to keep (oldest deleted)")
ap.add_argument("--vision", type=int, default=1,
                help="1 = send the lid pose to the FC as VISION_POSITION_ESTIMATE (EKF ExternalNav); 0 = off")
a = ap.parse_args()

latest = {"y": None, "yuyv": None, "n": 0, "at": 0.0}
lid = {"t": 0.0, "frame": -1, "boxes": [], "hz": 0.0, "w": 0, "h": 0, "error": None,
       "t_cap": 0.0, "skipped_pct": 0.0}   # t_cap: capture time of the frame this result is from (= its /h264 record time)


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
    if a.exposure > 0:                            # after opening: opening can reset the controls
        r = subprocess.run(["v4l2-ctl", "-d", a.dev, "-c", "auto_exposure=1", "-c", f"exposure_time_absolute={a.exposure}",
                            "-c", f"gain={a.gain}", "-c", "exposure_dynamic_framerate=0"], capture_output=True, text=True)
        print(f"exposure {a.exposure * 0.1:g} ms, gain {a.gain}" + (f" (v4l2-ctl: {r.stderr.strip()})" if r.returncode else ""),
              flush=True)
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
HFOV = a.hfov if a.hfov else (48.8 if "C270" in NAME.upper() else 70.4 if "C920" in NAME.upper() else 70.0)


MOUNT = Mount(a.mount_fwd, a.mount_right, a.mount_down, a.mount_rot)


def lid_pose(r):
    """Camera and drone pose in the lid frame from one LidFinder result (lid_pose.py)."""
    return _lid_pose(r, MOUNT)


def watchdog():
    """The webcam can stop sending frames (seen 2026-10-25: cap.read() blocked
    after about 9 min). Then exit, and systemd restarts the program (Restart=always)."""
    time.sleep(15)                             # time to open the camera
    while True:
        time.sleep(1)
        if time.time() - latest["at"] > 5:
            print("no camera frame for 5 s: exiting so systemd restarts the camera", flush=True)
            os._exit(3)


att_buf = collections.deque(maxlen=200)   # FC ATTITUDE: (Pi receive time, roll, pitch, yaw), newest last
imu = ImuPose(a.mount_rot)
imu_lock = threading.Lock()
imu_last = {}                             # box -> attitude of its last zero frame (stillness check)


def att_at(t):
    """The FC attitude at time t (interpolated), or None without a fresh one around t."""
    buf = list(att_buf)
    for (t0, *a0), (t1, *a1) in zip(buf, buf[1:]):
        if t0 <= t <= t1 and t1 - t0 < 0.2:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return (a0[0] + f * (a1[0] - a0[0]), a0[1] + f * (a1[1] - a0[1]), a0[2] + f * wrap(a1[2] - a0[2]))
    return None


def imu_fix(r, t_cap, K):
    """The IMU pose of one LidFinder result (lid_pose.py), with the stillness state and lock kept here."""
    att = att_at(t_cap - a.imu_lag)
    with imu_lock:
        return _imu_fix(r, att, K, imu, MOUNT, zero=not fc["armed"] and time.time() - fc["t"] < 3.0, last=imu_last)


DETECT_WORKERS = 2     # each worker takes the newest frame no worker has taken yet (alternate frames)
claim = {"n": -1}
rate = {"n": 0, "t0": time.time(), "skipped": 0}


def detect():
    """Full frame, full size, always the newest frame, never an old frame twice. One
    search takes about 190 ms on the Pi Zero 2 with 7 threshold windows (lid_tags.py);
    two workers run on alternate frames, and a slower worker never puts back an older pose."""
    finder = LidFinder(a.layout)
    while True:
        with cond:
            cond.wait_for(lambda: latest["n"] > claim["n"] and latest["y"] is not None, timeout=2)
            if latest["n"] <= claim["n"] or latest["y"] is None:
                continue                         # no new frame: do not report an old pose as new
            y, seen, t_cap = latest["y"], latest["n"], latest["at"]
            if claim["n"] >= 0:
                rate["skipped"] += max(0, seen - claim["n"] - 1)   # camera frames no worker searched
            claim["n"] = seen
        if a.detect_scale < 1.0:
            gray = cv2.resize(y, None, fx=a.detect_scale, fy=a.detect_scale, interpolation=cv2.INTER_AREA)
        else:
            gray = np.ascontiguousarray(y)
        try:
            K = camera_matrix(gray.shape[1], gray.shape[0], HFOV)
            found = finder.find(gray, K)
            if a.imu_tilt:
                found = [imu_fix(r, t_cap, K) for r in found]
            boxes = [lid_pose(r) for r in found]
            err = None
        except Exception as e:                  # keep the stream running if one frame fails
            boxes, err = [], f"{type(e).__name__}: {e}"
        with cond:
            rate["n"] += 1
            if time.time() - rate["t0"] > 2:
                lid["hz"] = round(rate["n"] / (time.time() - rate["t0"]), 1)
                lid["skipped_pct"] = round(100 * rate["skipped"] / max(1, rate["n"] + rate["skipped"]), 1)
                rate["n"], rate["t0"], rate["skipped"] = 0, time.time(), 0
            rec_q.append((seen, t_cap, time.time(), gray, boxes, err))
            if seen > lid["frame"]:
                # frame = the camera frame number, t_cap = its capture time: the same time as that
                # frame's /h264 record, the radio pose (LID* time_usec) and VISION_POSITION_ESTIMATE
                lid.update(t=time.time(), frame=seen, t_cap=t_cap, boxes=boxes, w=gray.shape[1], h=gray.shape[0],
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
                                   fc_armed=fc["armed"], fc_seen_s=round(time.time() - fc["t"], 1),
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
            msg = m.recv_match(type=["TUNNEL", "HEARTBEAT", "ATTITUDE"], blocking=True, timeout=wait)
        except OSError:
            msg = None
        now = time.time()
        if msg is not None and msg.get_type() == "ATTITUDE":
            if msg.get_srcComponent() == 1:                         # the FC (imu_fix)
                att_buf.append((now, msg.roll, msg.pitch, msg.yaw))
            msg = None
        if msg is not None and msg.get_type() == "HEARTBEAT":
            if msg.get_srcComponent() == 1 and msg.type != 6:      # the FC (not a ground station)
                fc["armed"], fc["t"] = bool(msg.base_mode & 128), now
            msg = None
        if msg is not None and msg.target_system == 1 and msg.target_component == 191 \
                and msg.payload_type == ZERO_PAYLOAD_TYPE:
            zero["want"], zero["peer"] = zero["want"] + 1, (msg.get_srcSystem(), msg.get_srcComponent())
            msg = None
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


fc = {"armed": False, "t": 0.0}           # FC armed state, from its heartbeat (snapshots() reads the link)
# Ground control's "zero the FC on the box" (TUNNEL ZERO_PAYLOAD_TYPE, before a hover arms): the next
# vision message carries a new reset counter, so the EKF jumps to the camera pose (the box is the origin)
ZERO_PAYLOAD_TYPE = 39003
zero = {"want": 0, "peer": None}
rec_q = collections.deque(maxlen=200)     # searched frames, newest last: (frame, t_cap, t_done, gray, boxes, err)
REC_PRE_S, REC_POST_S = 3.0, 2.0


def recorder():
    """Record what the CV saw while the FC is armed: one folder per arming in --rec-dir with
    frames/<frame>.jpg (the image the tag search ran on) and cv.jsonl (one line per searched
    frame: frame number, capture time, result time, every box with its tags, tag outlines in
    that image, pose, yaw, tilt, rvec/tvec, px/cell, and the FC armed state). It starts
    REC_PRE_S before the arming (from the queue) and ends REC_POST_S after the disarm."""
    if a.rec_dir == "none":
        return
    os.makedirs(a.rec_dir, exist_ok=True)
    out, jl, last_armed_t = None, None, 0.0
    while True:
        time.sleep(0.02)
        now = time.time()
        armed = fc["armed"] and now - fc["t"] < 3.0
        if armed:
            last_armed_t = now
        if out is None and armed:
            out = os.path.join(a.rec_dir, time.strftime("%Y%m%d-%H%M%S"))
            os.makedirs(os.path.join(out, "frames"), exist_ok=True)
            jl = open(os.path.join(out, "cv.jsonl"), "a")
            pre = [r for r in list(rec_q) if r[1] >= now - REC_PRE_S]
            rec_q.clear()
            rec_q.extend(pre)                                     # write the frames before the arming too
            olds = sorted(d for d in os.listdir(a.rec_dir) if os.path.isdir(os.path.join(a.rec_dir, d)))
            for d in olds[:-a.rec_keep]:
                shutil.rmtree(os.path.join(a.rec_dir, d), ignore_errors=True)
        if out is None:
            continue
        while rec_q:
            frame, t_cap, t_done, gray, boxes, err = rec_q.popleft()
            cv2.imwrite(os.path.join(out, "frames", f"{frame:07d}.jpg"), gray, [cv2.IMWRITE_JPEG_QUALITY, 90])
            jl.write(json.dumps({"frame": frame, "t_cap": round(t_cap, 4), "t_done": round(t_done, 4),
                                 "armed": fc["armed"], "w": gray.shape[1], "h": gray.shape[0], "err": err,
                                 "boxes": boxes}, separators=(",", ":")) + "\n")
        jl.flush()
        if not armed and now - last_armed_t > REC_POST_S:
            jl.close()
            out, jl = None, None


VEL_MAX_GAP_S = 0.25      # two imu poses further apart than this: no velocity from them


def vision(m, send_lock):
    """The lid pose to the FC, for its position estimate (EKF ExternalNav, source set 2).

    Every detection with a box in view goes out as one VISION_POSITION_ESTIMATE, at once,
    stamped with the capture time; nothing is resent between detections. Nothing is sent
    when no box is in view: the EKF then stops getting ExternalNav, and ground control
    stops the hold-to-hover.
    Frame: the lid frame turned to z down, as ArduPilot expects (x = along the lid,
    y = -across, z = -height above the sticker; yaw = the nose from the lid +x axis,
    clockwise). ArduPilot turns this frame to north itself (AP_VisualOdom yaw alignment),
    so the box does not have to point north. Position = the drone centre (lid_pose
    applies the camera mount offsets), so the FC VISO_POS_X/Y/Z stay 0. The covariance
    is left 0: the FC uses VISO_POS_M_NSE / VISO_YAW_M_NSE.
    With the CV+IMU pose (pose "imu") on two frames in a row of the same box, also a
    VISION_SPEED_ESTIMATE: the change in position over the time between the two captures,
    stamped at their midpoint (EKF ExternalNav velocity, VISO_VEL_M_NSE). Between fixes the
    EKF otherwise integrates the accelerometers alone, and at spin-up that drifted 5 cm the
    wrong way in 0.4 s (2026-11-02 22:12). The reset counter goes up
    when the box changes (a new frame origin), and when ground control asks to zero the
    FC on the box (before a hover arms); the Pi then answers it with the counter it sent."""
    last_t, last_box, reset, zero_done = 0.0, None, 0, 0
    prev = None                                      # (capture time, x, y, z, box) of the last imu pose
    while True:
        time.sleep(0.005)
        t = lid["t"]
        if t == last_t:
            continue
        last_t = t                                   # one message per detection, nothing in between
        boxes = lid["boxes"]
        b = boxes[0] if boxes else None
        if b is None:
            continue
        if last_box is not None and b["box"] != last_box:
            reset = (reset + 1) % 256
        last_box = b["box"]
        want = zero["want"]
        if want != zero_done:
            reset = (reset + 1) % 256
        x, y, z = b["drone_m"]
        t_cap = lid["t_cap"]                         # the camera frame's capture time
        vel = None
        if b.get("pose") == "imu":
            if prev and prev[4] == b["box"] and 0.0 < t_cap - prev[0] < VEL_MAX_GAP_S:
                dt = t_cap - prev[0]
                vel = ((t_cap + prev[0]) / 2, (x - prev[1]) / dt, (y - prev[2]) / dt, (z - prev[3]) / dt)
            prev = (t_cap, x, y, z, b["box"])
        else:
            prev = None
        try:
            with send_lock:
                m.mav.vision_position_estimate_send(int(t_cap * 1e6), float(x), float(-y), float(-z),
                                                    0.0, 0.0, -math.radians(b["yaw_deg"]), [0.0] * 21, reset)
                if vel:
                    m.mav.vision_speed_estimate_send(int(vel[0] * 1e6), float(vel[1]), float(-vel[2]), float(-vel[3]),
                                                     [0.0] * 9, reset)
                if want != zero_done and zero["peer"]:
                    m.mav.tunnel_send(zero["peer"][0], zero["peer"][1], ZERO_PAYLOAD_TYPE, 1, [reset] + [0] * 127)
            zero_done = want
        except OSError:
            time.sleep(0.5)


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
    if a.vision:
        threading.Thread(target=vision, args=(m, send_lock), daemon=True).start()
    next_ip = 0.0
    while True:
        time.sleep(1.0 / a.mav_hz)
        if a.imu_tilt and (not att_buf or time.time() - att_buf[-1][0] > 1.0):
            try:                                    # ask the FC for ATTITUDE at 50 Hz on this link (imu_fix)
                with send_lock:
                    m.mav.command_long_send(1, 1, 511, 0, 30, 20000, 0, 0, 0, 0, 0)
            except OSError:
                pass
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
        us = int(lid["t_cap"] * 1e6)            # capture time of the frame: matches its /h264 record
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
threading.Thread(target=recorder, daemon=True).start()
if a.mav != "none":
    threading.Thread(target=radio, daemon=True).start()
for _ in range(DETECT_WORKERS):
    threading.Thread(target=detect, daemon=True).start()
print(f"streaming on http://0.0.0.0:{a.port}/  camera {NAME}, HFOV {HFOV} deg", flush=True)
ThreadingHTTPServer(("", a.port), H).serve_forever()
