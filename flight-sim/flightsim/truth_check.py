"""Second gate: does the real lid detector recover the true pose from Isaac's frames?

Run inside the venv on the cluster (python -m flightsim.truth_check --port P --out DIR). The Isaac
server runs separately; this side asks it for frames, saves them, and judges them.

Two gates per pose, both at the same limit: the detector's own xyz_m against the true lid origin in the
camera frame, and the drone centre after imu_fix with the true attitude (zeroed on still frames at 0.5 m
with the same yaw). The tag-only drone centre is reported, not gated.
"""
import argparse
import json
import math
import statistics
import sys
import time
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from flightsim import drone_geometry
from flightsim.frames import Quat, Vec3, quat_to_matrix, camera_pose_world
from flightsim.profiles import load_camera
from flightsim.render_link import RenderClient
from imu_pose import REF_FRAMES, ImuPose
from lid_pose import Mount, imu_fix, lid_pose
from lid_tags import LidFinder, camera_matrix

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAYOUT_DIR = _ROOT.parent / "backend" / "companion" / "stickers_218x200"
CAMERA_PROFILE = _ROOT / "profiles" / "cameras" / "ov9281.json"
BOX = 1
# The camera mount in the drone body frame: geometry is x nose / y left / z up in mm, the Mount is
# ahead / right / below in metres.
_MX, _MY, _MZ = drone_geometry.CAMERA_MOUNT_MM
CAM_POS_FRD: Vec3 = (_MX / 1000.0, -_MY / 1000.0, -_MZ / 1000.0)
MOUNT = Mount(fwd_m=CAM_POS_FRD[0], right_m=CAM_POS_FRD[1], down_m=CAM_POS_FRD[2], rot_deg=0.0)

_HEIGHTS_M = (0.3, 0.5, 1.0, 2.0, 3.0)
_OFFSETS_M = ((0.0, 0.0), (0.03, -0.02))  # (north, west) = lid (x, y)
_YAWS_DEG = (0.0, 30.0)
_NEAR_LIMIT_M = 0.005     # up to and including 1.0 m
_NEAR_MAX_HEIGHT_M = 1.0
_FAR_FRACTION = 0.02      # of range, beyond 1.0 m
_ZERO_HEIGHT_M = 0.5


@dataclass(frozen=True)
class TruthPose:
    """Drone centre dx, dy, height in the lid frame (x north, y west, z up), nose yaw CCW from lid +x."""
    name: str
    dx_m: float
    dy_m: float
    height_m: float
    yaw_deg: float

    def drone_truth_m(self) -> Vec3:
        return (self.dx_m, self.dy_m, self.height_m)

    def lid_in_camera_m(self) -> NDArray[np.float64]:
        """Where the lid origin is in the detector's camera frame (x right, y down, z forward):
        the quantity LidFinder returns as xyz_m."""
        pos, quat = self.camera_pose()
        usd_to_cv = np.diag([1.0, -1.0, -1.0])  # USD camera axes (x right, y up, z back) -> OpenCV
        return -(quat_to_matrix(quat) @ usd_to_cv).T @ np.array(pos)

    def attitude(self) -> tuple[float, float, float]:
        """FC attitude (roll, pitch, yaw rad, body FRD to NED) of the level drone; yaw is the lid yaw negated."""
        return (0.0, 0.0, -math.radians(self.yaw_deg))

    def camera_pose(self) -> tuple[Vec3, Quat]:
        half = math.radians(-self.yaw_deg) / 2  # lid CCW about up is NED yaw about down, negated
        p_ned = (self.dx_m, -self.dy_m, -self.height_m)
        return camera_pose_world(p_ned, (math.cos(half), 0.0, 0.0, math.sin(half)), CAM_POS_FRD)


@dataclass(frozen=True)
class TruthResult:
    pose: TruthPose
    detected: bool
    error_m: float | None       # |detector xyz_m - true lid origin in the camera frame|; gated
    imu_error_m: float | None   # drone centre after imu_fix with the true attitude; gated
    tag_drone_error_m: float | None  # drone centre from the tags alone; reported, not gated
    yaw_error_deg: float | None
    range_m: float
    limit_m: float
    passed: bool


