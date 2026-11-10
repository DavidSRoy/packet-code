import math

import numpy as np
from numpy.typing import NDArray

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]

_NED_TO_NWU = np.diag([1.0, -1.0, -1.0])


def _quat_to_matrix(q: Quat) -> NDArray[np.float64]:
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n == 0.0:
        raise ValueError(f"[frames:quat_to_matrix] Zero-length quaternion — {{q: {q}}}")
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def _matrix_to_quat(m: NDArray[np.float64]) -> Quat:
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = 2 * math.sqrt(tr + 1)
        w, x, y, z = s / 4, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] >= m[1, 1] and m[0, 0] >= m[2, 2]:
        s = 2 * math.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2])
        w, x, y, z = (m[2, 1] - m[1, 2]) / s, s / 4, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] >= m[2, 2]:
        s = 2 * math.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2])
        w, x, y, z = (m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, s / 4, (m[1, 2] + m[2, 1]) / s
    else:
        s = 2 * math.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1])
        w, x, y, z = (m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, s / 4
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    return (float(w), float(x), float(y), float(z))


def camera_pose_world(
    p_ned: Vec3, q_body_to_ned: Quat, cam_pos_frd: Vec3, mount_rot_deg: float = 0.0
) -> tuple[Vec3, Quat]:
    """World is north-west-up metres. The returned quaternion orients a USD camera
    (looks along -Z, +Y is image up) to look along body down, image top toward the
    nose rotated by mount_rot_deg toward body right."""
    r_body = _quat_to_matrix(q_body_to_ned)
    pos = _NED_TO_NWU @ (np.array(p_ned) + r_body @ np.array(cam_pos_frd))

    a = math.radians(mount_rot_deg)
    z_axis = np.array([0.0, 0.0, -1.0])  # camera +Z in body FRD (view is body down)
    y_axis = np.array([math.cos(a), math.sin(a), 0.0])  # image up in body FRD
    x_axis = np.cross(y_axis, z_axis)
    r_cam_to_body = np.column_stack([x_axis, y_axis, z_axis])
    r_cam_world = _NED_TO_NWU @ r_body @ r_cam_to_body
    return (float(pos[0]), float(pos[1]), float(pos[2])), _matrix_to_quat(r_cam_world)
