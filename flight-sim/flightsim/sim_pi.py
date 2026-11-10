"""The hover simulator's camera, driven by rendered frames instead of a noise model.

RenderedCamera replaces physics.Camera.measure: at each exposure it renders the scene at the true
camera pose, runs the drone's own detector (LidFinder, then imu_fix and lid_pose from
backend/companion) on the frame, and hands the pose it found to physics.Camera's send path. A frame
with no detection sends nothing. The frame timing comes from the ComputeProfile instead of
model.json's camera block, so a slower computer or a worse camera gives a worse hover.

Runnable like e2e/fake_pi.py; the arguments it does not know go to physics.main():

  python sim_pi.py --render-ready-file R --camera cam.json --compute pc.json --layout lid_layout.json \\
      [--record-dir D] <physics.py arguments>
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

import physics  # noqa: E402
from imu_pose import ImuPose  # noqa: E402
from lid_pose import Mount, imu_fix, lid_pose  # noqa: E402
from lid_tags import LidFinder, camera_matrix  # noqa: E402

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
        self.rest_z = float(drone.p[2])                          # NED z of the drone resting on the box
        self.frame = 0

    def measure(
        self, t_exp: float, t_cap: float, p_true: NDArray[np.float64], q_true: NDArray[np.float64]
    ) -> tuple[NDArray[np.float64], float] | None:
        lid = np.array([0.0, 0.0, -self.C["lid_height_above_ground"]])
        pos, quat = camera_pose_world(
            tuple(float(v) for v in p_true - lid), tuple(float(v) for v in q_true),
            tuple(float(v) for v in self.C["cam_pos"]),
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
        if found:
            # ponytail: true attitude with lag, not the FC's estimate; switch to ATTITUDE from the MAVLink link if estimator error matters
            roll, pitch, att_yaw = physics.quat_to_euler(self.q_at(t_cap - self.C["tilt_attitude_lag_s"]))
            on_box = bool(self.rest_z - p_true[2] <= physics.LIFTOFF_H)    # still and disarmed
            fix = imu_fix(found[0], (roll, pitch, att_yaw), K, self.imu, self.mount, zero=on_box, last=self.last)
            drone_m = lid_pose(fix, self.mount)
            x, y, z = drone_m["drone_m"]
            estimate = lid + np.array([x, -y, -z])             # cam_stream.vision() sends x, -y, -z of drone_m
            yaw = -math.radians(drone_m["yaw_deg"])            # and the nose direction clockwise
            tags = len(drone_m["tags"])
            outlines = tuple(tuple((px / scale, py / scale) for px, py in o["px"]) for o in drone_m["outlines"])
        if self.recorder is not None:
            est = None if estimate is None else (float(estimate[0]), float(estimate[1]), float(estimate[2]))
            truth = (float(p_true[0]), float(p_true[1]), float(p_true[2]))
            self.recorder.add(frame, FrameRow(self.frame, t_exp, int(estimate is not None), tags, est, truth, outlines))
        self.frame += 1
        return None if estimate is None else (estimate, yaw)


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
    recorder = Recorder(args.record_dir, compute.rate_hz) if args.record_dir else None
    finder = LidFinder(str(args.layout))
    camera = load_camera(args.camera)

    def make(C: Mapping[str, object], rng: np.random.Generator, drone: physics.Drone) -> RenderedCamera:
        return RenderedCamera(C, rng, drone, renderer=client, finder=finder, camera=camera, compute=compute,
                              recorder=recorder)

    physics.Camera = make
    try:
        physics.main()
    finally:
        if recorder is not None:
            recorder.close()
        client.quit()


if __name__ == "__main__":
    main()
