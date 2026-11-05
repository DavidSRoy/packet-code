#!/usr/bin/env python3
"""Descent simulation for the box-lid camera: render what the camera sees on the
way down, with the gripper, housing and legs in the way, and run the real
detector (companion/lid_tags.py LidFinder) on every frame.

Geometry (Packet-V0 Master Assembly v60, measured in Fusion 2026-10-27, mm):
drone frame = master frame, +x nose (box long axis, gripper axis), +y left,
+z up. At the grab the lid top is at z = -158.1, so the drone origin is
158.1 mm above the lid. The X1C lid (BX-006 v7, box BX-005 v12, inside
218 mm) is 225.6 x 206.4 mm. Gripper jaws RP-019 v16.

The camera looks straight down (optionally tilted), image top = nose.
Lid frame (lid_layout.json): origin sticker centre, +x right, +y top, +z up.
At yaw 0 the drone +x is the lid +x.

Example:
  python3 tools/sim/lid_camera_sim.py --out lidsim --snap   (stickers_218x200 layout)
"""
import argparse
import json
import math
import os
import sys
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "companion"))
import lid_stickers as LS                 # noqa: E402
from lid_tags import LidFinder, camera_matrix   # noqa: E402

LID_TOP_Z = -158.1                         # lid top in the drone frame at the grab, mm
LID_W, LID_H = 225.6, 206.4                # lid top skin, mm

# Things between the camera and the lid, drone frame, mm: (xmin, xmax, ymin, ymax, zmin, zmax)
BOXES = {
    "RP-013 drive housing": (-100.0, 100.0, -47.0, 47.0, -147.3, -92.0),
    "RP-019 jaw 1": (-126.8, 65.0, -60.0, 34.9, -170.9, -131.9),
    "RP-019 jaw 2": (-65.0, 126.8, -34.9, 60.0, -170.9, -131.9),
    "FR-004 battery plate": (-64.0, 64.0, -60.0, 60.0, -92.0, -90.0),
}
# Landing legs (OG-001): 16 mm tubes in the x = 0 plane, centre y = +-(64.1 + 0.317 * (-4.1 - z))
LEG_R = 8.0

CAMERAS = {   # name: (width, height, HFOV deg, autofocus)
    "C270": (1280, 720, 48.8, False),
    "C920": (1280, 720, 70.4, True),
}


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


# camera axes in the drone frame: x_c = drone right (-y), y_c = toward the tail (-x), z_c = down
CAM_IN_DRONE = np.array([[0, -1, 0], [-1, 0, 0], [0, 0, -1.0]]).T   # columns: x_c, y_c, z_c in drone axes


def sticker_raster(px_per_mm=6.0):
    """Sticker image (white, black cells) at px_per_mm; y down like the SVG."""
    w, h = int(round(LS.W * px_per_mm)), int(round(LS.H * px_per_mm))
    img = np.full((h, w), 235, np.uint8)
    for sh in LS.shapes(LS.CURRENT_BOX):
        if sh[0] != "rect":
            continue
        _, x, y, rw, rh = sh
        x0, y0 = int(round(x * px_per_mm)), int(round(y * px_per_mm))
        x1, y1 = int(round((x + rw) * px_per_mm)), int(round((y + rh) * px_per_mm))
        img[y0:y1, x0:x1] = 18
    return img


