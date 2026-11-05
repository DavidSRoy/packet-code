"""Per-axis plant and disturbance from a long steady hover (400 Hz RATE log).

Usage: python tools/tuning/axis_id.py LOG.BIN T_START T_END

Model per axis: angular acceleration = K * output(t - d) + disturbance. Fits K and d by least
squares on 20 ms windows; the residual is the disturbance angular acceleration. Prints its
spectrum in bands (rad/s^2 RMS) and the attitude error each band produces open-loop.
"""
import sys
import numpy as np
from pymavlink import mavutil

path, T0, T1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
m = mavutil.mavlink_connection(path)
R = []
while True:
    x = m.recv_match(type="RATE")
    if x is None:
        break
    t = x.TimeUS / 1e6
    if T0 < t < T1:
        R.append((t, x.RDes, x.R, x.ROut, x.PDes, x.P, x.POut, x.YDes, x.Y, x.YOut))
R = np.array(R)
t = R[:, 0]; dt = np.median(np.diff(t))
print(f"{len(R)} samples at {1/dt:.0f} Hz, {t[-1]-t[0]:.1f} s")
M = 8
out = {}
for name, ci, co in (("roll", 2, 3), ("pitch", 5, 6), ("yaw", 8, 9)):
    w = np.radians(R[:, ci]); u = R[:, co]
    n = len(w)
    best = None
    cs = np.concatenate([[0], np.cumsum(u)])
    for d in range(0, 41):
        k = np.arange(d + M, n)
        A = np.column_stack([(cs[k - d] - cs[k - d - M]) * dt, np.full(len(k), M * dt)])
        y = w[k] - w[k - M]
        sol, *_ = np.linalg.lstsq(A, y, rcond=None)
        r2 = 1 - ((y - A @ sol) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        if best is None or r2 > best[0]:
            best = (r2, d, sol, k, y, A)
    r2, d, sol, k, y, A = best
    K = sol[0]
    resid = (y - A @ sol) / (M * dt)                      # disturbance angular acceleration, rad/s^2 (20 ms average)
    f = np.fft.rfftfreq(len(resid), dt)
    spec = np.abs(np.fft.rfft(resid * np.hanning(len(resid)))) * 2 / np.hanning(len(resid)).sum()
    psd = spec ** 2 / 2
    bands = [(0.1, 1), (1, 3), (3, 6), (6, 12), (12, 25)]
    txt = []
    for lo, hi in bands:
        b = (f >= lo) & (f < hi)
        rms = np.sqrt(psd[b].sum())
        # open-loop attitude error from this band: acceleration / (2 pi f)^2, at the band centre
        fc = np.sqrt(lo * hi)
        txt.append(f"{lo}-{hi} Hz {rms:.2f} rad/s^2 (~{np.degrees(rms / (2*np.pi*fc)**2):.2f} deg open-loop)")
    out[name] = (K, d * dt, r2)
    print(f"{name:5s}: K {K:7.1f} rad/s^2 per unit | delay {d*dt*1000:3.0f} ms | R^2 {r2:.2f} | output RMS {u.std():.3f}, rate RMS {np.degrees(w.std()):.1f} deg/s")
    print("        disturbance: " + "; ".join(txt))
