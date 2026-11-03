"""Phase/gain margins of the ArduCopter rate and angle loops on the identified plant."""
import numpy as np

K_ID, T_MEAS, F_GYRO_ID = 130.0, 0.038, 20.0
w = np.logspace(-0.5, 3.2, 6000)          # rad/s
s = 1j * w

def butter2(fc):
    wc = 2 * np.pi * fc
    return wc**2 / (s**2 + np.sqrt(2) * wc * s + wc**2)
def lpf1(fc):
    return 1.0 if fc <= 0 else 1 / (1 + s / (2 * np.pi * fc))
def notch(f0, bw, att_db):
    if f0 <= 0: return 1.0
    w0 = 2 * np.pi * f0; q = f0 / bw; a = 10 ** (-att_db / 20)
    return (s**2 + 2 * a * w0 / q * s / 2 + w0**2) / (s**2 + w0 / q * s + w0**2)
# delay of the motors, ESCs and loop: the measured delay less the 20 Hz gyro filter's group delay
T_MOTOR = T_MEAS - np.sqrt(2) / (2 * np.pi * F_GYRO_ID)

def margins(L):
    mag, ph = np.abs(L), np.unwrap(np.angle(L))
    i = np.where((mag[:-1] >= 1) & (mag[1:] < 1))[0]
    if len(i) == 0: return None
    i = i[0]; wc = w[i]; pm = 180 + np.degrees(ph[i])
    j = np.where((ph[:-1] > -np.pi) & (ph[1:] <= -np.pi))[0]
    gm = -20 * np.log10(mag[j[0]]) if len(j) else np.inf
    return wc, pm, gm

def rate_loop(P, I, D, fltd, fgyro, nf=0, nbw=30, natt=40, k=1.0):
    G = K_ID * k / s * np.exp(-s * T_MOTOR) * butter2(fgyro) * notch(nf, nbw, natt)
    C = P + I / s + D * s * lpf1(fltd)
    return C * G

def report(name, P, I, D, fltd, fgyro, angp, nf=0):
    print(f"{name}: P {P} I {I} D {D} FLTD {fltd} Hz | gyro {fgyro} Hz | notch {nf or 'off'} | angle P {angp}")
    for k in (0.7, 1.0, 1.5):
        L = rate_loop(P, I, D, fltd, fgyro, nf, k=k)
        r = margins(L)
        Tin = L / (1 + L)
        Lo = angp / s * Tin
        ro = margins(Lo)
        # stiffness: output per degree of steady angle error (angle P * rate P)
        print(f"   K x{k}: rate crossover {r[0]:5.1f} rad/s ({r[0]/2/np.pi:4.1f} Hz) PM {r[1]:5.1f} deg GM {r[2]:5.1f} dB"
              f" | angle crossover {ro[0]:5.1f} rad/s PM {ro[1]:5.1f} deg")
    print(f"   stiffness {angp * P * np.pi / 180:.4f} output per degree; integral corner {I / P:.1f} rad/s")

print(f"identified: K {K_ID} rad/s^2 per unit output, delay {T_MEAS*1000:.0f} ms (motors/ESC/loop {T_MOTOR*1000:.0f} ms + 20 Hz gyro filter)\n")
report("NOW     ", 0.135, 0.135, 0.0036, 10, 20, 4.5)
report("filters ", 0.135, 0.135, 0.0036, 10, 40, 4.5, nf=60)
for P, I, D, fltd, ang in ((0.20, 0.40, 0.0045, 20, 6.5), (0.22, 0.45, 0.0050, 20, 7.0), (0.25, 0.50, 0.0060, 20, 7.5), (0.30, 0.6, 0.007, 20, 8.0)):
    report(f"cand P{P}", P, I, D, fltd, 40, ang, nf=60)

print("\n--- search: rate P/D near now, rate I and angle P up; filters 40 Hz + 60 Hz notch ---")
best = []
for P in (0.12, 0.135, 0.15):
    for D in (0.0020, 0.0028, 0.0036):
        for fltd in (10, 15):
            for I in (0.135, 0.25, 0.35, 0.45):
                for angp in (5.0, 6.0, 7.0, 8.0, 9.0):
                    ok = True; out = []
                    for k in (1.0, 1.25):
                        L = rate_loop(P, I, D, fltd, 40, 60, k=k)
                        r = margins(L)
                        ro = margins(angp / s * (L / (1 + L)))
                        if r is None or ro is None: ok = False; break
                        out.append((r, ro))
                    if not ok: continue
                    (r1, o1), (r2, o2) = out
                    if r1[1] >= 50 and r1[2] >= 6 and o1[1] >= 50 and r2[1] >= 35 and r2[2] >= 3 and o2[1] >= 45:
                        stiff = angp * P * np.pi / 180
                        best.append((stiff, I / P, P, I, D, fltd, angp, r1, o1, r2))
best.sort(key=lambda b: (-b[0], -b[1]))
for b in best[:8]:
    stiff, ic, P, I, D, fltd, angp, r1, o1, r2 = b
    print(f"P {P} I {I} D {D} FLTD {fltd} angP {angp} | stiffness {stiff:.4f}/deg (now 0.0106), I corner {ic:.1f} rad/s | "
          f"rate xover {r1[0]:.0f} rad/s PM {r1[1]:.0f} GM {r1[2]:.1f} dB, angle xover {o1[0]:.1f} PM {o1[1]:.0f} | at K x1.25: PM {r2[1]:.0f} GM {r2[2]:.1f}")
