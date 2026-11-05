"""Where a hover still oscillates: frequency and size per loop, from a dataflash log.

Usage: python tools/tuning/oscillation.py LOG.BIN

For each armed flight, from the takeoff script's liftoff (HTO message) to the disarm:
  - rate and angle tracking error (RMS), per axis
  - spectrum of the roll/pitch angle and rate: the peak frequency says which loop rings
    (rate loop 4-7 Hz, angle loop 1-2 Hz, position loop under 1 Hz)
  - position target vs actual from the position controller (PSCN/PSCE/PSCD)
  - the gyro spectrum after the filters (batch sampler)
"""
import sys
import numpy as np
from pymavlink import mavutil


def spectrum_peak(t, x, fmin=0.3, fmax=20.0):
    if len(t) < 64:
        return None
    fs = 1 / np.median(np.diff(t))
    tt = np.arange(t[0], t[-1], 1 / fs)
    xx = np.interp(tt, t, x)
    xx = xx - np.polyval(np.polyfit(tt, xx, 1), tt)          # drop the drift
    win = np.hanning(len(xx))
    f = np.fft.rfftfreq(len(xx), 1 / fs)
    a = np.abs(np.fft.rfft(xx * win)) * 2 / win.sum()
    band = (f >= fmin) & (f <= fmax)
    i = np.argmax(a[band])
    return f[band][i], a[band][i], np.sqrt(np.mean(xx ** 2))


def main():
    m = mavutil.mavlink_connection(sys.argv[1])
    d = {k: [] for k in ("RATE", "ATT", "PSCN", "PSCE", "PSCD", "MSG", "EV", "ISBH", "ISBD")}
    cur = None
    while True:
        x = m.recv_match(type=list(d))
        if x is None:
            break
        t = x.get_type()
        if t == "ISBH":
            cur = {"t": x.SampleUS / 1e6, "type": x.type, "mul": x.mul, "rate": x.smp_rate, "x": [], "y": [], "z": []}
            d["ISBH"].append(cur)
        elif t == "ISBD" and cur is not None:
            cur["x"] += list(x.x); cur["y"] += list(x.y); cur["z"] += list(x.z)
        else:
            d[t].append(x)
    arms = [(e.TimeUS / 1e6, e.Id) for e in d["EV"] if e.Id in (10, 11)]
    lifts = [(x.TimeUS / 1e6, x.Message) for x in d["MSG"] if "HTO: liftoff" in x.Message]
    segs = []
    for tl, msg in lifts:
        dis = [ta for ta, i in arms if i == 11 and ta > tl]
        if dis:
            segs.append((tl, dis[0] - 0.1, msg))
    for tl, td, msg in segs:
        print(f"\n=== flight {tl:.1f}-{td:.1f} s ({td - tl:.1f} s airborne)  [{msg}]")
        R = np.array([(r.TimeUS / 1e6, r.RDes, r.R, r.PDes, r.P, r.YDes, r.Y, r.ROut, r.POut) for r in d["RATE"]
                      if tl + 0.5 < r.TimeUS / 1e6 < td])
        A = np.array([(a.TimeUS / 1e6, a.DesRoll, a.Roll, a.DesPitch, a.Pitch) for a in d["ATT"]
                      if tl + 0.5 < a.TimeUS / 1e6 < td])
        if len(R) < 64 or len(A) < 64:
            print("   too short for the spectrum"); continue
        print(f"   rate log {1 / np.median(np.diff(R[:, 0])):.0f} Hz, attitude log {1 / np.median(np.diff(A[:, 0])):.0f} Hz")
        for name, (cd, ca), (ad, aa) in (("roll", (1, 2), (1, 2)), ("pitch", (3, 4), (3, 4))):
            e_rate = np.sqrt(np.mean((R[:, cd] - R[:, ca]) ** 2))
            e_ang = np.sqrt(np.mean((A[:, ad] - A[:, aa]) ** 2))
            pa = spectrum_peak(A[:, 0], A[:, aa])
            pr = spectrum_peak(R[:, 0], R[:, ca], 0.3, 40)
            pt = spectrum_peak(A[:, 0], A[:, ad])
            print(f"   {name:5s}: rate error {e_rate:5.2f} deg/s RMS, angle error {e_ang:4.2f} deg RMS | "
                  f"angle peak {pa[0]:4.2f} Hz {pa[1]:4.2f} deg (RMS {pa[2]:.2f}) | target peak {pt[0]:4.2f} Hz {pt[1]:4.2f} deg | "
                  f"rate peak {pr[0]:4.1f} Hz {pr[1]:4.2f} deg/s")
        e_y = np.sqrt(np.mean((R[:, 5] - R[:, 6]) ** 2))
        print(f"   yaw  : rate error {e_y:5.2f} deg/s RMS")
        for k, lab in (("PSCN", "north"), ("PSCE", "east"), ("PSCD", "down")):
            P = [p for p in d[k] if tl + 0.5 < p.TimeUS / 1e6 < td]
            if not P:
                continue
            fields = P[0].get_fieldnames()
            tp, pp = ("TPN", "PN") if "TPN" in fields else ("TPE", "PE") if "TPE" in fields else ("TPD", "PD")
            t = np.array([p.TimeUS / 1e6 for p in P]); tgt = np.array([getattr(p, tp) for p in P]); act = np.array([getattr(p, pp) for p in P])
            pk = spectrum_peak(t, act - tgt, 0.1, 4)
            print(f"   pos {lab:5s}: error RMS {np.sqrt(np.mean((act - tgt) ** 2)) * 100:4.1f} cm, max {np.max(np.abs(act - tgt)) * 100:4.1f} cm"
                  + (f", peak {pk[0]:.2f} Hz {pk[1] * 100:.1f} cm" if pk else ""))
        G = [b for b in d["ISBH"] if b["type"] == 1 and tl < b["t"] < td]
        for i, b in enumerate(G[:4]):
            n = min(len(b["x"]), len(b["y"]), len(b["z"]))
            if n < 256:
                continue
            sig = np.array([b["x"][:n], b["y"][:n], b["z"][:n]], float) / b["mul"]
            sig -= sig.mean(axis=1, keepdims=True)
            win = np.hanning(n)
            f = np.fft.rfftfreq(n, 1 / b["rate"])
            a = np.degrees(np.sqrt((np.abs(np.fft.rfft(sig * win, axis=1)) * 2 / win.sum()) ** 2).sum(axis=0))
            top = np.argsort(a[f > 10])[::-1][:4]
            print(f"   gyro batch {i}: " + ", ".join(f"{f[f > 10][j]:.0f} Hz {a[f > 10][j]:.2f}" for j in top) + " deg/s")


if __name__ == "__main__":
    main()
