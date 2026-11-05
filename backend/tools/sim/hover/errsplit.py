#!/usr/bin/env python3
"""Split a sim run's horizontal error into estimate error and control error.

  python tools/sim/hover/errsplit.py RUN [RUN ...]

truth - start = (truth - EKF) + (EKF - target) + (target - start):
  est  = true position - FC estimate (XKF1 PN/PE, body origin)
  ctrl = FC estimate - FC position target (PSCN/PSCE TP)
Hold window: hand-over + 10 s to the descent. Times: FC -> wall (events) -> physics (wallmap).
"""
import json
import sys
from pathlib import Path

import numpy as np
from pymavlink import mavutil

HERE = Path(__file__).resolve().parent


def split(name):
    d = HERE / "runs" / name
    r = json.load(open(d / "result.json"))
    T = np.load(d / "truth.npz")["truth"]
    wm = np.loadtxt(d / "wallmap.txt")
    ev = r["events"]
    # FC time -> physics time: fit a line through the events (fc_t, wall) and the wall map
    fc = np.array([v["fc_t"] for v in ev.values() if isinstance(v, dict)])
    wall = np.array([v["wall"] for v in ev.values() if isinstance(v, dict)])
    ph = np.interp(wall, wm[:, 0], wm[:, 1])
    a, b = np.polyfit(fc, ph, 1)
    m = mavutil.mavlink_connection(r["dflog"])
    X, PN, PE = [], [], []
    while True:
        x = m.recv_match(type=["XKF1", "PSCN", "PSCE"])
        if x is None:
            break
        dd = x.to_dict()
        if x.get_type() == "XKF1":
            if dd["C"] == 0:
                X.append((dd["TimeUS"] / 1e6, dd["PN"], dd["PE"]))
        elif x.get_type() == "PSCN":
            PN.append((dd["TimeUS"] / 1e6, dd["TPN"]))
        else:
            PE.append((dd["TimeUS"] / 1e6, dd["TPE"]))
    X, PN, PE = np.array(X), np.array(PN), np.array(PE)
    t_h, t_d = ev["handover"]["fc_t"] + 10, ev["descend"]["fc_t"]
    u = np.arange(t_h, t_d, 0.02)
    up = a * u + b
    tx, ty = np.interp(up, T[:, 0], T[:, 1]), np.interp(up, T[:, 0], T[:, 2])
    arm = a * ev["armed"]["fc_t"] + b
    pre = (T[:, 0] > arm - 1.5) & (T[:, 0] < arm - 0.2)
    x0, y0 = T[pre, 1].mean(), T[pre, 2].mean()
    en, ee = np.interp(u, X[:, 0], X[:, 1]), np.interp(u, X[:, 0], X[:, 2])
    gn, ge = np.interp(u, PN[:, 0], PN[:, 1]), np.interp(u, PE[:, 0], PE[:, 1])
    # the EKF frame origin differs from the physics frame: remove the mean truth-EKF offset at rest
    pre_fc = (X[:, 0] > ev["armed"]["fc_t"] - 1.5) & (X[:, 0] < ev["armed"]["fc_t"] - 0.2)
    pre_ph = a * X[pre_fc, 0] + b
    on = np.mean(np.interp(pre_ph, T[:, 0], T[:, 1]) - X[pre_fc, 1])
    oe = np.mean(np.interp(pre_ph, T[:, 0], T[:, 2]) - X[pre_fc, 2])
    est = np.c_[tx - en - on, ty - ee - oe]
    ctl = np.c_[en - gn, ee - ge]
    tot = np.c_[tx - x0, ty - y0]
    tgt = np.c_[gn + on - x0, ge + oe - y0]
    f = lambda v: f"{np.sqrt(np.mean(np.sum(v ** 2, 1))) * 1000:6.1f} rms {np.max(np.hypot(*v.T)) * 1000:6.1f} max"
    print(f"{name:<24} total {f(tot)} | est {f(est)} | ctrl {f(ctl)} | target {f(tgt)}")
    if "-v" in sys.argv:
        # estimate error vs the true velocity: a lag tau gives est = tau * v (truth ahead of the estimate)
        vx, vy = np.interp(up, T[:, 0], T[:, 4]), np.interp(up, T[:, 0], T[:, 5])
        V = np.r_[vx, vy]
        E = np.r_[est[:, 0] - est[:, 0].mean(), est[:, 1] - est[:, 1].mean()]
        tau = np.dot(E, V) / np.dot(V, V)
        res = E - tau * V
        print(f"{'':<24} est mean {est.mean(0) * 1000} mm; est ~ tau*v: tau {tau * 1000:.0f} ms, explains "
              f"{(1 - res.var() / E.var()) * 100:.0f} %; residual {res.std() * 1000:.1f} mm; true speed rms {V.std() * 1000:.1f} mm/s")
        F = np.abs(np.fft.rfft(E[: len(u)] * np.hanning(len(u))))
        fr = np.fft.rfftfreq(len(u), 0.02)
        for lo, hi in ((0, 0.1), (0.1, 0.5), (0.5, 2), (2, 25)):
            sel = (fr >= lo) & (fr < hi)
            print(f"{'':<24}   est power {lo}-{hi} Hz: {np.sqrt((F[sel] ** 2).sum() / (F ** 2).sum()) * 100:.0f} %")


if __name__ == "__main__":
    for n in sys.argv[1:]:
        if not n.startswith('-'):
            split(n)
