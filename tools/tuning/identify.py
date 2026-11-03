"""Rate-loop tuning from a dataflash log: gyro spectrum and per-axis plant identification.

Usage: python tools/tuning/identify.py LOG.BIN ARM_S DISARM_S [OUT.npy]
The ISBH batches alternate raw and filtered (INS_LOG_BAT_OPT 4): the one with the large
high-frequency peaks is the raw gyro. Refit on the airborne part only (the legs resist rotation).
"""
import sys, math
import numpy as np
from pymavlink import mavutil

path = sys.argv[1]
T_ARM, T_DISARM = float(sys.argv[2]), float(sys.argv[3])
m = mavutil.mavlink_connection(path)
rate, ctun, batches, msgs = [], [], [], []
cur = None
while True:
    x = m.recv_match(type=["RATE", "CTUN", "ISBH", "ISBD", "MSG"])
    if x is None: break
    t = x.get_type()
    if t == "RATE": rate.append((x.TimeUS / 1e6, x.RDes, x.R, x.ROut, x.PDes, x.P, x.POut, x.YDes, x.Y, x.YOut, x.AOut))
    elif t == "CTUN": ctun.append((x.TimeUS / 1e6, x.ThO, x.Alt))
    elif t == "MSG": msgs.append((x.TimeUS / 1e6, x.Message))
    elif t == "ISBH":
        cur = {"t": x.SampleUS / 1e6, "type": x.type, "inst": x.instance, "mul": x.mul, "rate": x.smp_rate, "x": [], "y": [], "z": []}
        batches.append(cur)
    elif t == "ISBD" and cur is not None:
        cur["x"] += list(x.x); cur["y"] += list(x.y); cur["z"] += list(x.z)
rate = np.array(rate); ctun = np.array(ctun)
for t, s in msgs:
    if T_ARM - 1 < t < T_DISARM + 1 and ("HTO" in s or "Hop" in s): print(f"  {t:7.2f} {s}")

# ---- 1. gyro spectrum during the hover (throttle out > 0.2) ----
thr = lambda t: np.interp(t, ctun[:, 0], ctun[:, 1])
gyro = [b for b in batches if b["type"] == 1 and T_ARM < b["t"] < T_DISARM and thr(b["t"]) > 0.2]
print(f"\ngyro batches in the hover: {len(gyro)} (of {len(batches)}); sample rate {gyro[0]['rate'] if gyro else 0:.0f} Hz")
spec = {}
for i, b in enumerate(gyro):
    n = min(len(b["x"]), len(b["y"]), len(b["z"]))
    if n < 256: continue
    sig = np.array([b["x"][:n], b["y"][:n], b["z"][:n]], float) / b["mul"]          # rad/s
    sig -= sig.mean(axis=1, keepdims=True)
    win = np.hanning(n)
    f = np.fft.rfftfreq(n, 1 / b["rate"])
    amp = np.abs(np.fft.rfft(sig * win, axis=1)) * 2 / win.sum()
    key = "pre" if i % 2 == 0 else "post"                                       # INS_LOG_BAT_OPT 4: pre and post filter, in turn
    spec.setdefault(key, []).append((f, amp))
for key, lst in spec.items():
    f = lst[0][0]; a = np.mean([np.sqrt((s[1] ** 2).sum(axis=0)) for s in lst if len(s[0]) == len(f)], axis=0)
    a_deg = np.degrees(a)
    top = np.argsort(a_deg[f > 10])[::-1]
    fs, as_ = f[f > 10], a_deg[f > 10]
    peaks, used = [], []
    for j in top:
        if any(abs(fs[j] - u) < 8 for u in used): continue
        used.append(fs[j]); peaks.append((fs[j], as_[j]))
        if len(peaks) == 6: break
    lo = as_[(fs > 10) & (fs < 60)].mean(); hi = as_[(fs > 60) & (fs < 400)].mean()
    print(f"  {key}-filter ({len(lst)} batches): peaks " + ", ".join(f"{p[0]:.0f} Hz {p[1]:.3f} deg/s" for p in peaks)
          + f" | mean 10-60 Hz {lo:.3f}, 60-400 Hz {hi:.3f} deg/s")

# ---- 2. plant identification per axis ----
# airborne-ish: throttle output above 80 % of hover (the legs carry little) until disarm
t = rate[:, 0]
dt = np.median(np.diff(t))
sel = (t > T_ARM) & (t < T_DISARM - 0.05) & (rate[:, 10] > 0.8 * 0.275)
print(f"\nrate samples used: {sel.sum()} at {1/dt:.0f} Hz, {t[sel][0] if sel.any() else 0:.2f}-{t[sel][-1] if sel.any() else 0:.2f} s")
M = 8                                                                            # 20 ms windows
res = {}
for name, ci, co in (("roll", 2, 3), ("pitch", 5, 6), ("yaw", 8, 9)):
    w = np.radians(rate[:, ci]); u = rate[:, co]
    idx = np.where(sel)[0]
    best = None
    for d in range(0, 41):                                                       # 0-100 ms delay
        rows, ys = [], []
        for k in idx:
            if k - d - M < 0 or k >= len(t): continue
            ys.append(w[k] - w[k - M])
            rows.append([u[k - d - M:k - d].sum() * dt, M * dt])
        A, y = np.array(rows), np.array(ys)
        sol, *_ = np.linalg.lstsq(A, y, rcond=None)
        r2 = 1 - ((y - A @ sol) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        if best is None or r2 > best[0]: best = (r2, d, sol[0], sol[1])
    r2, d, K, b = best
    res[name] = (K, d * dt, b)
    print(f"  {name:5s}: K = {K:7.1f} rad/s^2 per unit output | delay {d*dt*1000:4.0f} ms | constant torque {b:6.2f} rad/s^2 "
          f"(= {b/K if K else 0:+.3f} output to cancel) | fit R^2 {r2:.2f}")
np.save(sys.argv[4] if len(sys.argv) > 4 else "/dev/null", np.array([[*res[n]] for n in ("roll", "pitch", "yaw")]))
