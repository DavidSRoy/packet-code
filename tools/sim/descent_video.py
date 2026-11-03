#!/usr/bin/env python3
"""Video of one simulated pickup descent: what the camera sees, with the tags the
real detector finds drawn on top, next to a rear view and a top view of the drone
over the box (camera field of view in blue).

Uses the scene of lid_camera_sim.py. Needs ffmpeg for the MP4 (H.264).

Example:
  python3 tools/sim/descent_video.py --cam C920 --out descent_C920.mp4   (body-left mount K, straight down)
  python3 tools/sim/descent_video.py --mount -140,140,-40 --aim 158.8,-158.8,-946.3 --out descent_J.mp4
  python3 tools/sim/descent_video.py --mount 70,95,-100 --aim "" --out descent_D.mp4
"""
import argparse
import math
import os
import subprocess
import tempfile

import cv2
import numpy as np

import lid_camera_sim as S

STICKER = dict(w=218, h=200, big_cell=18, small_cell=3.75, inset=5,
               extra=[(-44.5, 80), (0, 80), (44.5, 80), (-44.5, -80), (0, -80), (44.5, -80),
                      (-89, 36), (-89, -36), (89, 36), (89, -36)])
GREEN, RED, BLUE, GREY, WHITE = (80, 200, 80), (60, 60, 220), (220, 140, 40), (120, 120, 120), (240, 240, 240)


def path(n):
    """Height, offset, yaw, roll, pitch for each frame: a descent from 3 m that starts
    off to the side and turned, with wind wobble, and closes in as it comes down."""
    out = []
    for i in range(n):
        u = i / (n - 1)
        h = math.exp(math.log(3000) + (math.log(165) - math.log(3000)) * u)
        r = (30 + 0.15 * h) * (0.9 + 0.1 * math.sin(7 * u))
        a = math.radians(-35 + 90 * u)
        out.append((h, r * math.cos(a), r * math.sin(a), 15 * math.cos(3 * u) + 4 * math.sin(11 * u),
                    4 * math.sin(9 * u), 3 * math.sin(13 * u + 1)))
    return out


def box_pts(b):
    x0, x1, y0, y1, z0, z1 = b
    return np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], float)


def parts():
    """(name, corner points in the drone frame) for the drawings."""
    out = [(k, box_pts(b)) for k, b in S.BOXES.items()]
    for sgn in (1, -1):
        zs = np.array([-4.1, -295.0])
        ys = sgn * (64.1 + 0.317 * (-4.1 - zs))
        out.append(("leg", np.array([[x, y, z] for x in (-8, 8) for y, z in zip(ys, zs)] +
                                    [[x, y + d, z] for x in (-8, 8) for y, z in zip(ys, zs) for d in (-8, 8)])))
    for sx, sy in ((1, 1), (1, -1)):        # X650 arms: diagonals, motors about 230 mm out
        d = np.array([sx, sy, 0.0]) / math.sqrt(2)
        n = np.array([-d[1], d[0], 0.0]) * 10
        ends = [d * 325 * k for k in (1, -1)]
        out.append(("arm", np.array([e + s * n + [0, 0, z] for e in ends for s in (1, -1) for z in (-6, 0)])))
    return out


def lid_pts():
    w, h = S.LID_W / 2, S.LID_H / 2
    return np.array([[-w, -h, 0], [w, -h, 0], [w, h, 0], [-w, h, 0]], float)


def footprint(sc, R, t):
    """Where the four image corners hit the lid plane (world mm), or None past the horizon."""
    Ki = np.linalg.inv(sc.K)
    cam = -R.T @ t
    pts = []
    for u, v in ((0, 0), (sc.w, 0), (sc.w, sc.h), (0, sc.h)):
        d = R.T @ (Ki @ np.array([u, v, 1.0]))
        if d[2] >= -1e-6:
            return None
        pts.append(cam - cam[2] / d[2] * d)
    return np.array(pts), cam


def panel_rear(sc, R, t, R_wd, d0, size):
    """Rear view (looking forward along the box): world y across, z up."""
    W, H = size
    img = np.full((H, W, 3), 30, np.uint8)
    top = d0[2] + 120
    s = (H - 60) / (top + 60)
    cy = d0[1]
    to = lambda y, z: (int(W / 2 + (y - cy) * s), int(H - 30 - z * s))
    cv2.rectangle(img, to(-S.LID_H / 2, -150), to(S.LID_H / 2, 0), (90, 90, 90), -1)        # box
    cv2.rectangle(img, to(-S.LID_H / 2, -2), to(S.LID_H / 2, 0), WHITE, -1)                 # lid
    fp = footprint(sc, R, t)
    if fp is not None:
        pts, cam = fp
        ys = [p[1] for p in pts]
        cv2.fillPoly(img, [np.array([to(cam[1], cam[2]), to(min(ys), 0), to(max(ys), 0)])], (90, 60, 20))
    for name, p in parts():
        pw = (R_wd @ p.T).T + d0
        hull = cv2.convexHull(np.array([to(q[1], q[2]) for q in pw], np.int32))
        cv2.fillConvexPoly(img, hull, (70, 110, 160) if "RP" in name else GREY)
    cam = d0 + R_wd @ sc.mount
    cv2.circle(img, to(cam[1], cam[2]), 6, BLUE, -1)
    cv2.putText(img, "rear view", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 1, cv2.LINE_AA)
    return img


