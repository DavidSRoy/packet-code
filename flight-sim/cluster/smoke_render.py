"""Isaac Sim standalone smoke test: ground plane, one cube, one light, one top-down camera."""
import subprocess
import sys
from pathlib import Path

from isaacsim import SimulationApp

WIDTH, HEIGHT = 1280, 800
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "out") / "smoke.png"
WARMUP_STEPS = 40

simulation_app = SimulationApp({"headless": True, "width": WIDTH, "height": HEIGHT})

# Imports that need the Kit runtime must come after SimulationApp starts.
import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, Usd, UsdGeom, UsdLux  # noqa: E402


def _isaac_version() -> str:
    from isaacsim.core.version import get_version

    return "/".join(str(part) for part in get_version())


def _gpu_name() -> str:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _box(stage: Usd.Stage, path: str, center: Gf.Vec3d, size: Gf.Vec3d, color: Gf.Vec3f) -> None:
    cube = UsdGeom.Cube.Define(stage, path)
    cube.GetSizeAttr().Set(1.0)
    cube.AddTranslateOp().Set(center)
    cube.AddScaleOp().Set(size)
    cube.GetDisplayColorAttr().Set([color])


def main() -> None:
    print(f"[smoke] isaac version: {_isaac_version()}", flush=True)
    print(f"[smoke] gpu: {_gpu_name()}", flush=True)

    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.Xform.Define(stage, "/World")

    _box(stage, "/World/Ground", Gf.Vec3d(0, 0, -0.01), Gf.Vec3d(40, 40, 0.02), Gf.Vec3f(0.35, 0.55, 0.3))
    _box(stage, "/World/Cube", Gf.Vec3d(0, 0, 0.25), Gf.Vec3d(0.5, 0.5, 0.5), Gf.Vec3f(0.85, 0.15, 0.1))

    light = UsdLux.DistantLight.Define(stage, "/World/Sun")
    light.CreateIntensityAttr(3000.0)
    UsdGeom.Xformable(light).AddRotateXYZOp().Set(Gf.Vec3f(-50, 0, 30))

    camera = UsdGeom.Camera.Define(stage, "/World/Camera")
    # A USD camera looks down its local -Z, so with no rotation it faces straight down.
    camera.AddTranslateOp().Set(Gf.Vec3d(0, 0, 2.0))

    product = rep.create.render_product("/World/Camera", (WIDTH, HEIGHT))
    rgb = rep.AnnotatorRegistry.get_annotator("rgb")
    rgb.attach([product])

    data = None
    for step in range(WARMUP_STEPS):
        rep.orchestrator.step(rt_subframes=4)
        data = rgb.get_data()
        if data is not None and data.size > 0 and step >= 5:
            print(f"[smoke] frame captured on step {step}", flush=True)
            break
    if data is None or data.size == 0:
        raise RuntimeError(f"[smoke:main] No frame after {WARMUP_STEPS} steps — {{shape: {None if data is None else data.shape}}}")

    frame = np.asarray(data)[..., :3].astype(np.uint8)
    if frame.shape != (HEIGHT, WIDTH, 3):
        raise RuntimeError(f"[smoke:main] Unexpected frame shape — {{shape: {frame.shape}}}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(frame).save(OUT)
    mean, std = float(frame.mean()), float(frame.std())
    print(f"[smoke] wrote {OUT} mean={mean:.1f} std={std:.1f}", flush=True)
    if not 20.0 <= mean <= 235.0 or std <= 10.0:
        raise RuntimeError(
            f"[smoke:main] Frame looks blank or saturated — {{mean: {mean:.1f}, std: {std:.1f}, "
            "expected_mean: 20..235, expected_std: >10}"
        )


try:
    main()
finally:
    simulation_app.close()
