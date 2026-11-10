"""The hover simulator's camera, driven by rendered frames instead of a noise model.

RenderedCamera replaces physics.Camera.measure: at each exposure it renders the scene at the true
camera pose, runs the drone's own detector (LidFinder, then imu_fix and lid_pose from
backend/companion) on the frame, and hands the pose it found to physics.Camera's send path. A frame
with no detection sends nothing. The frame timing comes from the ComputeProfile instead of
model.json's camera block, so a slower computer or a worse camera gives a worse hover.

Runnable like e2e/fake_pi.py; the arguments it does not know go to physics.main():

  python sim_pi.py --render-ready-file R --camera cam.json --compute pc.json --layout lid_layout.json \\
      [--record-dir D] <physics.py arguments>

rate_hz in the ComputeProfile must be the effective detected rate: frames are exposed at that rate
and never dropped because detection is slow.

The sticker centre is at the lens' resting position (main() passes model.json cam_pos x, y as lid_xy), with
lid +x pointing north; the drone starts at the physics origin. Estimates are world positions, so the hover
holds the start point wherever the sticker is.

The estimate (and the sent position) is the point the Pi believes it is reporting: the drone centre
as seen through the Pi's mount belief (model.json cam_pos + pi_cam_pos_err). frames.csv truth is the
CG. So est_z - true_z carries the known mount-belief offset, and err_xy_mm picks up a term that grows
with tilt.

As in cam_stream.py: zeroing the IMU pose (imu_fix zero=True) is allowed only until the first
non-zero motor command, then latched off; a frame whose imu_fix/lid_pose raises is dropped and
printed to stderr; VISION_SPEED goes out only when this frame and the previous sent frame both have
pose "imu" (a tag-only frame resets the previous sample).
"""
import argparse
import math
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from numpy.typing import NDArray

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
for _dir in (_BACKEND / "companion", _BACKEND / "tools" / "sim" / "hover"):
    if str(_dir) not in sys.path:
        sys.path.append(str(_dir))

import physics  # type: ignore[import-not-found]  # noqa: E402
from imu_pose import ImuPose  # type: ignore[import-not-found]  # noqa: E402
from lid_pose import Mount, imu_fix, lid_pose  # type: ignore[import-not-found]  # noqa: E402
from lid_tags import LidFinder, camera_matrix  # type: ignore[import-not-found]  # noqa: E402

from flightsim.frames import Quat, Vec3, camera_pose_world  # noqa: E402
from flightsim.profiles import CameraProfile, ComputeProfile, load_camera, load_compute  # noqa: E402
from flightsim.recorder import FrameRow, Recorder  # noqa: E402
from flightsim.render_link import RenderClient  # noqa: E402


class Renderer(Protocol):
    def render(self, pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]: ...