class Scene:
    def __init__(self, cam, mount, tilt_deg, layout_path, px_per_mm=6.0):
        self.w, self.h, self.hfov, self.af = CAMERAS[cam]
        self.K = camera_matrix(self.w, self.h, self.hfov)
        pos, aim = (mount[0], mount[1]) if len(mount) == 2 else (mount, None)
        self.mount = np.array(pos, float)
        self.R_cd = CAM_IN_DRONE @ rot_x(math.radians(tilt_deg))
        if aim is not None:      # optical axis toward an aim point (drone frame), image top toward the nose
            z = np.array(aim, float) - self.mount
            z /= np.linalg.norm(z)
            y = np.array([-1.0, 0, 0]) - z * (-z[0])
            y /= np.linalg.norm(y)
            self.R_cd = np.column_stack([np.cross(y, z), y, z])
        self.finder = LidFinder(layout_path)
        self.ppm = px_per_mm
        self.tex = sticker_raster(px_per_mm)

    def pose(self, dx, dy, height, yaw_deg, roll_deg, pitch_deg):
        """World (lid) frame -> camera frame: X_c = R @ X_w + t (mm)."""
        R_wd = rot_z(math.radians(yaw_deg)) @ rot_x(math.radians(roll_deg)) @ rot_y(math.radians(pitch_deg))
        d0 = np.array([dx, dy, height])                    # drone origin in the lid frame
        cam_w = d0 + R_wd @ self.mount
        R_wc = R_wd @ self.R_cd                              # camera axes in the world frame
        R = R_wc.T
        return R, -R @ cam_w, R_wd, d0

    def project(self, R, t, pts):
        pc = (R @ pts.T).T + t
        return pc, pc[:, :2] / pc[:, 2:3] * np.array([self.K[0, 0], self.K[1, 1]]) + self.K[:2, 2]

    def render(self, dx, dy, height, yaw, roll, pitch, rng):
        R, t, R_wd, d0 = self.pose(dx, dy, height, yaw, roll, pitch)
        img = np.full((self.h, self.w), 95, np.uint8)        # ground
        # lid plastic, then sticker: homographies from lid-plane mm (y up) to image
        Hlid = self.K @ np.column_stack([R[:, 0], R[:, 1], t])
        lid = np.array([[-LID_W / 2, LID_H / 2], [LID_W / 2, LID_H / 2], [LID_W / 2, -LID_H / 2], [-LID_W / 2, -LID_H / 2]])
        lp = cv2.perspectiveTransform(lid.reshape(-1, 1, 2), Hlid).reshape(-1, 2)
        cv2.fillConvexPoly(img, np.round(lp * 16).astype(np.int32), 150, cv2.LINE_AA, 4)
        S = np.array([[1 / self.ppm, 0, -LS.W / 2], [0, -1 / self.ppm, LS.H / 2], [0, 0, 1]])   # texture px -> lid mm
        Ht = Hlid @ S
        warped = cv2.warpPerspective(self.tex, Ht, (self.w, self.h), flags=cv2.INTER_AREA, borderValue=0)
        mask = cv2.warpPerspective(np.full_like(self.tex, 255), Ht, (self.w, self.h), flags=cv2.INTER_LINEAR, borderValue=0)
        img = np.where(mask > 127, warped, img).astype(np.uint8)
        # occluders (all above the lid, so drawn over it)
        cam_z_drone = self.mount[2]
        for (x0, x1, y0, y1, z0, z1) in BOXES.values():
            z1c = min(z1, cam_z_drone - 3.0)                # keep the part below the lens only
            if z0 >= z1c:
                continue
            self._draw_box(img, R, t, R_wd, d0, (x0, x1, y0, y1, z0, z1c))
        for sgn in (1, -1):                                  # legs as short box segments
            for z in np.arange(-4.1, LID_TOP_Z - 40, -6.0):
                zc = min(z, cam_z_drone - 3.0)
                yc = sgn * (64.1 + 0.317 * (-4.1 - z))
                if z > cam_z_drone - 3.0:
                    continue
                self._draw_box(img, R, t, R_wd, d0, (-LEG_R, LEG_R, yc - LEG_R, yc + LEG_R, z - 6.5, zc))
        # optics: defocus (fixed-focus C270), lens softness, noise
        dist_mm = float(np.linalg.norm(t))
        sigma = 0.7
        if not self.af:
            f_mm, n, focus_mm, pitch_mm = 3.7, 2.0, 600.0, 3.6 / 1280
            coc = (f_mm / n) * f_mm * abs(1 / max(dist_mm, 50) - 1 / focus_mm) / pitch_mm
            sigma = math.hypot(sigma, coc / 2.355)
        img = cv2.GaussianBlur(img, (0, 0), sigma)
        img = np.clip(img + rng.normal(0, 3.0, img.shape), 0, 255).astype(np.uint8)
        return img, R, t

    def _draw_box(self, img, R, t, R_wd, d0, b):
        x0, x1, y0, y1, z0, z1 = b
        pts = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
        pw = (R_wd @ pts.T).T + d0
        pc, uv = self.project(R, t, pw)
        if (pc[:, 2] <= 1).any():
            return
        hull = cv2.convexHull(np.round(uv * 16).astype(np.int32))
        cv2.fillConvexPoly(img, hull, 55, cv2.LINE_AA, 4)

    def detect(self, img, R, t):
        res = self.finder.find(img, self.K)
        if not res:
            return False, None, []
        r = res[0]
        err = float(np.linalg.norm(np.array(r["xyz_m"]) * 1000 - t))
        return err < max(20.0, 0.05 * float(np.linalg.norm(t))), err, r["tags"]


HEIGHTS = [3000, 2400, 1800, 1400, 1100, 900, 700, 550, 450, 380, 320, 270, 230, 200, 180, 165]


def misalign(h, k, n, rng):
    """k-th of n misalignment samples at drone height h (mm above the lid):
    lateral offset up to 30 mm + 15 % of the height, yaw +-20 deg, tilt +-5 deg."""
    r = (30.0 + 0.15 * h) * math.sqrt((k + 0.5) / n)
    a = 2 * math.pi * (k * 0.618034 % 1)
    return r * math.cos(a), r * math.sin(a), rng.uniform(-20, 20), rng.uniform(-5, 5), rng.uniform(-5, 5)


