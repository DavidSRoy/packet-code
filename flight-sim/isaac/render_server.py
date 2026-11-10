"""Isaac Sim render server: builds the lid scene and answers pose requests with grey frames.

Run with Isaac's own Python (python.sh). Only numpy is needed beyond Isaac itself.
"""
import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the flightsim package; scene.py sits beside this file

import numpy as np  # noqa: E402
from numpy.typing import NDArray  # noqa: E402

from flightsim.frames import Quat, Vec3  # noqa: E402
from flightsim.profiles import load_camera  # noqa: E402
from flightsim.render_link import serve  # noqa: E402

_RT_SUBFRAMES = 4
_MAX_STEPS = 40  # steps before the first annotator data shows up


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=Path, required=True)
    parser.add_argument("--lid-png", type=Path, required=True)
    parser.add_argument("--lid-size-m", type=float, nargs=2, required=True, metavar=("W", "H"))
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--sun-elevation-deg", type=float, default=60.0)
    return parser.parse_args()


def _to_grey(rgba: NDArray[np.uint8]) -> NDArray[np.uint8]:
    rgb = rgba[..., :3].astype(np.float32)
    return np.rint(rgb @ np.array([0.299, 0.587, 0.114], np.float32)).astype(np.uint8)


def main() -> None:
    args = _parse()
    camera = load_camera(args.camera)

    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True, "width": camera.width, "height": camera.height})
    try:
        # Imports that need the Kit runtime must come after SimulationApp starts.
        import omni.replicator.core as rep
        import omni.usd
        from scene import build_scene

        omni.usd.get_context().new_stage()
        rig = build_scene(
            omni.usd.get_context().get_stage(), camera, args.lid_png.resolve(),
            (args.lid_size_m[0], args.lid_size_m[1]), args.sun_elevation_deg,
        )
        product = rep.create.render_product("/World/Rig/Camera", (camera.width, camera.height))
        rgb = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb.attach([product])

        def capture() -> NDArray[np.uint8]:
            for _ in range(_MAX_STEPS):
                rep.orchestrator.step(rt_subframes=_RT_SUBFRAMES)
                data = rgb.get_data()
                if data is not None and data.size > 0:
                    frame = np.asarray(data)
                    if frame.shape[:2] != (camera.height, camera.width):
                        raise RuntimeError(
                            f"[render_server:capture] Unexpected frame shape — {{shape: {frame.shape}, "
                            f"expected: {(camera.height, camera.width)}}}"
                        )
                    return _to_grey(frame)
            raise RuntimeError(f"[render_server:capture] No frame — {{steps: {_MAX_STEPS}}}")

        def render_fn(pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]:
            try:
                rig.set_pose(pos, quat)
                return capture()
            except Exception:
                traceback.print_exc()  # serve() only prints ValueError text and drops the client
                raise

        for _ in range(2):
            capture()
        print("[render_server] ready", flush=True)
        serve(render_fn, args.port, args.ready_file)
    finally:
        app.close()


main()
