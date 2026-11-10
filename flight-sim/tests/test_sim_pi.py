import csv
from collections import deque
import dataclasses
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

import physics
from flightsim import sim_pi
from flightsim.frames import Quat, Vec3
from flightsim.profiles import CameraProfile, ComputeProfile, load_compute
from flightsim.recorder import Recorder
from lid_camera_sim import CAM_IN_DRONE
from oracle_setup import CAM_MOUNT_MM

ROOT = Path(__file__).resolve().parents[2]
MODEL = json.loads((ROOT / "backend" / "tools" / "sim" / "hover" / "model.json").read_text())
COMPUTE = dataclasses.replace(
    load_compute(ROOT / "flight-sim" / "profiles" / "compute" / "pi-zero-2w.json"),
    detect_scale=1.0, detect_jitter_s=0.0,
)
LEVEL: Quat = (1.0, 0.0, 0.0, 0.0)


@dataclass
class FakeDrone:
    p: NDArray[np.float64]
    q: NDArray[np.float64] = field(default_factory=lambda: np.array(LEVEL))
    t_lift: float | None = None
    cmd_hist: deque[tuple[float, NDArray[np.float64]]] = field(default_factory=lambda: deque([(0.0, np.zeros(4))]))


class StubRenderer:
    """Renders the oracle scene at the camera pose it is asked for (level or yawed drones only)."""

    def __init__(self, scene, seed: int = 3) -> None:
        self.scene = scene
        self.rng = np.random.default_rng(seed)
        self.calls: list[tuple[Vec3, Quat, float]] = []

    def render(self, pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]:
        self.calls.append((pos, quat, t))
        usd_to_cv = np.diag([1.0, -1.0, -1.0])                    # USD camera (up, back) -> OpenCV camera (down, forward)
        r_wd = physics.quat_to_R(quat) @ usd_to_cv @ CAM_IN_DRONE.T
        yaw = math.degrees(math.atan2(r_wd[1, 0], r_wd[0, 0]))
        d0 = np.array(pos) * 1000.0 - r_wd @ np.array(CAM_MOUNT_MM)
        img, _, _ = self.scene.render(d0[0], d0[1], d0[2], yaw, 0.0, 0.0, self.rng)
        return img


def make_camera(scene, drone: FakeDrone, *, lag_s: float = 0.0, recorder: Recorder | None = None,
                compute: ComputeProfile = COMPUTE, send_speed: bool = False, lid_xy: tuple[float, float] = (0.0, 0.0),
                occluder_mount_mm: tuple[float, float, float] = CAM_MOUNT_MM):
    fwd, left, up = (v / 1000.0 for v in CAM_MOUNT_MM)
    C = dict(MODEL["camera"], cam_pos=[fwd, -left, -up], pi_cam_pos_err=[0.0, 0.0, 0.0],
             rate_jitter_s=0.0, drop_frac=0.0, send_speed=send_speed, tilt_attitude_lag_s=lag_s,
             noise_tail_frac=0.0)
    cam_profile = CameraProfile("stub", scene.w, scene.h, scene.hfov, True, "global", {}, "linear")
    renderer = StubRenderer(scene)
    cam = sim_pi.RenderedCamera(C, np.random.default_rng(1), drone, renderer=renderer, finder=scene.finder,
                                camera=cam_profile, compute=compute, recorder=recorder, lid_xy=lid_xy,
                                occluder_mount_mm=occluder_mount_mm)
    return cam, renderer


def run(cam, drone: FakeDrone, until_s: float, on_step=None) -> list[tuple[float, str, float, float, float, float]]:
    n = round(until_s / 0.001)
    for k in range(n):
        t = k * 0.001
        if on_step is not None:
            on_step(t)
        cam.step(t)
    return cam.sent


def test_estimate_matches_truth_over_lid(scene):
    drone = FakeDrone(np.array([0.030, 0.0, -0.500]))
    cam, renderer = make_camera(scene, drone)
    sent = run(cam, drone, 0.7)
    assert len(sent) == 1 and sent[0][1] == "pos"
    err_mm = np.linalg.norm((np.array(sent[0][3:6]) - drone.p) * 1000)
    print(f"sent position error {err_mm:.2f} mm")
    assert err_mm < 5.0
    assert renderer.calls[0][2] == pytest.approx(0.5)             # rendered at the exposure time


