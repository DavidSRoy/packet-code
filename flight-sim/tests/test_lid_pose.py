import math

import numpy as np
import pytest

from oracle_setup import MOUNT
from imu_pose import ImuPose
from lid_pose import imu_fix, lid_pose
from lid_tags import camera_matrix

# Oracle truth -> lid_pose convention, read from the code (no sign flips):
# * Scene.pose puts the drone origin d0 = (dx, dy, height) mm in the lid frame (origin sticker
#   centre, +x right, +y top, +z up), and the drone frame is x nose / y left / z up. lid_pose
#   returns drone_m in that same lid frame, in metres, so truth is (dx, dy, height) / 1000.
# * Scene.pose turns the drone by rot_z(yaw) CCW; lid_pose's yaw_deg is the nose direction from
#   lid +x, CCW: the same angle.
# * Scene mount (fwd, left, up) mm in the drone frame is lid_pose's Mount (fwd, right, down) m:
#   fwd = x / 1000, right = -y / 1000, down = -z / 1000.
# * imu_fix takes the FC attitude as body FRD -> world NED. Lid frame -> NED is the fixed turn
#   C = diag(1, -1, -1) (lid x = north, lid y = west, lid z = up = -down), body FLU -> FRD is
#   D = diag(1, -1, -1), so B_ned = C @ R_wd @ D, and the Euler angles come out of
#   B = Rz(yaw) Ry(pitch) Rx(roll) (imu_pose.body_to_world).
FLIP = np.diag([1.0, -1.0, -1.0])


def attitude(scene, dx, dy, height, yaw, roll, pitch):
    R_wd = scene.pose(dx, dy, height, yaw, roll, pitch)[2]
    B = FLIP @ R_wd @ FLIP
    pitch_r = -math.asin(B[2, 0])
    return (math.atan2(B[2, 1], B[2, 2]), pitch_r, math.atan2(B[1, 0], B[0, 0]))


def find_one(scene, img, K):
    found = scene.finder.find(img, K)
    assert len(found) == 1
    return found[0]


def test_lid_pose_matches_the_renderer_truth(scene):
    rng = np.random.default_rng(1)
    img, _, _ = scene.render(30.0, 0.0, 500.0, 10.0, 0.0, 0.0, rng)
    K = camera_matrix(scene.w, scene.h, scene.hfov)
    out = lid_pose(find_one(scene, img, K), MOUNT)
    err_mm = np.linalg.norm((np.array(out["drone_m"]) - np.array([0.030, 0.0, 0.500])) * 1000)
    print(f"lid_pose drone_m error {err_mm:.2f} mm")
    assert err_mm < 5.0
    assert out["yaw_deg"] == pytest.approx(10.0, abs=1.0)


def test_imu_fix_with_a_tilted_drone(scene):
    rng = np.random.default_rng(2)
    K = camera_matrix(scene.w, scene.h, scene.hfov)
    imu_state = ImuPose(MOUNT.rot_deg)
    last = {}
    level_att = attitude(scene, 30.0, 0.0, 500.0, 10.0, 0.0, 0.0)
    for _ in range(3):                              # still and disarmed: the zero
        img, _, _ = scene.render(30.0, 0.0, 500.0, 10.0, 0.0, 0.0, rng)
        imu_fix(find_one(scene, img, K), level_att, K, imu_state, MOUNT, zero=True, last=last)
    att = attitude(scene, 30.0, 0.0, 500.0, 10.0, 5.0, 0.0)
    img, _, _ = scene.render(30.0, 0.0, 500.0, 10.0, 5.0, 0.0, rng)
    fixed = imu_fix(find_one(scene, img, K), att, K, imu_state, MOUNT, zero=False, last=last)
    assert fixed["pose"] == "imu"
    out = lid_pose(fixed, MOUNT)
    print(f"imu_fix tilt_deg {out['tilt_deg']}")
    assert out["tilt_deg"] == pytest.approx(5.0, abs=0.5)
    err_mm = np.linalg.norm((np.array(out["drone_m"]) - np.array([0.030, 0.0, 0.500])) * 1000)
    print(f"imu_fix drone_m error {err_mm:.2f} mm")
    assert err_mm < 5.0
