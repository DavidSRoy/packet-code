"""Attitude gains that minimise the angle error for the measured disturbance torque.

Plant per axis (tools/tuning/axis_id.py on the 62 s hover, log 00000035): K/s with total delay
T (motors, ESCs, props, gyro filter and notch). Controller as ArduCopter: angle P into a rate
PID (D through FLTD, error through FLTE). A torque disturbance with the measured band spectrum
enters as angular acceleration; the angle error is the disturbance through
(1/s^2) / (1 + L_rate + ANG_P * L_rate / s)  (rate loop and angle loop closed).
"""
import numpy as np

w = np.logspace(-1, 3, 6000)
s = 1j * w

# measured disturbance (rad/s^2 RMS per band) and plants
AXES = {
    "roll":  dict(K=81.2, T=0.052, bands=[(0.1, 1, 0.52), (1, 3, 0.38), (3, 6, 0.41), (6, 12, 0.37), (12, 25, 0.48)]),
    "pitch": dict(K=73.1, T=0.055, bands=[(0.1, 1, 0.54), (1, 3, 0.42), (3, 6, 0.44), (6, 12, 0.31), (12, 25, 0.19)]),
}


def lpf(fc):
    return 1.0 if fc <= 0 else 1 / (1 + s / (2 * np.pi * fc))


def loops(K, T, P, I, D, ang_p, fltd=15.0, flte=0.0):
    G = K * np.exp(-T * s) / s
    C = (P + I / s) * lpf(flte) + D * s * lpf(fltd)
    L = C * G                                             # rate loop
    Lang = ang_p * (L / (1 + L)) / s                      # angle loop around the closed rate loop
    # disturbance angular acceleration -> angle: plant 1/s^2 with both loops closed
    Hd = (np.exp(0 * s) / s ** 2) / (1 + L + ang_p * L / s)
    return L, Lang, Hd


def margin(L):
    mag, ph = np.abs(L), np.unwrap(np.angle(L))
    i = np.where((mag[:-1] >= 1) & (mag[1:] < 1))[0]
    if not len(i):
        return None
    i = i[0]
    j = np.where((ph[:-1] > -np.pi) & (ph[1:] <= -np.pi))[0]
    gm = -20 * np.log10(mag[j[0]]) if len(j) else np.inf
    return w[i], 180 + np.degrees(ph[i]), gm


def angle_error_deg(Hd, bands):
    """RMS angle error for a disturbance flat within each measured band."""
    tot = 0.0
    for lo, hi, rms in bands:
        b = (w >= 2 * np.pi * lo) & (w < 2 * np.pi * hi)
        psd = rms ** 2 / (2 * np.pi * (hi - lo))           # per rad/s
        tot += np.trapezoid(np.abs(Hd[b]) ** 2 * psd, w[b])
    return np.degrees(np.sqrt(tot))


def evaluate(ax, P, I, D, ang_p, fltd=15.0, kscale=1.0, tscale=1.0):
    a = AXES[ax]
    L, Lang, Hd = loops(a["K"] * kscale, a["T"] * tscale, P, I, D, ang_p, fltd)
    return margin(L), margin(Lang), angle_error_deg(Hd, a["bands"]), np.abs(Lang / (1 + Lang)).max()


if __name__ == "__main__":
    now = dict(P=0.15, I=0.45, D=0.002, ang_p=9.0, fltd=15.0)
    for ax in AXES:
        r, a, e, pk = evaluate(ax, **now)
        print(f"{ax} NOW P{now['P']} I{now['I']} D{now['D']} angP{now['ang_p']}: rate xover {r[0]:.1f} rad/s PM {r[1]:.0f} GM {r[2]:.1f} dB | "
              f"angle PM {a[1]:.0f}, peak x{pk:.2f} | predicted angle error {e:.2f} deg RMS")
    print("\nsearch: smallest predicted angle error, margins held at K x1.3 and delay x1.15")
    rows = []
    for P in (0.08, 0.10, 0.12, 0.15, 0.18):
        for I in (0.15, 0.3, 0.45, 0.7, 1.0):
            for D in (0.0, 0.002, 0.004, 0.006):
                for fltd in (10.0, 20.0):
                    for ang_p in (4.5, 6.0, 7.5, 9.0, 11.0, 13.0):
                        ok, err = True, 0.0
                        for ax in AXES:
                            r, a, e, pk = evaluate(ax, P, I, D, ang_p, fltd)
                            r2, a2, _, pk2 = evaluate(ax, P, I, D, ang_p, fltd, kscale=1.3, tscale=1.15)
                            if not (r and a and r2 and a2):
                                ok = False; break
                            if r[1] < 45 or r[2] < 6 or a[1] < 45 or pk > 1.3 or r2[1] < 30 or r2[2] < 3 or a2[1] < 35:
                                ok = False; break
                            err = max(err, e)
                        if ok:
                            rows.append((err, P, I, D, fltd, ang_p))
    rows.sort()
    for err, P, I, D, fltd, ang_p in rows[:8]:
        line = f"P{P} I{I} D{D} FLTD{fltd:.0f} angP{ang_p}: worst axis {err:.2f} deg RMS |"
        for ax in AXES:
            r, a, e, pk = evaluate(ax, P, I, D, ang_p, fltd)
            line += f" {ax} PM {r[1]:.0f} GM {r[2]:.1f} angPM {a[1]:.0f} ({e:.2f} deg)"
        print(line)


YAW = dict(K=8.5, T=0.05, bands=[(0.1, 1, 0.09), (1, 3, 0.07), (3, 6, 0.07), (6, 12, 0.07), (12, 25, 0.19)])


def yaw_eval(P, I, flte, ang_p, kscale=1.0):
    L, Lang, Hd = loops(YAW["K"] * kscale, YAW["T"], P, I, 0.0, ang_p, fltd=0.0, flte=flte)
    return margin(L), margin(Lang), angle_error_deg(Hd, YAW["bands"]), np.abs(Lang / (1 + Lang)).max()


if __name__ == "__main__":
    r, a, e, pk = yaw_eval(0.18, 0.018, 2.0, 4.5)
    print(f"\nyaw NOW P0.18 I0.018 FLTE2 angP4.5: rate xover {r[0]:.1f} rad/s PM {r[1]:.0f} | angle PM {a[1]:.0f} peak x{pk:.2f} | predicted heading error {e:.2f} deg RMS (flown: 1.93)")
    rows = []
    for P in (0.3, 0.45, 0.6, 0.8, 1.0):
        for I in (0.03, 0.06, 0.1, 0.2, 0.4):
            for flte in (2.0, 3.0, 5.0):
                for ang_p in (3.0, 4.5, 6.0):
                    ok, worst = True, 0.0
                    for ks in (0.6, 1.0, 1.5):
                        r, a, e, pk = yaw_eval(P, I, flte, ang_p, ks)
                        if not (r and a) or r[1] < 45 or r[2] < 6 or a[1] < 45 or pk > 1.3:
                            ok = False; break
                        worst = max(worst, e)
                    if ok:
                        rows.append((yaw_eval(P, I, flte, ang_p)[2], worst, P, I, flte, ang_p))
    rows.sort()
    for e, worst, P, I, flte, ang_p in rows[:5]:
        r, a, _, pk = yaw_eval(P, I, flte, ang_p)
        print(f"yaw P{P} I{I} FLTE{flte} angP{ang_p}: heading error {e:.2f} deg RMS (worst over K x0.6-1.5: {worst:.2f}) | rate xover {r[0]:.1f} PM {r[1]:.0f} GM {r[2]:.1f} | angle PM {a[1]:.0f}")
