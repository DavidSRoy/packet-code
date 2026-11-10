"""Second gate: does the real lid detector recover the true pose from Isaac's frames?

Run inside the venv on the cluster (python -m flightsim.truth_check run ...). The Isaac server runs
separately; this side asks it for frames, saves them, and judges them.
"""
import argparse
import json
import math
import sys
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from flightsim.frames import Quat, Vec3, _quat_to_matrix, camera_pose_world
from flightsim.profiles import load_camera
from flightsim.render_link import RenderClient
from lid_pose import Mount, lid_pose
from lid_tags import LidFinder, camera_matrix

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAYOUT_DIR = _ROOT.parent / "backend" / "companion" / "stickers_218x200"
CAMERA_PROFILE = _ROOT / "profiles" / "cameras" / "ov9281.json"
BOX = 1
# Oracle mount D: 70 mm ahead, 95 mm left, 100 mm below the drone centre (FRD: right is negative).
CAM_POS_FRD: Vec3 = (0.070, -0.095, 0.100)
MOUNT = Mount(fwd_m=0.070, right_m=-0.095, down_m=0.100, rot_deg=0.0)

_HEIGHTS_M = (0.3, 0.5, 1.0, 2.0, 3.0)
_OFFSETS_M = ((0.0, 0.0), (0.03, -0.02))  # (north, west) = lid (x, y)
_YAWS_DEG = (0.0, 30.0)
_NEAR_LIMIT_M = 0.005     # up to and including 1.0 m
_NEAR_MAX_HEIGHT_M = 1.0
_FAR_FRACTION = 0.02      # of range, beyond 1.0 m


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
        return -(_quat_to_matrix(quat) @ usd_to_cv).T @ np.array(pos)

    def camera_pose(self) -> tuple[Vec3, Quat]:
        half = math.radians(-self.yaw_deg) / 2  # lid CCW about up is NED yaw about down, negated
        p_ned = (self.dx_m, -self.dy_m, -self.height_m)
        return camera_pose_world(p_ned, (math.cos(half), 0.0, 0.0, math.sin(half)), CAM_POS_FRD)


@dataclass(frozen=True)
class TruthResult:
    pose: TruthPose
    detected: bool
    error_m: float | None       # |detector xyz_m - true lid origin in the camera frame|; gated
    drone_error_m: float | None  # drone centre from lid_pose without IMU tilt; reported, not gated
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


def frame_path(frames_dir: Path, index: int) -> Path:
    return frames_dir / f"pose_{index:02d}.png"


def check(frames_dir: Path, layout_dir: Path = DEFAULT_LAYOUT_DIR) -> list[TruthResult]:
    camera = load_camera(CAMERA_PROFILE)
    K = camera_matrix(camera.width, camera.height, camera.hfov_deg)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)  # LidFinder never closes its layout file
        finder = LidFinder(str(layout_dir / "lid_layout.json"))
    results: list[TruthResult] = []
    for index, pose in enumerate(pose_grid()):
        path = frame_path(Path(frames_dir), index)
        gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise FileNotFoundError(f"[truth_check:check] Missing frame — {{path: {path}}}")
        cam_pos = np.array(pose.camera_pose()[0])
        range_m = float(np.linalg.norm(cam_pos))
        limit_m = _NEAR_LIMIT_M if pose.height_m <= _NEAR_MAX_HEIGHT_M else _FAR_FRACTION * range_m
        found = [r for r in finder.find(gray, K) if r["box"] == BOX]
        if not found:
            results.append(TruthResult(pose, False, None, None, None, range_m, limit_m, False))
            continue
        out = lid_pose(found[0], MOUNT)
        error_m = float(np.linalg.norm(np.array(found[0]["xyz_m"]) - pose.lid_in_camera_m()))
        drone_error_m = float(np.linalg.norm(np.array(out["drone_m"]) - np.array(pose.drone_truth_m())))
        yaw_error = (out["yaw_deg"] - pose.yaw_deg + 180.0) % 360.0 - 180.0
        results.append(TruthResult(pose, True, error_m, drone_error_m, yaw_error, range_m, limit_m, error_m < limit_m))
    return results


def _contact_sheet(frames_dir: Path, results: list[TruthResult], columns: int = 4) -> NDArray[np.uint8]:
    thumbs: list[NDArray[np.uint8]] = []
    for index, r in enumerate(results):
        thumb = cv2.resize(cv2.imread(str(frame_path(frames_dir, index))), (320, 200), interpolation=cv2.INTER_AREA)
        label = f"{r.pose.name} {'ok' if r.passed else 'FAIL'}"
        cv2.putText(thumb, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if r.passed else (0, 0, 255), 1)
        thumbs.append(thumb)
    blank = np.zeros_like(thumbs[0])
    while len(thumbs) % columns:
        thumbs.append(blank)
    rows = [np.hstack(thumbs[i:i + columns]) for i in range(0, len(thumbs), columns)]
    return np.vstack(rows)


def _report(results: list[TruthResult]) -> str:
    lines = ["pose            detected  err_mm  limit_mm  drone_mm  yaw_err  range_m  result"]
    for r in results:
        err = "-" if r.error_m is None else f"{r.error_m * 1e3:.2f}"
        drone = "-" if r.drone_error_m is None else f"{r.drone_error_m * 1e3:.1f}"
        yaw = "-" if r.yaw_error_deg is None else f"{r.yaw_error_deg:+.1f}"
        lines.append(
            f"{r.pose.name:<15} {str(r.detected):<9} {err:>6}  {r.limit_m * 1e3:8.1f}  {drone:>8}  {yaw:>7}  "
            f"{r.range_m:7.3f}  {'PASS' if r.passed else 'FAIL'}"
        )
    return "\n".join(lines)


def _run(port: int, out_dir: Path, layout_dir: Path) -> int:
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    client = RenderClient("127.0.0.1", port, timeout_s=600.0)
    try:
        for index, pose in enumerate(pose_grid()):
            pos, quat = pose.camera_pose()
            frame = client.render(pos, quat, float(index))
            cv2.imwrite(str(frame_path(frames_dir, index)), frame)
    finally:
        client.quit()
    results = check(frames_dir, layout_dir)
    cv2.imwrite(str(out_dir / "contact-sheet.png"), _contact_sheet(frames_dir, results))
    (out_dir / "truth-results.json").write_text(json.dumps([asdict(r) for r in results], indent=1))
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
