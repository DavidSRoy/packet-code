import math
import warnings
from pathlib import Path

import cv2
import lid_stickers as LS
import numpy as np
import pytest
from lid_camera_sim import CAMERAS, Scene

from flightsim import drone_geometry as dg
from flightsim.truth_check import (
    CAM_POS_FRD,
    DEFAULT_LAYOUT_DIR,
    TruthPose,
    check,
    pose_grid,
)

_STICKER = dict(
    w=218.0, h=200.0, big_cell=18.0, small_cell=3.75, inset=5.0,
    extra=[(-44.5, 80), (0, 80), (44.5, 80), (-44.5, -80), (0, -80), (44.5, -80),
           (-89, 36), (-89, -36), (89, 36), (89, -36)],
)


@pytest.fixture(scope="module")
def oracle():
    LS.configure(**_STICKER)
    mp = pytest.MonkeyPatch()
    mp.setitem(CAMERAS, "OV9281", (1280, 800, 70.0, True))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)  # LidFinder never closes its layout file
        yield Scene("OV9281", dg.CAMERA_MOUNT_MM, 0.0, str(DEFAULT_LAYOUT_DIR / "lid_layout.json"))
    mp.undo()


def test_grid_covers_heights_offsets_and_yaws():
    grid = pose_grid()
    assert sorted({p.height_m for p in grid}) == [0.3, 0.5, 1.0, 2.0, 3.0]
    assert len({(p.dx_m, p.dy_m) for p in grid}) > 1
    assert len({p.yaw_deg for p in grid}) > 1
    assert len({p.name for p in grid}) == len(grid)


def test_camera_pose_matches_the_oracle_geometry(oracle):
    for p in pose_grid():
        R, t, _, _ = oracle.pose(p.dx_m * 1e3, p.dy_m * 1e3, p.height_m * 1e3, p.yaw_deg, 0.0, 0.0)
        cam_mm = -R.T @ t                      # camera position in the lid frame
        r_usd = R.T @ np.diag([1.0, -1.0, -1.0])  # oracle camera axes (x right, y down, z fwd) -> USD (x right, y up, z back)
        pos, quat = p.camera_pose()
        np.testing.assert_allclose(np.array(pos) * 1e3, cam_mm, atol=1e-6)
        w, x, y, z = quat
        r = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ])
        np.testing.assert_allclose(r, r_usd, atol=1e-9)


def test_lid_in_camera_matches_the_oracle(oracle):
    for p in pose_grid():
        _, t, _, _ = oracle.pose(p.dx_m * 1e3, p.dy_m * 1e3, p.height_m * 1e3, p.yaw_deg, 0.0, 0.0)
        np.testing.assert_allclose(p.lid_in_camera_m() * 1e3, t, atol=1e-6)


def test_truth_check_passes_on_the_oracle_frames(oracle, tmp_path):
    rng = np.random.default_rng(3)
    for i, p in enumerate(pose_grid()):
        img, _, _ = oracle.render(p.dx_m * 1e3, p.dy_m * 1e3, p.height_m * 1e3, p.yaw_deg, 0.0, 0.0, rng)
        cv2.imwrite(str(tmp_path / f"pose_{i:02d}.png"), img)
    results = check(tmp_path)
    for r in results:
        print(r)
    assert len(results) == len(pose_grid())
    assert all(r.passed for r in results)


def test_check_fails_a_pose_with_no_frame_content(tmp_path):
    for i, _ in enumerate(pose_grid()):
        cv2.imwrite(str(tmp_path / f"pose_{i:02d}.png"), np.full((800, 1280), 95, np.uint8))
    results = check(tmp_path)
    assert not any(r.detected or r.passed for r in results)


def test_oracle_mount_matches_the_frd_mount():
    assert CAM_POS_FRD == (0.070, -0.095, 0.100)
    assert math.isclose(dg.CAMERA_MOUNT_MM[1], 95.0)