def pose_grid() -> list[TruthPose]:
    return [
        TruthPose(f"h{h:.1f}_o{k}_y{yaw:+.0f}", dx, dy, h, yaw)
        for h in _HEIGHTS_M
        for k, (dx, dy) in enumerate(_OFFSETS_M)
        for yaw in _YAWS_DEG
    ]


def zero_poses() -> list[TruthPose]:
    """One still pose per distinct yaw in the grid, at 0.5 m above the lid centre: the IMU zero frames."""
    return [TruthPose(f"zero_y{yaw:+.0f}", 0.0, 0.0, _ZERO_HEIGHT_M, yaw) for yaw in sorted({p.yaw_deg for p in pose_grid()})]


def frame_path(frames_dir: Path, index: int) -> Path:
    return frames_dir / f"pose_{index:02d}.png"


def zero_frame_path(frames_dir: Path, yaw_index: int, k: int) -> Path:
    return frames_dir / f"zero_{yaw_index:02d}_{k:02d}.png"


def _read(path: Path) -> NDArray[np.uint8]:
    gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise FileNotFoundError(f"[truth_check:read] Missing or unreadable frame — {{path: {path}}}")
    return gray


def check(frames_dir: Path, layout_dir: Path = DEFAULT_LAYOUT_DIR) -> list[TruthResult]:
    camera = load_camera(CAMERA_PROFILE)
    K = camera_matrix(camera.width, camera.height, camera.hfov_deg)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)  # LidFinder never closes its layout file
        finder = LidFinder(str(layout_dir / "lid_layout.json"))
    zero_yaws = [z.yaw_deg for z in zero_poses()]
    zero_found = [
        [
            f
            for k in range(REF_FRAMES)
            for f in finder.find(_read(zero_frame_path(Path(frames_dir), yi, k)), K)
            if f["box"] == BOX
        ]
        for yi in range(len(zero_yaws))
    ]
    results: list[TruthResult] = []
    for index, pose in enumerate(pose_grid()):
        gray = _read(frame_path(Path(frames_dir), index))
        cam_pos = np.array(pose.camera_pose()[0])
        range_m = float(np.linalg.norm(cam_pos))
        limit_m = _NEAR_LIMIT_M if pose.height_m <= _NEAR_MAX_HEIGHT_M else _FAR_FRACTION * range_m
        found = [r for r in finder.find(gray, K) if r["box"] == BOX]
        if not found:
            results.append(TruthResult(pose, False, None, None, None, None, range_m, limit_m, False))
            continue
        out = lid_pose(found[0], MOUNT)
        error_m = float(np.linalg.norm(np.array(found[0]["xyz_m"]) - pose.lid_in_camera_m()))
        tag_error_m = float(np.linalg.norm(np.array(out["drone_m"]) - np.array(pose.drone_truth_m())))
        yaw_error = (out["yaw_deg"] - pose.yaw_deg + 180.0) % 360.0 - 180.0
        imu_error_m = _imu_error_m(pose, found[0], zero_found[zero_yaws.index(pose.yaw_deg)], K)
        passed = error_m < limit_m and imu_error_m is not None and imu_error_m < limit_m
        results.append(TruthResult(pose, True, error_m, imu_error_m, tag_error_m, yaw_error, range_m, limit_m, passed))
    return results


def _imu_error_m(pose: TruthPose, found: dict, zero_found: list[dict], K: NDArray[np.float64]) -> float | None:
    """Drone centre error after imu_fix with the true attitude, zeroed on the still frames; None if no IMU pose."""
    imu = ImuPose(MOUNT.rot_deg)
    last: dict = {}
    for frame in zero_found:
        imu_fix(frame, pose.attitude(), K, imu, MOUNT, zero=True, last=last)  # still: same attitude as the pose
    fixed = imu_fix(found, pose.attitude(), K, imu, MOUNT, zero=False, last=last)
    if fixed["pose"] != "imu":
        return None
    out = lid_pose(fixed, MOUNT)
    return float(np.linalg.norm(np.array(out["drone_m"]) - np.array(pose.drone_truth_m())))


