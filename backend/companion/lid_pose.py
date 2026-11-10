"""The lid pose maths of cam_stream.py, importable without the camera and the servers.

lid_pose: camera and drone pose in the lid frame from one LidFinder result.
imu_fix:  the same result with the rotation from the FC attitude (imu_pose.py).
"""
import math
from dataclasses import dataclass

import cv2
import numpy as np

from imu_pose import ImuPose, wrap

STILL_RAD = math.radians(0.3)             # attitude change between zero frames above this: not still


@dataclass(frozen=True)
class Mount:
    """Camera mount in the drone body frame (see cam_stream.py): m ahead of, right of and below the drone centre."""
    fwd_m: float
    right_m: float
    down_m: float
    rot_deg: float


def lid_pose(r: dict, mount: Mount) -> dict:
    """Camera and drone pose in the lid frame from one LidFinder result.

    Lid frame: origin at the sticker centre, +x along the long side (sticker
    right), +y along the short side (sticker top), +z up out of the lid.
    Camera frame: x image right, y image down, z out of the lens.
    """
    R = np.array(r["R"]); t = np.array(r["xyz_m"])
    Rt = R.T                                  # camera frame -> lid frame
    cam = -Rt @ t                             # camera position in the lid frame
    # Drone body axes in the camera frame (camera looks down, image top = nose),
    # then turned by the mount rotation about the down axis.
    c, s = math.cos(math.radians(mount.rot_deg)), math.sin(math.radians(mount.rot_deg))
    fwd_c = np.array([s, -c, 0.0])
    right_c = np.array([c, s, 0.0])
    down_c = np.array([0.0, 0.0, 1.0])
    to_centre_c = -(mount.fwd_m * fwd_c + mount.right_m * right_c + mount.down_m * down_c)
    centre = cam + Rt @ to_centre_c
    fwd_l = Rt @ fwd_c
    yaw = math.degrees(math.atan2(fwd_l[1], fwd_l[0]))   # nose direction from lid +x, CCW
    down_l = Rt @ down_c
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, -down_l[2]))))
    tag_tilt = tilt
    if r.get("tag_R") is not None:                # the tags' own tilt, for comparison (imu_fix)
        tag_tilt = math.degrees(math.acos(max(-1.0, min(1.0, -(np.array(r["tag_R"]).T @ down_c)[2]))))
    return {"box": r["box"], "tags": r["tags"], "px_per_cell": round(r["px_per_cell"], 1),
            "pose": r.get("pose", "tags"), "tag_tilt_deg": round(tag_tilt, 1),
            "camera_m": [round(v, 4) for v in cam], "drone_m": [round(v, 4) for v in centre],
            "yaw_deg": round(yaw, 1), "tilt_deg": round(tilt, 1),
            "range_m": round(r["range_m"], 3), "outlines": r["outlines"],
            "rvec": [round(float(v), 5) for v in cv2.Rodrigues(R)[0].ravel()],   # lid -> camera rotation
            "tvec": [round(float(v), 4) for v in t]}                            # lid origin in the camera frame, m


def imu_fix(r: dict, att: tuple[float, float, float] | None, K: np.ndarray, imu: ImuPose, mount: Mount,
            *, zero: bool, last: dict) -> dict:
    # mount is unused: ImuPose already carries the mount rotation.
    """While still and disarmed (zero): add the frame to the zero. Then (armed or not): the rotation
    from the IMU tilt and the tag heading, the position from the corners (imu_pose.py).
    Without a zero or an attitude: the tag-only pose, marked so.

    att: the FC attitude at the frame's time, or None. last: box -> attitude of its last zero frame
    (stillness check), kept by the caller between frames. The caller holds the lock around the call."""
    r = dict(r, pose="tags", tag_tilt=None)
    if att is None:
        return r
    if zero:
        prev = last.get(r["box"])
        if prev is not None and max(abs(att[0] - prev[0]), abs(att[1] - prev[1]), abs(wrap(att[2] - prev[2]))) > STILL_RAD:
            imu.still[r["box"]].clear()                # moved: start the zero again
        last[r["box"]] = att
        imu.zero(r["box"], r["R"], att)
    res = imu.pose(r["box"], r["R"], att, r["obj"], r["img"], K)
    if res is None:
        return r
    R, t = res
    return dict(r, R=R.tolist(), xyz_m=t.tolist(), pose="imu", tag_R=r["R"])
