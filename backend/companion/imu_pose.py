"""Lid pose with the tilt from the FC's IMU instead of from the tags.

Two small tags (4 cm, in one column on box 1) give the distance and the heading
well, but the tilt badly: in the 2026-11-02 21:56 hover the tag tilt swung 3-34
deg while the drone tilted under 3 deg, and at 0.4 m each degree of tilt error is
about 7 mm of false sideways position (5-20 cm jumps frame to frame).

So: while the drone sits still and disarmed, keep the tag rotation and the FC
attitude together (the zero, averaged over REF_FRAMES frames). After that, each
frame's rotation is the zero rotation turned by the IMU's attitude change since
the zero, with the heading from the tags; only the position is solved from the
tag corners, with that rotation fixed (a linear least squares).

Frames: lid -> camera rotation R (as solvePnP: X_cam = R @ X_lid + t). FC
attitude: roll, pitch, yaw (rad), body FRD -> world NED.
"""
import collections
import math

import numpy as np

REF_FRAMES = 10          # still frames averaged into the zero


def body_to_world(roll, pitch, yaw):
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    return np.array([[cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
                     [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
                     [-sp, sr * cp, cr * cp]])


def body_to_camera(mount_rot_deg):
    """Body FRD axes in the camera frame (camera looks down, image top = nose), as columns."""
    c, s = math.cos(math.radians(mount_rot_deg)), math.sin(math.radians(mount_rot_deg))
    return np.array([[s, c, 0.0], [-c, s, 0.0], [0.0, 0.0, 1.0]])


def lid_yaw(R):
    """The lid +x axis seen in the camera image plane (the same yaw as lid_tags.py)."""
    return math.atan2(R[1, 0], R[0, 0])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def orthonormal(M):
    U, _, Vt = np.linalg.svd(M)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt
    return R


def translation(R, obj, img, K):
    """t with R fixed: every corner gives two linear equations, x_n * P_z = P_x (and y)."""
    obj, img = np.asarray(obj, float), np.asarray(img, float)
    xn = (img[:, 0] - K[0, 2]) / K[0, 0]
    yn = (img[:, 1] - K[1, 2]) / K[1, 1]
    P = obj @ R.T
    A = np.zeros((2 * len(obj), 3)); b = np.zeros(2 * len(obj))
    A[0::2, 0], A[0::2, 2], b[0::2] = 1.0, -xn, xn * P[:, 2] - P[:, 0]
    A[1::2, 1], A[1::2, 2], b[1::2] = 1.0, -yn, yn * P[:, 2] - P[:, 1]
    return np.linalg.lstsq(A, b, rcond=None)[0]


class ImuPose:
    def __init__(self, mount_rot_deg=0.0):
        self.M = body_to_camera(mount_rot_deg)
        self.still = collections.defaultdict(lambda: collections.deque(maxlen=REF_FRAMES))
        self.ref = {}                     # box -> (R0 lid->camera, body->world at the zero)

    def zero(self, box, R_tags, att):
        """A still, disarmed frame: add it to the zero of this box."""
        q = self.still[box]
        q.append((np.asarray(R_tags, float), body_to_world(*att)))
        if len(q) >= 3:
            self.ref[box] = (orthonormal(sum(r for r, _ in q)), orthonormal(sum(b for _, b in q)))

    def pose(self, box, R_tags, att, obj, img, K):
        """(R, t) with the IMU tilt and the tag heading, or None before this box has a zero."""
        if box not in self.ref:
            return None
        R0, B0 = self.ref[box]
        B = body_to_world(*att)
        Rp = self.M @ B.T @ B0 @ self.M.T @ R0
        d = wrap(lid_yaw(np.asarray(R_tags, float)) - lid_yaw(Rp))
        R = min((Rp @ rot_z(d), Rp @ rot_z(-d)),     # turn about the lid normal to the tag heading
                key=lambda r: abs(wrap(lid_yaw(r) - lid_yaw(np.asarray(R_tags, float)))))
        return R, translation(R, obj, img, K)