def run_case(args):
    cam, mount_name, mount, tilt, layout, samples, seed, sticker = args
    LS.configure(**sticker)
    rng = np.random.default_rng(seed)
    sc = Scene(cam, mount, tilt, layout)
    rows = []
    for h in HEIGHTS:
        ok = 0
        tags = set()
        for k in range(samples):
            dx, dy, yaw, roll, pitch = misalign(h, k, samples, rng)
            img, R, t = sc.render(dx, dy, h, yaw, roll, pitch, rng)
            good, err, tg = sc.detect(img, R, t)
            ok += good
            tags.update(tg)
        rows.append({"h": h, "ok": ok, "n": samples, "tags": sorted(tags)})
    return {"cam": cam, "mount": mount_name, "tilt": tilt, "rows": rows}


MOUNTS = {   # lens centre in the drone frame, mm; optional aim point (straight down if none)
    "A current (134,0,-112)": (134.0, 0.0, -112.0),
    "B side (70,75,-100)": (70.0, 75.0, -100.0),
    "C nose (180,0,-110)": (180.0, 0.0, -110.0),
    "D side-out (70,95,-100)": (70.0, 95.0, -100.0),
    "E side-out-aimed (70,95,-100)>(0,0,-700)": ((70.0, 95.0, -100.0), (0.0, 0.0, -700.0)),
    "F side-out-low (70,95,-125)": (70.0, 95.0, -125.0),
    "G side-out-low-aimed (70,95,-125)>(0,0,-700)": ((70.0, 95.0, -125.0), (0.0, 0.0, -700.0)),
    "H nose-past-jaws (140,0,-110)": (140.0, 0.0, -110.0),
    "I nose-aimed (140,0,-110)>(0,0,-700)": ((140.0, 0.0, -110.0), (0.0, 0.0, -700.0)),
    # under the rear-left arm (on the arm diagonal, 198 mm out), 40 mm below the frame,
    # tilted 25 deg in toward the drone's centre line (tools/sim/mount_sweep.py)
    "J rear-left-arm (-140,140,-40) tilt 25": ((-140.0, 140.0, -40.0), (158.8, -158.8, -946.3)),
    # left side of the body between the two left arms, 45 mm out from the landing leg,
    # straight down; clear of the prop discs (best such spot in mount_sweep.py)
    "K body-left (40,120,-40)": (40.0, 120.0, -40.0),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="lidsim")
    ap.add_argument("--layout", default=None, help="lid_layout.json; default: make one for the current sticker size")
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--tilts", default="0", help="camera tilts toward the centre, deg, e.g. 0,10")
    ap.add_argument("--snap", action="store_true", help="save example frames")
    ap.add_argument("--size", default="218x200", help="sticker WxH mm")
    ap.add_argument("--big-cell", type=float, default=18.0)
    ap.add_argument("--small-cell", type=float, default=3.75)
    ap.add_argument("--inset", type=float, default=5.0)
    ap.add_argument("--extra", default="-44.5,80;0,80;44.5,80;-44.5,-80;0,-80;44.5,-80;-89,36;-89,-36;89,36;89,-36", help="extra small tag centres 'x,y;x,y' in lid mm")
    ap.add_argument("--cams", default=",".join(CAMERAS))
    ap.add_argument("--mounts", default="", help="mount names (first word, e.g. A,B); default all")
    a = ap.parse_args()
    w, h = (float(v) for v in a.size.lower().split("x"))
    sticker = dict(w=w, h=h, big_cell=a.big_cell, small_cell=a.small_cell, inset=a.inset,
                   extra=[tuple(float(v) for v in p.split(",")) for p in a.extra.split(";") if p.strip()])
    LS.configure(**sticker)
    os.makedirs(a.out, exist_ok=True)
    layout = a.layout or LS.write_layout(os.path.join(a.out, "lid_layout.json"), [LS.CURRENT_BOX])
    tilts = [float(x) for x in a.tilts.split(",")]
    mounts = {k: v for k, v in MOUNTS.items() if not a.mounts or k.split()[0] in a.mounts.split(",")}
    cams = a.cams.split(",")
    jobs = [(c, mn, m, tl, layout, a.samples, 7, sticker) for c in cams for mn, m in mounts.items() for tl in tilts]
    with Pool() as p:
        results = p.map(run_case, jobs)
    json.dump(results, open(os.path.join(a.out, "results.json"), "w"), indent=1)
    for r in results:
        line = " ".join(f"{x['h']/1000:.2f}:{x['ok']}/{x['n']}" for x in r["rows"])
        print(f"{r['cam']} {r['mount']:<26} tilt {r['tilt']:>4.0f}  {line}")
    if a.snap:
        rng = np.random.default_rng(1)
        for c in cams:
            for mn, m in mounts.items():
                sc = Scene(c, m, tilts[0], layout)
                for h in (1800, 450, 200):
                    img, R, t = sc.render(40, -30, h, 8, 2, -2, rng)
                    cv2.imwrite(os.path.join(a.out, f"{c}_{mn.split()[0]}_{h}.png"), img)


if __name__ == "__main__":
    main()
