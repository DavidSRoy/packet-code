import math

import pytest

from flightsim.frames import Quat, Vec3, camera_pose_world


def rotate(q: Quat, v: Vec3) -> Vec3:
    w, x, y, z = q
    vx, vy, vz = v
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def test_level_camera_looks_down_with_north_up():
    pos, q = camera_pose_world((0, 0, -1.0), (1, 0, 0, 0), (0, 0, 0))
    assert pos == pytest.approx((0, 0, 1.0))
    assert rotate(q, (0, 0, -1)) == pytest.approx((0, 0, -1))
    assert rotate(q, (0, 1, 0)) == pytest.approx((1, 0, 0))


def test_yaw_east_turns_image_up_east():
    h = math.sqrt(0.5)
    _, q = camera_pose_world((0, 0, -1.0), (h, 0, 0, h), (0, 0, 0))
    assert rotate(q, (0, 0, -1)) == pytest.approx((0, 0, -1))
    assert rotate(q, (0, 1, 0)) == pytest.approx((0, -1, 0))


def test_lever_arm_moves_camera_forward():
    pos, _ = camera_pose_world((0, 0, -1.0), (1, 0, 0, 0), (0.127, 0, 0.101))
    assert pos == pytest.approx((0.127, 0, 0.899))


def test_mount_rotation_turns_image_up_toward_right():
    _, q = camera_pose_world((0, 0, -1.0), (1, 0, 0, 0), (0, 0, 0), 90.0)
    assert rotate(q, (0, 1, 0)) == pytest.approx((0, -1, 0))
    assert rotate(q, (0, 0, -1)) == pytest.approx((0, 0, -1))


def test_roll_tilts_view_axis():
    a = math.radians(30) / 2
    _, q = camera_pose_world((0, 0, -1.0), (math.cos(a), math.sin(a), 0, 0), (0, 0, 0))
    # positive roll about nose: body down swings toward body left, which is west (world +y)
    assert rotate(q, (0, 0, -1)) == pytest.approx((0, math.sin(math.radians(30)), -math.cos(math.radians(30))))