def test_lid_away_from_the_physics_origin_is_rendered_relative_and_estimated_in_the_world(scene):
    drone = FakeDrone(np.array([0.230, -0.050, -0.500]))
    cam, renderer = make_camera(scene, drone, lid_xy=(0.200, -0.050))
    sent = run(cam, drone, 0.7)
    assert len(sent) == 1
    err_mm = np.linalg.norm((np.array(sent[0][3:6]) - drone.p) * 1000)
    assert err_mm < 5.0
    # the camera is 30 mm north of the lid centre, as in the test above
    assert renderer.calls[0][0][0] == pytest.approx(0.030 + CAM_MOUNT_MM[0] / 1000.0, abs=1e-9)


def test_no_tags_sends_nothing_and_records_row(scene, tmp_path: Path):
    drone = FakeDrone(np.array([0.0, 0.0, -20.0]))
    rec = Recorder(tmp_path, fps=10.0)
    cam, _ = make_camera(scene, drone, recorder=rec)
    sent = run(cam, drone, 0.7)
    rec.close()
    assert sent == []
    rows = list(csv.DictReader((tmp_path / "frames.csv").read_text().splitlines()))
    assert len(rows) == 1 and rows[0]["detected"] == "0" and rows[0]["true_z"] == "-20.0"


def test_compute_profile_delay_is_applied(scene):
    # distinct from model.json's camera block, so the override is what is measured
    compute = dataclasses.replace(COMPUTE, rate_hz=7.0, exposure_to_readout_s=0.03, detect_s=0.2,
                                  link_s=0.01, detect_jitter_s=0.0)
    drone = FakeDrone(np.array([0.030, 0.0, -0.500]))
    cam, renderer = make_camera(scene, drone, compute=compute)
    t_first_send = None
    for k in range(1000):
        t = k * 0.001
        cam.step(t)
        if cam.sent and t_first_send is None:
            t_first_send = t
    assert len(renderer.calls) >= 2
    t_exp0, t_exp1 = renderer.calls[0][2], renderer.calls[1][2]
    assert t_first_send is not None
    assert t_first_send - t_exp0 == pytest.approx(compute.exposure_to_readout_s + compute.detect_s + compute.link_s,
                                                   abs=0.0015)
    assert t_exp1 - t_exp0 == pytest.approx(1.0 / 7.0)


@pytest.mark.parametrize("rolled_at_exposure", [True, False])
def test_attitude_comes_from_parent_lagged_truth(scene, monkeypatch: pytest.MonkeyPatch, rolled_at_exposure: bool):
    seen: list[tuple[float, float, float] | None] = []
    real = sim_pi.imu_fix

    def spy(r, att, K, imu, mount, *, zero, last):
        seen.append(att)
        return real(r, att, K, imu, mount, zero=zero, last=last)

    monkeypatch.setattr(sim_pi, "imu_fix", spy)
    drone = FakeDrone(np.array([0.030, 0.0, -0.500]))
    cam, _ = make_camera(scene, drone, lag_s=0.02)
    t_exp = cam.next_exp
    t_cap = t_exp + cam.C["exposure_to_readout_s"]
    t_lag = t_cap - cam.C["tilt_attitude_lag_s"]
    t_mid = (t_exp + t_lag) / 2                                  # between the exposure and the lagged sample
    assert t_exp < t_mid < t_lag < t_cap
    roll = math.radians(5.0)
    rolled = np.array([math.cos(roll / 2), math.sin(roll / 2), 0.0, 0.0])
    level = np.array(LEVEL)

    def on_step(t: float) -> None:
        # rolled only in the window that holds the exposure (or only the one that holds the lagged sample);
        # level again before the send, so the attitude at send time is level either way
        in_window = t < t_mid if rolled_at_exposure else t_mid <= t < t_cap
        drone.q = rolled if in_window else level

    run(cam, drone, 0.7, on_step)
    assert len(seen) == 1 and seen[0] is not None
    lagged_roll = 0.0 if rolled_at_exposure else roll
    assert seen[0] == pytest.approx((lagged_roll, 0.0, 0.0))
    assert seen[0] == pytest.approx(physics.quat_to_euler(cam.q_at(t_lag)))


