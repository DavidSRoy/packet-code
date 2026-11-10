#!/usr/bin/env python3
"""Physics and box-camera model for the hover simulator (ArduPilot SITL JSON backend).

ArduCopter SITL (the same 4.7.2 firmware as the drone) runs the real controllers and EKF3.
This process is its world, in lockstep:

  SITL -> here   servo packet (PWM of motors 1-4) every physics step (SIM_RATE_HZ, 1200 Hz)
  here -> SITL   the new state: gyro and specific force AT THE IMU POSITION (lever arm),
                 position, velocity, attitude

Physics (model.json): rigid body; 4 motors on the ArduPilot quad-X layout with a pure delay
and a first-order lag; thrust curve that ArduPilot's MOT_THST_EXPO / voltage scaling inverts
exactly; ground effect per prop (Cheeseman-Bennett); 4 skid contact points on the box
(spring, damper, smoothed Coulomb friction); linear drag; random torques and forces
(Ornstein-Uhlenbeck), stronger near the ground.

Box camera, like companion/cam_stream.py: frames at rate_hz; the image is exposed at t_exp,
read out at t_cap = t_exp + exposure_to_readout_s, detected detect_s later, and reaches the FC
link_s after that. The Pi turns the tag pose into the drone position with the FC attitude at
t_cap - tilt_attitude_lag_s (pose "imu"), so an attitude change between t_exp and that moment
moves the measured position. It sends VISION_POSITION_ESTIMATE (stamp = t_cap on the Pi clock,
roll = pitch = 0) and VISION_SPEED_ESTIMATE (change between two frames, stamped at the middle),
from sysid 1 / compid 191 on a SITL serial port.

The true state is saved (npz) when the process gets SIGTERM/SIGINT.
"""
import argparse
import json
import math
import os
import signal
import socket
import struct
import sys
import time
from collections import deque

import numpy as np

os.environ.setdefault("MAVLINK20", "1")
from pymavlink import mavutil  # noqa: E402

G = 9.80665
LIFTOFF_H = 0.008                  # m: true CG height above rest that times the stress-test events
SERVO16 = struct.Struct("<HHI16H")
SERVO32 = struct.Struct("<HHI32H")


def quat_to_R(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def quat_mul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2])


def quat_to_euler(q):
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


class OU:
    """Ornstein-Uhlenbeck noise: std sigma, correlation time tau."""

    def __init__(self, sigma, tau, rng):
        self.sigma, self.tau, self.rng = np.asarray(sigma, float), float(tau), rng
        self.x = np.zeros(len(self.sigma))

    def step(self, dt):
        a = math.exp(-dt / self.tau)
        self.x = a * self.x + self.sigma * math.sqrt(1 - a * a) * self.rng.standard_normal(len(self.sigma))
        return self.x


