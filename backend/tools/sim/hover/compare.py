#!/usr/bin/env python3
"""Same hover measurements on real and simulated dataflash logs, side by side.

  python tools/sim/hover/compare.py LOG.BIN [LOG.BIN ...]

Per log, over the hold: from 5 s after the HTO hand-over message to the start of the descent
(the height target rises 5 mm over its hold value) or 0.5 s before the motors stop:
  - FC position error RMS N/E/D (PSCN/PSCE/PSCD target - actual) and its main frequency
  - roll/pitch angle RMS, rate (RATE.R/P) band RMS 3.5-5.5 Hz, rate spectrum peak
  - velocity-loop D term (PIDN/PIDE.D) RMS at 4-5 Hz and the D-term tilt command / actual tilt
    at the roll/pitch peak (tools/sim/hover/IDENT.md, logs/ANALYSIS_2026-11-03_log45_oscillation.md)
"""
import sys

import numpy as np
from pymavlink import mavutil

G = 9.80665


def load(path):
    T = ("RATE", "PIDN", "PIDE", "ATT", "CTUN", "PSCN", "PSCE", "PSCD", "MSG")
    m = mavutil.mavlink_connection(path)
    D = {k: [] for k in T}
    while True:
        x = m.recv_match(type=list(T))
        if x is None:
            break
        D[x.get_type()].append(x.to_dict())
    return {k: v for k, v in D.items()}


def series(D, k, f, u):
    t = np.array([d["TimeUS"] for d in D[k]]) / 1e6
    return np.interp(u, t, np.array([d[f] for d in D[k]]))


def band(x, fs, f0, f1):
    F = np.fft.rfft(x - x.mean())
    f = np.fft.rfftfreq(len(x), 1 / fs)
    F[(f < f0) | (f > f1)] = 0
    return float(np.sqrt(np.mean(np.fft.irfft(F, len(x)) ** 2)))


def peak(x, fs, f0=0.1, f1=20):
    F = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    s = (f >= f0) & (f <= f1)
    return float(f[s][np.argmax(F[s])])


def tf(a, b, fs, f0=3.0, f1=6.0):
    A = np.fft.rfft((a - a.mean()) * np.hanning(len(a)))
    B = np.fft.rfft((b - b.mean()) * np.hanning(len(b)))
    f = np.fft.rfftfreq(len(a), 1 / fs)
    s = (f >= f0) & (f <= f1)
    i = np.argmax(abs(B[s]))
    H = A[s][i] / B[s][i]
    return float(f[s][i]), float(abs(H)), float(np.degrees(np.angle(H)))


def measure(path):
    D = load(path)
    ct = np.array([d["TimeUS"] for d in D["CTUN"]]) / 1e6
    th = np.array([d["ThO"] for d in D["CTUN"]])
    air = ct[th > 0.05]
    t0, t1 = air[0] + 3, air[-1] - 0.5
    hand = [d["TimeUS"] / 1e6 for d in D["MSG"] if "handed over" in d["Message"]]
    if hand:
        t0 = hand[0] + 5.0
    td = np.array([d["TimeUS"] for d in D["PSCD"]]) / 1e6
    tpd = np.array([d["TPD"] for d in D["PSCD"]])
    s = (td > t0) & (td < t1)
    if s.any():
        hold = np.median(tpd[s][: max(1, s.sum() // 4)])
        down = td[s][tpd[s] > hold + 0.005]
        if len(down):
            t1 = min(t1, down[0] - 0.5)
    fs = 400.0
    u = np.arange(t0, t1, 1 / fs)
    out = {"log": path.split("/")[-1], "hover_s": round(t1 - t0, 1)}
    for ax, k in (("N", "PSCN"), ("E", "PSCE"), ("D", "PSCD")):
        e = series(D, k, "TP" + ax, u) - series(D, k, "P" + ax, u)
        out[f"pos{ax}_rms_mm"] = round(float(np.sqrt(np.mean((e - e.mean()) ** 2))) * 1000, 1)
        out[f"pos{ax}_peak_hz"] = round(peak(e, fs, 0.05, 5), 2)
    for ax, f in (("roll", "Roll"), ("pitch", "Pitch")):
        a = series(D, "ATT", f, u)
        out[f"{ax}_rms_deg"] = round(float(np.std(a)), 2)
    R, P = series(D, "RATE", "R", u), series(D, "RATE", "P", u)
    out["rateR_3.5-5.5Hz_dps"] = round(band(R, fs, 3.5, 5.5), 2)
    out["rateP_3.5-5.5Hz_dps"] = round(band(P, fs, 3.5, 5.5), 2)
    out["rate_peak_hz"] = round(peak(R + P, fs, 0.5, 20), 2)
    dn, de = series(D, "PIDN", "D", u), series(D, "PIDE", "D", u)
    out["velD_4-5Hz_mss"] = round((band(dn, fs, 4, 5) + band(de, fs, 4, 5)) / 2, 3)
    yaw = np.radians(series(D, "ATT", "Yaw", u))
    afwd = dn * np.cos(yaw) + de * np.sin(yaw)
    argt = -dn * np.sin(yaw) + de * np.cos(yaw)
    roll = np.cumsum(R) / fs
    pitch = np.cumsum(P) / fs
    for ax, c, x in (("roll", np.degrees(argt / G), roll), ("pitch", np.degrees(-afwd / G), pitch)):
        f, g, ph = tf(c, x, fs)
        out[f"Dloop_{ax}"] = f"{g:.2f} @ {f:.2f} Hz ({ph:+.0f} deg)"
    return out


if __name__ == "__main__":
    rows = [measure(p) for p in sys.argv[1:]]
    keys = list(rows[0])
    w = max(len(k) for k in keys)
    for k in keys:
        print(f"{k:<{w}}  " + "  ".join(f"{str(r.get(k)):>26}" for r in rows))
