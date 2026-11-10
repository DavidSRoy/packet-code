"""What sits between the camera and the lid, in the camera's own frame.

Pure Python so both the Isaac scene and the tests can use it. Dimensions are copied from
backend/tools/sim/lid_camera_sim.py (drone frame: x nose, y left, z up, mm); a test pins them to it.
"""
from dataclasses import dataclass

import numpy as np

# Oracle mount D: lens centre in the drone frame, mm (70 ahead, 95 left, 100 below).
CAMERA_MOUNT_MM = (70.0, 95.0, -100.0)
LID_TOP_Z_MM = -158.1
LID_SIZE_MM = (225.6, 206.4)
LEG_R_MM = 8.0
LENS_CLEARANCE_MM = 3.0  # parts are cut off this far below the lens

# (xmin, xmax, ymin, ymax, zmin, zmax)
Bounds = tuple[float, float, float, float, float, float]
BOXES_MM: dict[str, Bounds] = {
    "RP-013 drive housing": (-100.0, 100.0, -47.0, 47.0, -147.3, -92.0),
    "RP-019 jaw 1": (-126.8, 65.0, -60.0, 34.9, -170.9, -131.9),
    "RP-019 jaw 2": (-65.0, 126.8, -34.9, 60.0, -170.9, -131.9),
    "FR-004 battery plate": (-64.0, 64.0, -60.0, 60.0, -92.0, -90.0),
}


@dataclass(frozen=True)
class Cuboid:
    name: str
    centre_m: tuple[float, float, float]
    size_m: tuple[float, float, float]


def drone_bounds_mm(mount_mm: tuple[float, float, float] = CAMERA_MOUNT_MM) -> dict[str, Bounds]:
    """Occluders in the drone frame, cut off below the lens as the oracle does."""
    limit = mount_mm[2] - LENS_CLEARANCE_MM
    out: dict[str, Bounds] = {}
    for name, (x0, x1, y0, y1, z0, z1) in BOXES_MM.items():
        top = min(z1, limit)
        if z0 < top:
            out[name] = (x0, x1, y0, y1, z0, top)
    for side, sgn in (("left", 1.0), ("right", -1.0)):
        for z in np.arange(-4.1, LID_TOP_Z_MM - 40.0, -6.0):
            if z > limit:
                continue
            yc = sgn * (64.1 + 0.317 * (-4.1 - float(z)))
            out[f"leg {side} {len(out)}"] = (
                -LEG_R_MM, LEG_R_MM, yc - LEG_R_MM, yc + LEG_R_MM, float(z) - 6.5, float(z),
            )
    return out


def camera_frame_cuboids(mount_mm: tuple[float, float, float] = CAMERA_MOUNT_MM) -> list[Cuboid]:
    """The same occluders as axis-aligned cuboids in metres in the USD camera frame
    (x image right = drone right, y image up = nose, z toward the viewer = drone up), origin at the lens."""
    mx, my, mz = mount_mm
    cuboids: list[Cuboid] = []
    for name, (x0, x1, y0, y1, z0, z1) in drone_bounds_mm(mount_mm).items():
        lo = (my - y1, x0 - mx, z0 - mz)
        hi = (my - y0, x1 - mx, z1 - mz)
        centre = tuple((a + b) / 2000.0 for a, b in zip(lo, hi))
        size = tuple((b - a) / 1000.0 for a, b in zip(lo, hi))
        cuboids.append(Cuboid(name, (centre[0], centre[1], centre[2]), (size[0], size[1], size[2])))
    return cuboids