class Drone:
    def __init__(self, M, rng):
        self.M = M
        self.m = M["mass"]
        self.I = np.array(M["inertia"], float)
        L = M["arm_len"]
        ang = np.radians(M["motor_angles_deg"])
        self.r_mot = np.c_[L * np.cos(ang), L * np.sin(ang), np.full(4, M["motor_z"])]
        self.ydir = np.array(M["motor_yaw_dir"], float)
        self.skid = np.array(M["skid_points"], float)
        self.r_imu = np.array(M["imu_pos"], float)
        self.p = np.array([0.0, 0.0, -self.skid[:, 2].max()])
        self.v = np.zeros(3)
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        self.w = np.zeros(3)
        self.wdot = np.zeros(3)
        self.f_body = np.array([0.0, 0.0, -G])      # specific force at the CG, body
        self.T = np.zeros(4)
        self.cmd_hist = deque()                     # (t, actuator[4])
        # disturbances as accelerations (the logs give angular and linear acceleration, not torque)
        self.dalpha = [OU(c["sigma"], c["tau"], rng) for c in M["dist_alpha"]]
        self.daccel = [OU(c["sigma"], c["tau"], rng) for c in M["dist_accel"]]
        self.zp_rest = -(self.skid[:, 2].max() - M["motor_z"])     # prop height (z, NED) resting on the box
        bf = M["battery_v"] / M["battery_v_max"]
        self.bf = bf
        # stress-test events (default off: absent from model.json, no random numbers drawn). Times are
        # in s after the liftoff (true CG first LIFTOFF_H above its resting height), so that t ~ 15 is
        # the middle of a 30 s hold at 2 cm (hold window ~ liftoff + 3 s .. + 33 s).
        #   gust:        {"t": 15, "dur": 1.0, "accel": [0.3, 0, 0]}  world NED acceleration step, m/s^2
        #   thrust_ramp: {"t": 0, "dur": 30, "scale_end": 0.95}  thrust x 1 -> scale_end (held after)
        #   camera.blackout: {"t": 15, "dur": 1.0}  no camera frame exposed in the window
        self.gust = M.get("gust")
        self.thrust_ramp = M.get("thrust_ramp")
        self.events_on = bool(self.gust or self.thrust_ramp or M["camera"].get("blackout"))
        self.t_lift = None

    def thrust_of(self, act):
        M = self.M
        u = np.clip((act - M["spin_min"]) / (M["spin_max"] - M["spin_min"]), 0.0, 1.0)
        w = u * self.bf
        e = M["thrust_expo"]
        return M["thrust_full"] * ((1 - e) * w + e * w * w) * (act > 0.02)

    def ground_effect(self, R):
        """Thrust factor of each prop from its height above where it sits on the box.
        'fit': 1 + a*exp(-h/b), fitted to the hover logs (h = height above the rest height);
        'cb': Cheeseman-Bennett 1/(1-(R/4z)^2) from the prop height above the box top."""
        G_ = self.M["ground_effect"]
        if not G_:
            return np.ones(4)
        zp = self.p[2] + (R @ self.r_mot.T)[2]
        if G_ == "cb":
            h = np.maximum(-zp, 1e-3)
            ratio = np.minimum(self.M["prop_radius"] / (4 * h), 0.5)
            return 1.0 / (1.0 - ratio * ratio)
        h = np.maximum(self.zp_rest - zp, 0.0)
        return 1.0 + self.M["ge_a"] * np.exp(-h / self.M["ge_b"])

    def step(self, dt, t, act_cmd):
        M = self.M
        self.cmd_hist.append((t, act_cmd))
        while len(self.cmd_hist) > 1 and self.cmd_hist[1][0] <= t - M["motor_delay"]:
            self.cmd_hist.popleft()
        act = self.cmd_hist[0][1]
        T_cmd = self.thrust_of(act)
        if self.thrust_ramp and self.t_lift is not None:
            r_ = self.thrust_ramp
            f = min(max((t - self.t_lift - r_["t"]) / r_["dur"], 0.0), 1.0)
            T_cmd = T_cmd * (1.0 + f * (r_["scale_end"] - 1.0))
        a = 1.0 - math.exp(-dt / M["motor_tau"])
        self.T += a * (T_cmd - self.T)

        R = quat_to_R(self.q)
        T = self.T * self.ground_effect(R)
        # forces (body) and torques (body) from the props
        # thrust axis off the IMU z axis (logs 43/45: 0.9 deg nose-up trim, PSC I term -0.15 m/s^2 north)
        bx, by = M.get("thrust_axis_xy", [0.0, 0.0])
        F_b = np.array([bx * T.sum(), by * T.sum(), -T.sum()])
        tau = np.array([-(self.r_mot[:, 1] * T).sum(), (self.r_mot[:, 0] * T).sum(),
                        (self.ydir * T).sum() * M["yaw_torque_per_thrust"]])
        tau -= np.array(M["rot_damp"]) * self.w

        # disturbances: stronger near the ground (recirculation)
        h_cg = -self.p[2] - self.skid[:, 2].max()
        gain = 1.0 + M["dist_ground_gain"] * math.exp(-max(h_cg, 0.0) / M["dist_ground_h"])
        airborne_frac = min(1.0, T.sum() / (self.m * G))
        alpha_d = sum(o.step(dt) for o in self.dalpha) * gain * airborne_frac
        tau = tau + self.I * alpha_d
        accel_d = sum(o.step(dt) for o in self.daccel) * gain * airborne_frac
        F_w = R @ F_b + self.m * accel_d
        F_w = F_w - np.array(M["drag_lin"]) * self.v
        if self.gust and self.t_lift is not None and 0.0 <= t - self.t_lift - self.gust["t"] < self.gust["dur"]:
            F_w = F_w + self.m * np.array(self.gust["accel"], float)

        # skid contact with the box top (z = 0)
        cp = self.p + (R @ self.skid.T).T
        cv = self.v + (R @ np.cross(self.w, self.skid).T).T
        for i in range(len(self.skid)):
            pen = cp[i, 2]
            if pen > 0:
                N = max(0.0, M["contact_k"] * pen + M["contact_c"] * cv[i, 2])
                vt = cv[i, :2]
                fr = -M["contact_mu"] * N * vt / math.sqrt(vt @ vt + M["contact_v_eps"] ** 2)
                Fc = np.array([fr[0], fr[1], -N])
                F_w = F_w + Fc
                tau = tau + np.cross(self.skid[i], R.T @ Fc)

        acc_w = F_w / self.m + np.array([0.0, 0.0, G])
        self.f_body = R.T @ (F_w / self.m)
        self.wdot = (tau - np.cross(self.w, self.I * self.w)) / self.I
        self.v = self.v + acc_w * dt
        self.p = self.p + self.v * dt
        self.w = self.w + self.wdot * dt
        dq = np.r_[1.0, 0.5 * self.w * dt]
        self.q = quat_mul(self.q, dq)
        self.q /= np.linalg.norm(self.q)
        if self.events_on and self.t_lift is None and -self.p[2] - self.skid[:, 2].max() > LIFTOFF_H:
            self.t_lift = t
            print(f"physics: liftoff at t={t:.4f} (stress-test events are timed from here)", flush=True)

    def imu(self):
        """Gyro and specific force at the IMU position (lever arm: wdot x r + w x (w x r))."""
        r = self.r_imu
        f = self.f_body + np.cross(self.wdot, r) + np.cross(self.w, np.cross(self.w, r))
        return self.w.copy(), f