def test_zeroing_stops_at_the_first_motor_command_and_stays_off(scene, monkeypatch: pytest.MonkeyPatch):
    zeros: list[bool] = []
    real = sim_pi.imu_fix

    def spy(r, att, K, imu, mount, *, zero, last):
        zeros.append(zero)
        return real(r, att, K, imu, mount, zero=zero, last=last)

    monkeypatch.setattr(sim_pi, "imu_fix", spy)
    drone = FakeDrone(np.array([0.030, 0.0, -0.500]))               # at rest height or not, only commands count
    cam, _ = make_camera(scene, drone)

    def on_step(t: float) -> None:
        if abs(t - 0.75) < 5e-4:
            drone.cmd_hist.append((t, np.full(4, 0.2)))             # first non-zero command
        if abs(t - 0.95) < 5e-4:
            drone.cmd_hist.clear()
            drone.cmd_hist.append((t, np.zeros(4)))                 # motors back to zero: still latched

    run(cam, drone, 1.2, on_step)
    assert zeros[0] is True and zeros[-1] is False and len(zeros) >= 3
    assert zeros == sorted(zeros, reverse=True)                     # True... then False..., never back


def test_a_failing_frame_is_dropped_and_the_run_goes_on(scene, monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path):
    real = sim_pi.imu_fix
    calls: list[int] = []

    def flaky(r, att, K, imu, mount, *, zero, last):
        calls.append(1)
        if len(calls) == 1:
            raise np.linalg.LinAlgError("SVD did not converge")
        return real(r, att, K, imu, mount, zero=zero, last=last)

    monkeypatch.setattr(sim_pi, "imu_fix", flaky)
    drone = FakeDrone(np.array([0.030, 0.0, -0.500]))
    rec = Recorder(tmp_path, fps=10.0)
    cam, _ = make_camera(scene, drone, recorder=rec)
    sent = run(cam, drone, 0.9, None)
    rec.close()
    assert [s[2] for s in sent] == pytest.approx([0.66, 0.76])    # exposure 0.5 dropped; 0.6 and 0.7 sent
    assert "[sim_pi:measure] Frame dropped" in capsys.readouterr().err
    rows = list(csv.DictReader((tmp_path / "frames.csv").read_text().splitlines()))
    assert [r["detected"] for r in rows][:2] == ["0", "1"]


def test_speed_needs_two_imu_frames_in_a_row(scene, monkeypatch: pytest.MonkeyPatch):
    poses = iter(["imu", "imu", "tags", "imu", "imu"])
    real = sim_pi.imu_fix

    def relabel(r, att, K, imu, mount, *, zero, last):
        return dict(real(r, att, K, imu, mount, zero=zero, last=last), pose=next(poses))

    monkeypatch.setattr(sim_pi, "imu_fix", relabel)
    drone = FakeDrone(np.array([0.030, 0.0, -0.500]))
    cam, _ = make_camera(scene, drone, send_speed=True)
    sent = run(cam, drone, 1.05)                                   # five frames sent, the sixth still in flight
    kinds = [s[1] for s in sent]
    assert kinds.count("pos") == 5 and kinds.count("vel") == 2
    # vel follows frame 2 and frame 5 only (pos index 1 and 4)
    pos_seen = 0
    after = []
    for k in kinds:
        if k == "pos":
            pos_seen += 1
        else:
            after.append(pos_seen)
    assert after == [2, 5]


def test_occluder_mount_that_differs_from_the_camera_position_is_refused(scene):
    drone = FakeDrone(np.array([0.0, 0.0, -0.5]))
    shifted = (CAM_MOUNT_MM[0] + 5.0, CAM_MOUNT_MM[1], CAM_MOUNT_MM[2])
    with pytest.raises(ValueError, match=r"\[sim_pi:RenderedCamera\] Occluder mount differs"):
        make_camera(scene, drone, occluder_mount_mm=shifted)


def test_compute_delay_longer_than_the_attitude_history_is_refused(scene):
    drone = FakeDrone(np.array([0.0, 0.0, -0.5]))
    slow = dataclasses.replace(COMPUTE, detect_s=0.6)
    with pytest.raises(ValueError, match=r"\[sim_pi:RenderedCamera\] Compute delay is longer than the attitude history"):
        make_camera(scene, drone, compute=slow)
