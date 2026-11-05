#!/usr/bin/env python3
"""Where the hold error sits in frequency: true horizontal position variance by band.

  python tools/sim/hover/bands.py RUN [RUN ...]

Hold window: hand-over + 3 s to the descent. Each band's share is of the total variance (sums to 100 %).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BANDS = ((0.0, 0.1), (0.1, 0.3), (0.3, 0.7), (0.7, 1.0), (1.0, 1.6), (1.6, 3.0), (3.0, 10.0))


def bands(name):
    d = HERE / "runs" / name
    r = json.load(open(d / "result.json"))
    T = np.load(d / "truth.npz")["truth"]
    wm = np.loadtxt(d / "wallmap.txt")
    pt = lambda e: float(np.interp(r["events"][e]["wall"], wm[:, 0], wm[:, 1]))
    w = (T[:, 0] >= pt("handover") + 3) & (T[:, 0] <= pt("descend"))
    fs = 1 / np.median(np.diff(T[:, 0]))
    tot, out = 0.0, []
    P = 0
    for c in (1, 2):
        x = T[w, c] - T[w, c].mean()
        F = np.abs(np.fft.rfft(x)) ** 2
        P = P + F
    f = np.fft.rfftfreq(w.sum(), 1 / fs)
    tot = P[1:].sum()
    rms = np.sqrt(np.sum([np.var(T[w, c]) for c in (1, 2)])) * 1000
    cells = [f"{P[(f >= lo) & (f < hi) & (f > 0)].sum() / tot * 100:5.1f}" for lo, hi in BANDS]
    print(f"{name:<22} rms {rms:5.1f} mm  " + "  ".join(cells))


if __name__ == "__main__":
    print(" " * 38 + "  ".join(f"{lo}-{hi}Hz".rjust(5) for lo, hi in BANDS))
    for n in sys.argv[1:]:
        bands(n)
