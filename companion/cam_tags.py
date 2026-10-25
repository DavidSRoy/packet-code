#!/usr/bin/env python3
"""Find box-lid tags in the USB camera image.

Prints the tag ID, the distance to the tag and the tag size in pixels.
The camera model is approximate (Arducam OV9281: 70 deg HFOV,
no lens calibration yet),
so the distances are estimates until the camera is calibrated.

Example:
  python3 cam_tags.py --family 36h11 --size-m 0.18 --save /tmp/tags.jpg
"""
import argparse
import math
import time

import cv2
import numpy as np

FAMILIES = {
    "36h11": cv2.aruco.DICT_APRILTAG_36h11,
    "25h9": cv2.aruco.DICT_APRILTAG_25h9,
    "16h5": cv2.aruco.DICT_APRILTAG_16h5,
    "aruco4x4": cv2.aruco.DICT_4X4_50,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/dev/video0")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--hfov", type=float, default=70.0, help="horizontal FOV, deg")
    ap.add_argument("--family", default="36h11", choices=sorted(FAMILIES))
    ap.add_argument("--size-m", type=float, default=0.18,
                    help="tag black-border width in metres")
    ap.add_argument("--frames", type=int, default=0, help="0 = run until Ctrl+C")
    ap.add_argument("--save", help="write an annotated JPEG to this path")
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.dev, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {a.dev}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fx = (w / 2) / math.tan(math.radians(a.hfov) / 2)
    K = np.array([[fx, 0, w / 2], [0, fx, h / 2], [0, 0, 1]], dtype=np.float64)
    dist = np.zeros(5)
    s = a.size_m / 2
    obj = np.array([[-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]], dtype=np.float64)

    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(FAMILIES[a.family]), params)
    print(f"camera {w}x{h}, fx={fx:.0f} px, family {a.family}, tag {a.size_m*1000:.0f} mm")

    n, t0 = 0, time.time()
    try:
        while a.frames == 0 or n < a.frames:
            ok, frame = cap.read()
            if not ok:
                print("frame read failed")
                continue
            n += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
            corners, ids, _ = det.detectMarkers(gray)
            fps = n / (time.time() - t0)
            if ids is None:
                print(f"[{fps:4.1f} fps] no tags")
            else:
                for c, i in zip(corners, ids.flatten()):
                    pts = c.reshape(4, 2).astype(np.float64)
                    side = np.mean(np.linalg.norm(pts - np.roll(pts, 1, axis=0), axis=1))
                    ok, rvec, tvec = cv2.solvePnP(obj, pts, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)
                    rng = float(np.linalg.norm(tvec)) if ok else float("nan")
                    x, y, z = tvec.flatten() if ok else (0, 0, 0)
                    print(f"[{fps:4.1f} fps] id {i:3d}  range {rng:5.2f} m  "
                          f"offset x {x:+.2f} y {y:+.2f} m  side {side:5.1f} px")
            if a.save:
                out = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                if ids is not None:
                    cv2.aruco.drawDetectedMarkers(out, corners, ids)
                cv2.imwrite(a.save, out)
    except KeyboardInterrupt:
        pass
    cap.release()


if __name__ == "__main__":
    main()
