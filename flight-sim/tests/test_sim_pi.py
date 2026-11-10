import csv
import dataclasses
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

import physics
from conftest import CAM_MOUNT_MM
from flightsim import sim_pi
from flightsim.frames import Quat, Vec3
from flightsim.profiles import CameraProfile, ComputeProfile, load_compute
from flightsim.recorder import Recorder
from lid_camera_sim import CAM_IN_DRONE

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


class StubRenderer:
    """Renders the oracle scene at the camera pose it is asked for (level or yawed drones only)."""

    def __init__(self, scene, seed: int = 3) -> None:
        self.scene = scene
        self.rng = np.random.default_rng(seed)
        self.calls: list[tuple[Vec3, Quat, float]] = []
        self.last_frame_id = -1

    def render(self, pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]:
        self.calls.append((pos, quat, t))
        usd_to_cv = np.diag([1.0, -1.0, -1.0])                    # USD camera (up, back) -> OpenCV camera (down, forward)
        r_wd = physics.quat_to_R(quat) @ usd_to_cv @ CAM_IN_DRONE.T
        yaw = math.degrees(math.atan2(r_wd[1, 0], r_wd[0, 0]))
        d0 = np.array(pos) * 1000.0 - r_wd @ np.array(CAM_MOUNT_MM)
        img, _, _ = self.scene.render(d0[0], d0[1], d0[2], yaw, 0.0, 0.0, self.rng)
        self.last_frame_id += 1
        return img


def make_camera(scene, drone: FakeDrone, *, lag_s: float = 0.0, recorder: Recorder | None = None,
                compute: ComputeProfile = COMPUTE):
    fwd, left, up = (v / 1000.0 for v in CAM_MOUNT_MM)
    C = dict(MODEL["camera"], cam_pos=[fwd, -left, -up], pi_cam_pos_err=[0.0, 0.0, 0.0],
             rate_jitter_s=0.0, drop_frac=0.0, send_speed=False, tilt_attitude_lag_s=lag_s,
             noise_tail_frac=0.0)
    cam_profile = CameraProfile("stub", scene.w, scene.h, scene.hfov, True, "global", {})
    renderer = StubRenderer(scene)
    cam = sim_pi.RenderedCamera(C, np.random.default_rng(1), drone, renderer=renderer, finder=scene.finder,
                                camera=cam_profile, compute=compute, recorder=recorder)
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
    drone = FakeDrone(np.array([0.030, 0.0, -0.500]))
    cam, _ = make_camera(scene, drone)
    t_sent: list[float] = []
    for k in range(700):
        t = k * 0.001
        cam.step(t)
        if cam.sent and not t_sent:
            t_sent.append(t)
    assert t_sent[0] - 0.5 == pytest.approx(0.06 + 0.05 + 0.005, abs=0.0015)


def test_attitude_comes_from_parent_lagged_truth(scene, monkeypatch: pytest.MonkeyPatch):
    seen: list[tuple[float, float, float] | None] = []
    real = sim_pi.imu_fix

    def spy(r, att, K, imu, mount, *, zero, last):
        seen.append(att)
        return real(r, att, K, imu, mount, zero=zero, last=last)

    monkeypatch.setattr(sim_pi, "imu_fix", spy)
    drone = FakeDrone(np.array([0.030, 0.0, -0.500]))
    cam, _ = make_camera(scene, drone, lag_s=0.02)
    roll = math.radians(5.0)
    rolled = np.array([math.cos(roll / 2), math.sin(roll / 2), 0.0, 0.0])

    def on_step(t: float) -> None:
        if t >= 0.55:                  # after the exposure; t_cap - lag = 0.54 still sees the level drone
            drone.q = rolled

    run(cam, drone, 0.7, on_step)
    assert len(seen) == 1 and seen[0] is not None
    assert seen[0] == pytest.approx(physics.quat_to_euler(cam.q_at(0.56 - 0.02)))
    assert seen[0] == pytest.approx((0.0, 0.0, 0.0))
    assert physics.quat_to_euler(drone.q)[0] == pytest.approx(roll)   # the current truth is different