def panel_top(sc, R, t, R_wd, d0, size):
    """Top view centred on the lid: world x across (nose of a level drone to the right), y up."""
    W, H = size
    img = np.full((H, W, 3), 30, np.uint8)
    s = min(W, H) / 900
    to = lambda x, y: (int(W / 2 + x * s), int(H / 2 - y * s))
    fp = footprint(sc, R, t)
    if fp is not None:
        pts = np.clip(fp[0][:, :2], -5000, 5000)
        cv2.fillPoly(img, [np.array([to(*p) for p in pts], np.int32)], (90, 60, 20))
    lid = lid_pts()
    cv2.fillPoly(img, [np.array([to(p[0], p[1]) for p in lid], np.int32)], WHITE)
    for name, p in parts():
        pw = (R_wd @ p.T).T + d0
        hull = cv2.convexHull(np.array([to(q[0], q[1]) for q in pw], np.int32))
        cv2.polylines(img, [hull], True, (70, 110, 160) if "RP" in name else GREY, 2, cv2.LINE_AA)
    cam = d0 + R_wd @ sc.mount
    cv2.circle(img, to(cam[0], cam[1]), 6, BLUE, -1)
    cv2.putText(img, "top view (blue = camera view on the lid plane)", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 1, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", default="C920", choices=list(S.CAMERAS))
    ap.add_argument("--mount", default="40,120,-40", help="lens x,y,z in the drone frame, mm")
    ap.add_argument("--aim", default="", help="aim point x,y,z, drone frame mm (\"\" = straight down)")
    ap.add_argument("--frames", type=int, default=240)
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--out", default="descent.mp4")
    ap.add_argument("--stills", action="store_true", help="also save 4 frames as PNG next to the video")
    a = ap.parse_args()
    S.LS.configure(**STICKER)
    layout = S.LS.write_layout(os.path.join(tempfile.mkdtemp(), "lid_layout.json"), [S.LS.CURRENT_BOX])
    m = tuple(float(v) for v in a.mount.split(","))
    if a.aim:
        m = (m, tuple(float(v) for v in a.aim.split(",")))
    sc = S.Scene(a.cam, m, 0, layout)
    rng = np.random.default_rng(3)
    W = 1920
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                           "-s", f"{W}x720", "-r", str(a.fps), "-i", "-", "-c:v", "libx264",
                           "-pix_fmt", "yuv420p", "-crf", "20", a.out], stdin=subprocess.PIPE)
    found = 0
    for i, (h, dx, dy, yaw, roll, pitch) in enumerate(path(a.frames)):
        img, R, t = sc.render(dx, dy, h, yaw, roll, pitch, rng)
        R_, t_, R_wd, d0 = sc.pose(dx, dy, h, yaw, roll, pitch)
        res = sc.finder.find(img, sc.K)
        view = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        good = False
        if res:
            r = res[0]
            err = float(np.linalg.norm(np.array(r["xyz_m"]) * 1000 - t))
            good = err < max(20.0, 0.05 * float(np.linalg.norm(t)))
            for o in r["outlines"]:
                cv2.polylines(view, [np.array(o["px"], np.int32)], True, GREEN if good else RED, 3, cv2.LINE_AA)
            msg = f"BOX {r['box']}  {len(r['tags'])} tags  position error {err:.0f} mm"
        else:
            msg = "no box found"
        found += good
        cv2.rectangle(view, (0, 0), (1280, 44), (0, 0, 0), -1)
        cv2.putText(view, f"{a.cam} camera   {h / 1000:.2f} m above lid   {msg}", (14, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, GREEN if good else RED, 2, cv2.LINE_AA)
        left = np.vstack([panel_rear(sc, R, t, R_wd, d0, (640, 360)), panel_top(sc, R, t, R_wd, d0, (640, 360))])
        cv2.line(left, (0, 360), (640, 360), (80, 80, 80), 2)
        frame = np.hstack([left, view])
        ff.stdin.write(frame.tobytes())
        if a.stills and i in (0, a.frames // 2, int(a.frames * 0.85), a.frames - 1):
            cv2.imwrite(os.path.splitext(a.out)[0] + f"_f{i:03d}.png", frame)
    ff.stdin.close()
    ff.wait()
    print(f"{a.out}: box found in {found}/{a.frames} frames")


if __name__ == "__main__":
    main()
