#!/usr/bin/env python3
"""Search camera mount spots and angles under the drone with the descent sim.

Every lens position on a grid under the frame (x along the box, y to the side,
some heights), tilted (default 0 / 15 / 30 deg) in toward the drone's centre line, gets the
same misaligned descents as lid_camera_sim.py. Spots inside the drive housing or
next to a landing leg are skipped. y >= 0 only: the gripper is the same turned
180 deg, so (x, y) and (-x, -y) see the same.

Score: share of descents with the box found, low (0.45 m and below) and high.

Example:
  python3 tools/sim/mount_sweep.py --out sweep --cam C920
"""
import argparse
import json
import math
import os
from multiprocessing import Pool

import numpy as np

import lid_camera_sim as S

LOW = [450, 320, 270, 230, 200, 180]
HIGH = [3000, 1400, 700]


def leg_y(z):
    return 64.1 + 0.317 * (-4.1 - z)


MOTOR = 325 / math.sqrt(2)      # X650 motors on the diagonals, 325 mm out
PROP_R = 190.5 + 20             # 15 in props plus 20 mm: keep the camera out of the downwash


def valid(x, y, z):
    if abs(x) < 105 and abs(y) < 52 and z > -147.3:          # inside the drive housing
        return False
    if abs(x) < 28 and abs(y - leg_y(z)) < 28:               # on top of a landing leg
        return False
    if math.hypot(abs(x) - MOTOR, abs(y) - MOTOR) < PROP_R:  # under a propeller
        return False
    return True


def mount(x, y, z, tilt):
    """Lens at (x, y, z); tilted `tilt` deg toward the drone's vertical centre line."""
    if tilt == 0:
        return (x, y, z)
    r = math.hypot(x, y)
    ux, uy = (-x / r, -y / r) if r > 1 else (-1.0, 0.0)
    t = math.radians(tilt)
    return ((x, y, z), (x + 1000 * math.sin(t) * ux, y + 1000 * math.sin(t) * uy, z - 1000 * math.cos(t)))


def run(args):
    cam, key, m, layout, samples, sticker = args
    S.HEIGHTS = HIGH + LOW
    r = S.run_case((cam, key, m, 0, layout, samples, 7, sticker))
    ok = {row["h"]: row["ok"] / row["n"] for row in r["rows"]}
    return {"key": key, "low": float(np.mean([ok[h] for h in LOW])),
            "high": float(np.mean([ok[h] for h in HIGH])), "by_h": ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sweep")
    ap.add_argument("--cam", default="C920")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--tag", default="", help="suffix for the results file")
    ap.add_argument("--xs", default="-160:180:20", help="lens x range start:stop:step, mm")
    ap.add_argument("--ys", default="0:140:20", help="lens y range (side), mm")
    ap.add_argument("--zs", default="-95,-120", help="lens heights, mm (frame origin = 0)")
    ap.add_argument("--tilts", default="0,15,30", help="tilts in toward the centre line, deg")
    a = ap.parse_args()
    sticker = dict(w=218, h=200, big_cell=18, small_cell=3.75, inset=5,
                   extra=[(-44.5, 80), (0, 80), (44.5, 80), (-44.5, -80), (0, -80), (44.5, -80),
                          (-89, 36), (-89, -36), (89, 36), (89, -36)])
    S.LS.configure(**sticker)
    os.makedirs(a.out, exist_ok=True)
    layout = S.LS.write_layout(os.path.join(a.out, "lid_layout.json"), [S.LS.CURRENT_BOX])
    jobs = []
    def rng(r):
        lo, hi, st = (float(v) for v in r.split(":"))
        return np.arange(lo, hi + 1e-6, st)
    for x in rng(a.xs):
        for y in rng(a.ys):
            for z in (float(v) for v in a.zs.split(",")):
                if not valid(x, y, z):
                    continue
                for tilt in (int(v) for v in a.tilts.split(",")):
                    key = f"{x:.0f},{y:.0f},{z:.0f},t{tilt}"
                    jobs.append((a.cam, key, mount(float(x), float(y), z, tilt), layout, a.samples, sticker))
    print(f"{len(jobs)} mount spots, {a.cam}", flush=True)
    with Pool() as p:
        res = p.map(run, jobs, chunksize=4)
    res.sort(key=lambda r: (r["high"] >= 0.9, r["low"]), reverse=True)
    json.dump(res, open(os.path.join(a.out, f"sweep_{a.cam}{a.tag}.json"), "w"), indent=1)
    for r in res[:15]:
        print(f"{r['key']:<22} low {r['low']:.2f} high {r['high']:.2f}")


if __name__ == "__main__":
    main()