class Camera:
    def __init__(self, C, rng, drone):
        self.C, self.rng, self.d = C, rng, drone
        self.next_exp = 0.5
        self.pending = []                 # (t_send, msg dict)
        self.prev = None                  # (t_cap, pos) for the speed estimate
        self.q_hist = deque()             # (t, q) for the Pi's attitude match
        self.reset_counter = 0
        self.clock_off = 1.7e9            # Pi clock = sim time + this
        self.link = None
        self.sent = []

    def connect(self, url):
        try:
            self.link = mavutil.mavlink_connection(url, source_system=1, source_component=191, autoreconnect=True)
        except Exception as e:
            print("camera link failed:", e, flush=True)
            self.link = None

    def q_at(self, t):
        best = None
        for tt, q in self.q_hist:
            if tt <= t:
                best = q
            else:
                break
        return best if best is not None else self.d.q

    def measure(self, t_exp, t_cap, p_true, q_true):
        """(position, yaw) the Pi reports for the frame exposed at t_exp, or None for no message. Overridable."""
        C = self.C
        # the Pi: tag pose in the camera frame (true attitude at exposure), turned into the
        # drone position with the attitude it has at t_cap - lag
        lid = np.array([0.0, 0.0, C["lid_height_above_ground"] * -1.0])
        R_true = quat_to_R(q_true)
        R_used = quat_to_R(self.q_at(t_cap - C["tilt_attitude_lag_s"]))
        r_cam = np.array(C["cam_pos"])
        rel_cam = R_true.T @ (lid - (p_true + R_true @ r_cam))   # lid seen from the lens (body axes), true
        r_cam_pi = r_cam + np.array(C["pi_cam_pos_err"])         # where the Pi thinks the lens is
        p_meas = lid - R_used @ (rel_cam + r_cam_pi)
        sc = C["noise_tail_mult"] if self.rng.random() < C["noise_tail_frac"] else 1.0
        p_meas = p_meas + sc * self.rng.normal(0, [C["noise_xy_m"], C["noise_xy_m"], C["noise_z_m"]])
        yaw = quat_to_euler(q_true)[2] + self.rng.normal(0, C["noise_yaw_rad"])
        return p_meas, yaw

    def step(self, t):
        C, d = self.C, self.d
        self.q_hist.append((t, d.q.copy()))
        while self.q_hist and self.q_hist[0][0] < t - 0.5:
            self.q_hist.popleft()
        if t >= self.next_exp:
            t_exp = self.next_exp
            self.next_exp += 1.0 / C["rate_hz"] + self.rng.normal(0, C["rate_jitter_s"])
            t_cap = t_exp + C["exposure_to_readout_s"]
            t_send = t_cap + C["detect_s"] + abs(self.rng.normal(0, C["detect_jitter_s"])) + C["link_s"]
            bo = C.get("blackout")
            dark = bool(bo) and d.t_lift is not None and bo["t"] <= t_exp - d.t_lift < bo["t"] + bo["dur"]
            if self.rng.random() >= C["drop_frac"] and not dark:
                self.pending.append([t_send, t_exp, t_cap, d.p.copy(), d.q.copy()])
        out = []
        while self.pending and self.pending[0][0] <= t:
            t_send, t_exp, t_cap, p_true, q_true = self.pending.pop(0)
            measured = self.measure(t_exp, t_cap, p_true, q_true)
            if measured is None:
                continue
            p_meas, yaw = measured
            out.append(("pos", t_cap, p_meas, yaw))
            if C["send_speed"] and self.prev is not None and 0 < t_cap - self.prev[0] < C["speed_max_gap_s"]:
                vel = (p_meas - self.prev[1]) / (t_cap - self.prev[0])
                out.append(("vel", (t_cap + self.prev[0]) / 2, vel, None))
            self.prev = (t_cap, p_meas)
        for kind, ts, v, yaw in out:
            self.sent.append((t, kind, ts, *v))
            if self.link is None:
                continue
            usec = int((ts + self.clock_off) * 1e6)
            try:
                if kind == "pos":
                    self.link.mav.vision_position_estimate_send(usec, float(v[0]), float(v[1]), float(v[2]),
                                                                0.0, 0.0, float(yaw), [0.0] * 21, self.reset_counter)
                else:
                    self.link.mav.vision_speed_estimate_send(usec, float(v[0]), float(v[1]), float(v[2]),
                                                             [0.0] * 9, self.reset_counter)
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(os.path.dirname(__file__), "model.json"))
    ap.add_argument("--set", action="append", default=[], help="override model value: key=json or camera.key=json")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--port", type=int, default=9002)
    ap.add_argument("--cam-url", default="tcp:127.0.0.1:5762")
    ap.add_argument("--out", required=True)
    ap.add_argument("--substeps", type=int, default=2)
    ap.add_argument("--wallmap", default=None, help="file: wall time, sim time every 0.1 s")
    a = ap.parse_args()

    M = json.load(open(a.model))
    for kv in a.set:
        k, v = kv.split("=", 1)
        tgt = M
        parts = k.split(".")
        for p in parts[:-1]:
            tgt = tgt[p]
        tgt[parts[-1]] = json.loads(v)
    rng = np.random.default_rng(a.seed)
    drone = Drone(M, rng)
    cam = Camera(M["camera"], rng, drone)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", a.port))
    sock.settimeout(1.0)

    log = []                       # 400 Hz truth
    t = 0.0
    last_log = -1.0
    cam_connect_t = 3.0            # wall seconds after the first packet
    first_wall = None
    stop = {"now": False}

    def save(*_):
        stop["now"] = True
    signal.signal(signal.SIGTERM, save)
    signal.signal(signal.SIGINT, save)

    act = np.zeros(4)
    wm = open(a.wallmap, "w") if a.wallmap else None
    last_wm = -1.0
    queued = None                      # a packet read while dropping resends, to handle next
    while not stop["now"]:
        if queued is not None:
            data, addr = queued
            queued = None
        else:
            try:
                data, addr = sock.recvfrom(256)
            except socket.timeout:
                continue
        if len(data) == SERVO16.size:
            magic, rate, fcount, *pwm = SERVO16.unpack(data)
        elif len(data) == SERVO32.size:
            magic, rate, fcount, *pwm = SERVO32.unpack(data)
        else:
            continue
        if first_wall is None:
            first_wall = time.time()
        if cam.link is None and time.time() - first_wall > cam_connect_t:
            cam.connect(a.cam_url)
            cam_connect_t = 1e9
        dt = 1.0 / max(rate, 50)
        act = np.array([(p - M["pwm_min"]) / (M["pwm_max"] - M["pwm_min"]) if p > 900 else 0.0 for p in pwm[:4]])
        h = dt / a.substeps
        for _ in range(a.substeps):
            drone.step(h, t, act)
            t += h
        cam.step(t)
        gyro, accel = drone.imu()
        reply = {"timestamp": t,
                 "imu": {"gyro": gyro.tolist(), "accel_body": accel.tolist()},
                 "position": drone.p.tolist(),
                 "quaternion": drone.q.tolist(),
                 "velocity": drone.v.tolist(),
                 "battery": {"voltage": M["battery_v"], "current": 18.0}}
        sock.sendto((json.dumps(reply) + "\n").encode(), addr)
        # SITL resends a packet after 1 s without a reply, so a slow camera render leaves copies of this one
        # queued. They are already answered; stepping again would double the step. A copy that arrives after
        # the reply (a lost reply) is not queued yet and is answered normally.
        sock.settimeout(0.0)
        try:
            while True:
                data, addr = sock.recvfrom(256)
                if struct.unpack_from("<HHI", data)[2] != fcount:
                    queued = (data, addr)
                    break
        except (BlockingIOError, struct.error):
            pass
        sock.settimeout(1.0)
        if wm and t - last_wm >= 0.1:
            last_wm = t
            wm.write(f"{time.time():.4f} {t:.5f}\n")
            wm.flush()
        if t - last_log >= 0.0025 - 1e-9:
            last_log = t
            r, p_, y = quat_to_euler(drone.q)
            log.append((t, *drone.p, *drone.v, r, p_, y, *drone.w, *drone.T, *act))

    arr = np.array(log)
    sent = np.array([(s[0], 0 if s[1] == "pos" else 1, s[2], *s[3:]) for s in cam.sent]) if cam.sent else np.zeros((0, 6))
    np.savez_compressed(a.out, truth=arr, cam=sent,
                        truth_cols="t px py pz vx vy vz roll pitch yaw wx wy wz T1 T2 T3 T4 a1 a2 a3 a4",
                        model=json.dumps(M))
    print(f"physics: saved {len(arr)} truth rows, {len(sent)} camera messages -> {a.out}", flush=True)


if __name__ == "__main__":
    main()
