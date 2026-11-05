"""Horizontal position loop (ArduCopter PSC_NE) on the measured acceleration response.

Plant: commanded acceleration -> position = G * exp(-T s) / s^2, with G and T measured from
EKF velocity (XKF1, 25 Hz) against the commanded acceleration (PSCN/PSCE): G ~0.6, T 0.2-0.33 s in
the 2026-11-03 hovers (10 Hz PSC accelerations gave an optimistic 0.92 / 0.20 s).
Controller: velocity target = POS_P * position error; acceleration = VEL_P*e + VEL_I*int(e)
+ VEL_D*de/dt, the error through FLTE and the D term through FLTD (first order).
Reports the velocity and position loop margins and the closed-loop resonance (the peak of
position target -> position: how much a disturbance near that frequency is amplified, the
visible sway), and the stiffness against a constant push (low-frequency |1/(1+L)|).
"""
import numpy as np

G, T = 0.6, 0.30          # measured at 25 Hz (EKF velocity vs command); 0.92 / 0.20 from 10 Hz data was optimistic
w = np.logspace(-2, 2, 8000)
s = 1j * w


def lpf(fc):
    return 1 / (1 + s / (2 * np.pi * fc))


def loops(pos_p, vel_p, vel_i, vel_d, flte=5.0, fltd=5.0, g=G, t=T):
    plant_v = g * np.exp(-t * s) / s                      # acceleration -> velocity
    cv = (vel_p + vel_i / s) * lpf(flte) + vel_d * s * lpf(fltd)
    lv = cv * plant_v
    tv = lv / (1 + lv)
    lp = pos_p * tv / s                                   # velocity target -> position
    tp = lp / (1 + lp)
    return lv, lp, tp


def margin(L):
    mag, ph = np.abs(L), np.unwrap(np.angle(L))
    i = np.where((mag[:-1] >= 1) & (mag[1:] < 1))[0]
    if not len(i):
        return None
    i = i[-1]
    j = np.where((ph[:-1] > -np.pi) & (ph[1:] <= -np.pi))[0]
    gm = -20 * np.log10(mag[j[0]]) if len(j) else np.inf
    return w[i], 180 + np.degrees(ph[i]), gm


def report(name, pos_p, vel_p, vel_i, vel_d, **kw):
    out = []
    for g, t in ((G, T), (G, T * 1.3)):
        lv, lp, tp = loops(pos_p, vel_p, vel_i, vel_d, g=g, t=t, **kw)
        mv, mp = margin(lv), margin(lp)
        k = np.argmax(np.abs(tp))
        out.append((mv, mp, np.abs(tp)[k], w[k]))
    (mv, mp, pk, wk), (mv2, mp2, pk2, wk2) = out
    print(f"{name:34s} vel PM {mv[1]:4.0f} GM {mv[2]:4.1f} dB | pos xover {mp[0]:.2f} rad/s PM {mp[1]:4.0f} | "
          f"resonance x{pk:.2f} at {wk / 2 / np.pi:.2f} Hz | delay +30%: pos PM {mp2[1]:4.0f}, resonance x{pk2:.2f}")
    return mp[1], pk, mp2[1], pk2


if __name__ == "__main__":
    print(f"plant: acceleration gain {G}, delay {T * 1000:.0f} ms\n")
    report("NOW  P1 V2 I1 D0.25", 1.0, 2.0, 1.0, 0.25)
    rows = []
    for pos_p in (0.6, 0.8, 1.0, 1.2):
        for vel_p in (1.2, 1.5, 2.0, 2.5):
            for vel_i in (0.0, 0.3, 0.5, 1.0):
                for vel_d in (0.0, 0.25, 0.5, 0.75):
                    lv, lp, tp = loops(pos_p, vel_p, vel_i, vel_d)
                    lv2, lp2, tp2 = loops(pos_p, vel_p, vel_i, vel_d, t=T * 1.3)
                    mv, mp, mp2 = margin(lv), margin(lp), margin(lp2)
                    if not (mv and mp and mp2):
                        continue
                    pk, pk2 = np.abs(tp).max(), np.abs(tp2).max()
                    stiff = pos_p * vel_p                       # acceleration per metre of error (low frequency)
                    rows.append((pk, pk2, -stiff, pos_p, vel_p, vel_i, vel_d, mp[1], mv[1], mv[2]))
    print("\nlowest resonance with stiffness >= 1.5 m/s^2 per m and margins kept:")
    good = [r for r in rows if -r[2] >= 1.5 and r[7] >= 55 and r[8] >= 45 and r[9] >= 8 and r[1] < 1.25]
    good.sort()
    for r in good[:10]:
        pk, pk2, ns, pos_p, vel_p, vel_i, vel_d, pm, vpm, vgm = r
        report(f"P{pos_p} V{vel_p} I{vel_i} D{vel_d} (stiff {-ns:.1f})", pos_p, vel_p, vel_i, vel_d)


def push_response(pos_p, vel_p, vel_i, vel_d, flte=5.0, fltd=5.0, g=G, t=T):
    """RMS position (per unit) for a broadband acceleration push (flat 0.05-5 Hz): the sway."""
    plant_p = np.exp(-t * s) / s ** 2                       # disturbance acceleration -> position
    cv = (vel_p + vel_i / s) * lpf(flte) + vel_d * s * lpf(fltd)
    # loop: a_cmd = cv*(pos_p*(-x) - v) -> x;  x/d = plant / (1 + g*plant*cv*(pos_p + s))
    h = plant_p / (1 + g * np.exp(-t * s) / s ** 2 * cv * (pos_p + s))
    band = (w >= 2 * np.pi * 0.05) & (w <= 2 * np.pi * 5)
    return np.sqrt(np.trapezoid(np.abs(h[band]) ** 2, w[band]))


if __name__ == "__main__":
    base = push_response(1.0, 2.0, 1.0, 0.25)
    print(f"\nsway for the same push, relative to now (lower = stiller); margins at the measured delay and +30 %:")
    rows = []
    for pos_p in (0.8, 1.0, 1.2, 1.5, 1.8):
        for vel_p in (2.0, 2.5, 3.0, 3.5):
            for vel_i in (0.5, 1.0, 1.5, 2.0):
                for vel_d in (0.0, 0.25, 0.5):
                    lv, lp, tp = loops(pos_p, vel_p, vel_i, vel_d)
                    lv2, lp2, tp2 = loops(pos_p, vel_p, vel_i, vel_d, t=T * 1.3)
                    mv, mp, mv2, mp2 = margin(lv), margin(lp), margin(lv2), margin(lp2)
                    if not (mv and mp and mv2 and mp2):
                        continue
                    if mv[1] < 45 or mv[2] < 6 or mp[1] < 45 or mp2[1] < 35 or np.abs(tp2).max() > 1.3 or mv2[1] < 30:
                        continue
                    rows.append((push_response(pos_p, vel_p, vel_i, vel_d) / base, pos_p, vel_p, vel_i, vel_d, mv, mp, np.abs(tp).max(), mp2, mv2))
    rows.sort()
    for r in rows[:8]:
        sw, pos_p, vel_p, vel_i, vel_d, mv, mp, pk, mp2, mv2 = r
        print(f"  P{pos_p} V{vel_p} I{vel_i} D{vel_d}: sway x{sw:.2f} | vel PM {mv[1]:.0f} GM {mv[2]:.1f} | pos PM {mp[1]:.0f} "
              f"resonance x{pk:.2f} | delay +30%: vel PM {mv2[1]:.0f}, pos PM {mp2[1]:.0f}")