def _contact_sheet(frames_dir: Path, results: list[TruthResult], columns: int = 4) -> NDArray[np.uint8]:
    thumbs: list[NDArray[np.uint8]] = []
    for index, r in enumerate(results):
        image = cv2.imread(str(frame_path(frames_dir, index)))
        if image is None:
            raise FileNotFoundError(
                f"[truth_check:contact_sheet] Missing or unreadable frame — {{path: {frame_path(frames_dir, index)}}}"
            )
        thumb = cv2.resize(image, (320, 200), interpolation=cv2.INTER_AREA)
        label = f"{r.pose.name} {'ok' if r.passed else 'FAIL'}"
        cv2.putText(thumb, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if r.passed else (0, 0, 255), 1)
        thumbs.append(thumb)
    blank = np.zeros_like(thumbs[0])
    while len(thumbs) % columns:
        thumbs.append(blank)
    rows = [np.hstack(thumbs[i:i + columns]) for i in range(0, len(thumbs), columns)]
    return np.vstack(rows)


def _report(results: list[TruthResult]) -> str:
    lines = ["pose            detected  err_mm  imu_mm  limit_mm  tags_mm  yaw_err  range_m  result"]
    for r in results:
        err = "-" if r.error_m is None else f"{r.error_m * 1e3:.2f}"
        imu = "-" if r.imu_error_m is None else f"{r.imu_error_m * 1e3:.2f}"
        tags = "-" if r.tag_drone_error_m is None else f"{r.tag_drone_error_m * 1e3:.1f}"
        yaw = "-" if r.yaw_error_deg is None else f"{r.yaw_error_deg:+.1f}"
        lines.append(
            f"{r.pose.name:<15} {str(r.detected):<9} {err:>6}  {imu:>6}  {r.limit_m * 1e3:8.1f}  {tags:>7}  {yaw:>7}  "
            f"{r.range_m:7.3f}  {'PASS' if r.passed else 'FAIL'}"
        )
    return "\n".join(lines)


def _run(port: int, out_dir: Path, layout_dir: Path) -> int:
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    client = RenderClient("127.0.0.1", port, timeout_s=600.0)
    render_ms: list[float] = []

    def render(pose: TruthPose, t: float) -> NDArray[np.uint8]:
        pos, quat = pose.camera_pose()
        start = time.perf_counter()
        frame = client.render(pos, quat, t)
        render_ms.append((time.perf_counter() - start) * 1e3)
        return frame

    try:
        for yaw_index, zero in enumerate(zero_poses()):
            for k in range(REF_FRAMES):
                cv2.imwrite(str(zero_frame_path(frames_dir, yaw_index, k)), render(zero, float(k)))
        for index, pose in enumerate(pose_grid()):
            cv2.imwrite(str(frame_path(frames_dir, index)), render(pose, float(index)))
    finally:
        client.quit()
    results = check(frames_dir, layout_dir)
    cv2.imwrite(str(out_dir / "contact-sheet.png"), _contact_sheet(frames_dir, results))
    timing = {"min": min(render_ms), "median": statistics.median(render_ms), "max": max(render_ms), "frames": len(render_ms)}
    (out_dir / "truth-results.json").write_text(
        json.dumps({"render_ms": timing, "poses": [asdict(r) for r in results]}, indent=1)
    )
    print(f"render ms per frame (first request included): {timing}", flush=True)
    print(_report(results), flush=True)
    failed = [r.pose.name for r in results if not r.passed]
    if failed:
        print(f"[truth_check:run] Gate failed — {{failed: {failed}}}", file=sys.stderr)
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--layout-dir", type=Path, default=DEFAULT_LAYOUT_DIR)
    args = parser.parse_args()
    return _run(args.port, args.out, args.layout_dir)


if __name__ == "__main__":
    sys.exit(main())
