#!/usr/bin/env python3
"""Map of mount_sweep.py results: the drone seen from below, each grid spot coloured
by how often the box was found low down (0.45 m to the grab), best height and tilt
at that spot. Mirrored to y < 0 (the gripper is the same turned 180 deg).

Example:
  python3 tools/sim/sweep_map.py sweep/sweep_C920.json sweep/sweep_C920_wide.json --out mount_map.png
"""
import argparse
import json
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

import lid_camera_sim as S
import mount_sweep as MS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="mount_map.png")
    ap.add_argument("--title", default="")
    ap.add_argument("--mark", action="append", default=[], help="x,y,label: mark a mount spot, e.g. -140,140,arm")
    a = ap.parse_args()
    best = defaultdict(lambda: None)
    for f in a.files:
        for r in json.load(open(f)):
            x, y, z, t = r["key"].split(",")
            k = (float(x), float(y))
            if r["high"] < 0.9 or not MS.valid(float(x), float(y), float(z)):
                continue
            if best[k] is None or r["low"] > best[k]["low"]:
                best[k] = dict(r, z=float(z), tilt=int(t[1:]))
    fig, ax = plt.subplots(figsize=(11, 9))
    for name, (x0, x1, y0, y1, z0, z1) in S.BOXES.items():
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=1.5,
                               ec="#c08a4e" if "jaw" in name else "#555", ls="-" if "jaw" in name else "--"))
    ax.add_patch(Rectangle((-S.LID_W / 2, -S.LID_H / 2), S.LID_W, S.LID_H, fill=False, lw=2, ec="#333"))
    ax.text(0, 0, "lid at the grab", ha="center", va="center", fontsize=9, color="#333")
    for sgn in (1, -1):
        ax.plot([0, 0], [sgn * 64.1, sgn * 156.3], color="#555", lw=6, alpha=0.5)   # landing leg, top to foot
        ax.plot([-230, 230], [sgn * 230, -sgn * 230], color="#999", lw=4, alpha=0.4)
        for sx in (1, -1):                                                           # prop disc, kept clear
            ax.add_patch(Circle((sx * MS.MOTOR, sgn * MS.MOTOR), MS.PROP_R, fc="#9ab", alpha=0.18, ec="#678", ls=":"))
    pts = [(k, v) for k, v in best.items() if v]
    for (x, y), v in pts:
        for sy in (1, -1):
            c = plt.cm.RdYlGn(v["low"])
            ax.add_patch(Circle((x * sy, y * sy), 8.5, color=c))
        ax.text(x, y, f"{v['low']*100:.0f}", ha="center", va="center", fontsize=6.5)
    top = sorted(pts, key=lambda p: -p[1]["low"])[:5]
    ax.text(-250, -250, "Best spots (x, y, z mm; tilt in):\n" + "\n".join(
        f"{v['low']*100:.0f}%  ({x:.0f}, {y:.0f}, {v['z']:.0f}) tilt {v['tilt']} deg" for (x, y), v in top),
        fontsize=8, va="bottom", family="monospace", bbox=dict(fc="white", ec="#999"))
    for m in a.mark:
        x, y, lab = m.split(",", 2)
        ax.plot(float(x), float(y), marker="*", ms=22, mfc="none", mec="#0b4f8f", mew=2.2)
        ax.annotate(lab, (float(x), float(y)), xytext=(14, -4), textcoords="offset points", fontsize=9,
                    color="#0b4f8f", fontweight="bold")
    ax.set_aspect("equal")
    ax.set_xlim(-260, 260)
    ax.set_ylim(-260, 260)
    ax.set_xlabel("forward (nose) mm")
    ax.set_ylabel("to the left mm")
    ax.set_title(a.title or "Drone from below: % of descents with the box found from 0.45 m down to the grab,\n"
                 "best lens height and tilt at each spot (spots that lose the box higher up are left out)", fontsize=10)
    sm = plt.cm.ScalarMappable(cmap="RdYlGn", norm=plt.Normalize(0, 100))
    fig.colorbar(sm, ax=ax, shrink=0.7, label="% found from 0.45 m down")
    ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(a.out, dpi=110)


if __name__ == "__main__":
    main()
