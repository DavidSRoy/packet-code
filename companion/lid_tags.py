#!/usr/bin/env python3
"""Find Packet box lids in a camera image and give each box's ID and pose.

The lid sticker (see lid_stickers.py) has one ArUco 4x4_50 tag (ID = box
number) and four AprilTag 36h11 corner tags (IDs 4n .. 4n+3). Every visible
tag of a box goes into one solvePnP, so the pose works far away (big tag only)
and close in (corner tags only).

Pose: camera frame (x right, y down, z forward) to lid frame (lid_layout.json).
Without a lens calibration the camera matrix is an estimate from the HFOV.

Example (live camera):
  python3 lid_tags.py --layout lid_layout.json
"""
import argparse
import json
import math
from collections import defaultdict

import cv2
import numpy as np


def camera_matrix(w, h, hfov_deg=70.0):
    fx = (w / 2) / math.tan(math.radians(hfov_deg) / 2)
    return np.array([[fx, 0, w / 2], [0, fx, h / 2], [0, 0, 1]], dtype=np.float64)


class LidFinder:
    def __init__(self, layout_path):
        lay = json.load(open(layout_path))
        self.big = {}     # aruco id -> (box, 4x3 corners)
        self.small = {}   # apriltag id -> (box, 4x3 corners)
        for b in lay["boxes"]:
            t = b["aruco_4x4_50"]
            self.big[t["id"]] = (b["box"], np.array(t["corners_m"]))
            for t in b["apriltag_36h11"]:
                self.small[t["id"]] = (b["box"], np.array(t["corners_m"]))
        p = cv2.aruco.DetectorParameters()
        p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        # One detector for both dictionaries (OpenCV >= 4.12): the threshold and contour
        # stage runs once on the full frame, then each dictionary decodes the candidates.
        # Same tags and corners as two detectors, half the CPU (measured 2026-10-25 on the
        # Pi Zero 2 W, 1280x720: 119 ms against 234 ms on one core).
        self.det = cv2.aruco.ArucoDetector(
            [cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
             cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)], p)
        self.kinds = [(self.big, 6, "A"), (self.small, 8, "T")]    # by dictionary index

    def find(self, gray, K, dist=None):
        """Return [{box, tags, range_m, xyz_m, yaw_deg, px_per_cell, R, outlines}] for each box seen.

        xyz_m and R map lid points into the camera frame: X_cam = R @ X_lid + xyz_m.
        outlines has the image corners of each tag that was found."""
        dist = np.zeros(5) if dist is None else dist
        pts = defaultdict(lambda: ([], [], [], [], []))  # box -> obj, img, tag names, cell px, outlines
        corners, ids, _, dict_idx = self.det.detectMarkersMultiDict(gray)
        if ids is not None:
            for c, i, d in zip(corners, ids.flatten(), dict_idx.flatten()):
                table, cells, kind = self.kinds[int(d)]
                if int(i) not in table:
                    continue
                box, obj = table[int(i)]
                img = c.reshape(4, 2).astype(np.float64)
                side = np.mean(np.linalg.norm(img - np.roll(img, 1, axis=0), axis=1))
                o, m, n, s, ol = pts[box]
                o.extend(obj); m.extend(img); n.append(f"{kind}{int(i)}"); s.append(side / cells)
                ol.append({"tag": f"{kind}{int(i)}", "px": img.round(1).tolist()})
        out = []
        for box, (o, m, names, cell_px, outlines) in sorted(pts.items()):
            o, m = np.array(o), np.array(m)
            flag = cv2.SOLVEPNP_IPPE if len(o) == 4 else cv2.SOLVEPNP_ITERATIVE
            if len(o) > 4:  # seed with IPPE on the first tag, then refine on all points
                ok, rv, tv = cv2.solvePnP(o[:4], m[:4], K, dist, flags=cv2.SOLVEPNP_IPPE)
                ok, rv, tv = cv2.solvePnP(o, m, K, dist, rv, tv, True, flag)
            else:
                ok, rv, tv = cv2.solvePnP(o, m, K, dist, flags=flag)
            if not ok:
                continue
            R, _ = cv2.Rodrigues(rv)
            # lid +x axis seen in the image plane -> yaw of the lid relative to camera x
            yaw = math.degrees(math.atan2(R[1, 0], R[0, 0]))
            out.append({"box": box, "tags": names, "range_m": float(np.linalg.norm(tv)),
                        "xyz_m": tv.flatten().tolist(), "yaw_deg": yaw,
                        "px_per_cell": float(min(cell_px)),
                        "R": R.tolist(), "outlines": outlines})
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default="lid_layout.json")
    ap.add_argument("--dev", default="/dev/video0")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--hfov", type=float, default=70.0)
    a = ap.parse_args()

    finder = LidFinder(a.layout)
    cap = cv2.VideoCapture(a.dev, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    K = camera_matrix(w, h, a.hfov)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
            for r in finder.find(gray, K):
                x, y, z = r["xyz_m"]
                print(f"box {r['box']:2d}  range {r['range_m']:5.2f} m  "
                      f"x {x:+.2f} y {y:+.2f} z {z:.2f}  yaw {r['yaw_deg']:+6.1f}  "
                      f"{r['px_per_cell']:.1f} px/cell  {' '.join(r['tags'])}")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