class RenderedCamera(physics.Camera):
    def __init__(
        self,
        C: Mapping[str, object],
        rng: np.random.Generator,
        drone: physics.Drone,
        *,
        renderer: Renderer,
        finder: LidFinder,
        camera: CameraProfile,
        compute: ComputeProfile,
        recorder: Recorder | None = None,
        lid_xy: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        timing = {
            "rate_hz": compute.rate_hz,
            "exposure_to_readout_s": compute.exposure_to_readout_s,
            "detect_s": compute.detect_s,
            "detect_jitter_s": compute.detect_jitter_s,
            "link_s": compute.link_s,
        }
        super().__init__(dict(C, **timing), rng, drone)
        self.renderer, self.finder, self.camera, self.compute, self.recorder = renderer, finder, camera, compute, recorder
        cam_pos = np.array(self.C["cam_pos"])
        self.mount = Mount(*(cam_pos + np.array(self.C["pi_cam_pos_err"])).tolist(), 0.0)   # the Pi's belief
        self.imu = ImuPose(self.mount.rot_deg)
        self.last: dict[int, tuple[float, float, float]] = {}   # imu_fix's stillness state, as in cam_stream.py
        self.armed = False                                       # latched at the first non-zero motor command
        self.prev_imu = False                                    # the previous sent frame had pose "imu"
        self.frame = 0
        self.lid = np.array([lid_xy[0], lid_xy[1], -float(self.C["lid_height_above_ground"])])   # sticker centre, world NED

    def step(self, t: float) -> None:
        if not self.armed:
            self.armed = any(bool(np.any(act > 0.0)) for _, act in self.d.cmd_hist)
        super().step(t)

    def measure(
        self, t_exp: float, t_cap: float, p_true: NDArray[np.float64], q_true: NDArray[np.float64]
    ) -> tuple[NDArray[np.float64], float] | None:
        lid = self.lid
        rel = p_true - lid
        cam_pos = self.C["cam_pos"]
        pos, quat = camera_pose_world(
            (float(rel[0]), float(rel[1]), float(rel[2])),
            (float(q_true[0]), float(q_true[1]), float(q_true[2]), float(q_true[3])),
            (float(cam_pos[0]), float(cam_pos[1]), float(cam_pos[2])),
        )
        frame = self.renderer.render(pos, quat, t_exp)
        if frame.shape != (self.camera.height, self.camera.width):
            raise ValueError(
                f"[sim_pi:measure] Rendered frame does not match the camera profile — "
                f"{{got: {frame.shape}, camera: {self.camera.name!r}, "
                f"expected: {(self.camera.height, self.camera.width)}}}"
            )
        scale = self.compute.detect_scale
        gray = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1.0 else frame
        K = camera_matrix(gray.shape[1], gray.shape[0], self.camera.hfov_deg)
        found = self.finder.find(gray, K)
        estimate = None
        yaw = 0.0
        outlines: tuple[tuple[tuple[float, float], ...], ...] = ()
        tags = 0
        is_imu = False
        if found:
            # ponytail: true attitude with lag, not the FC's estimate; switch to ATTITUDE from the MAVLink link if estimator error matters
            roll, pitch, att_yaw = physics.quat_to_euler(self.q_at(t_cap - self.C["tilt_attitude_lag_s"]))
            try:
                fix = imu_fix(found[0], (roll, pitch, att_yaw), K, self.imu, self.mount, zero=not self.armed,
                              last=self.last)
                drone_m = lid_pose(fix, self.mount)
            except (np.linalg.LinAlgError, cv2.error, ValueError) as exc:
                print(f"[sim_pi:measure] Frame dropped — {{frame: {self.frame}, t_exp: {t_exp:.3f}, "
                      f"error: {type(exc).__name__}: {exc}}}", file=sys.stderr)
            else:
                x, y, z = drone_m["drone_m"]
                estimate = lid + np.array([x, -y, -z])         # cam_stream.vision() sends x, -y, -z of drone_m
                yaw = -math.radians(drone_m["yaw_deg"])        # and the nose direction clockwise
                tags = len(drone_m["tags"])
                is_imu = drone_m["pose"] == "imu"
                outlines = tuple(tuple((px / scale, py / scale) for px, py in o["px"]) for o in drone_m["outlines"])
        if self.recorder is not None:
            est = None if estimate is None else (float(estimate[0]), float(estimate[1]), float(estimate[2]))
            truth = (float(p_true[0]), float(p_true[1]), float(p_true[2]))
            self.recorder.add(frame, FrameRow(self.frame, t_exp, int(estimate is not None), tags, est, truth, outlines))
        self.frame += 1
        if estimate is None:
            return None
        if not (is_imu and self.prev_imu):
            self.prev = None                 # physics.Camera then sends no VISION_SPEED for this frame
        self.prev_imu = is_imu
        return estimate, yaw


def _wait_for_port(ready_file: Path, timeout_s: float = 600.0) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if ready_file.exists() and ready_file.read_text().strip():
            return int(ready_file.read_text())
        time.sleep(0.5)
    raise TimeoutError(f"[sim_pi:wait_for_port] Renderer never became ready — {{ready_file: {str(ready_file)!r}}}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--render-ready-file", type=Path, required=True)
    ap.add_argument("--camera", type=Path, required=True)
    ap.add_argument("--compute", type=Path, required=True)
    ap.add_argument("--layout", type=Path, required=True)
    ap.add_argument("--record-dir", type=Path)
    args, rest = ap.parse_known_args()
    sys.argv = [sys.argv[0], *rest]

    compute = load_compute(args.compute)
    client = RenderClient("127.0.0.1", _wait_for_port(args.render_ready_file))
    recorder: Recorder | None = None
    try:
        recorder = Recorder(args.record_dir, compute.rate_hz) if args.record_dir else None
        finder = LidFinder(str(args.layout))
        camera = load_camera(args.camera)

        def make(C: Mapping[str, object], rng: np.random.Generator, drone: physics.Drone) -> RenderedCamera:
            # The sticker centre goes under the lens at rest. Under the drone centre the gripper jaws, which
            # reach from behind the lens to its nose side, would cover every ray that reaches the lid.
            cam_pos = C["cam_pos"]
            return RenderedCamera(C, rng, drone, renderer=client, finder=finder, camera=camera, compute=compute,
                                  recorder=recorder, lid_xy=(float(cam_pos[0]), float(cam_pos[1])))

        physics.Camera = make
        physics.main()
    finally:
        if recorder is not None:
            recorder.close()
        client.quit()


if __name__ == "__main__":
    main()
