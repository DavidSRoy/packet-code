"""Shared setup of the lid_camera_sim oracle scene (see test_lid_pose.py for why this mount)."""
from pathlib import Path

from lid_pose import Mount

LAYOUT = str(Path(__file__).resolve().parents[2] / "backend" / "companion" / "stickers_218x200" / "lid_layout.json")

# The oracle's defaults (lid_camera_sim.py main): 218x200 sticker, extra small tags.
STICKER = dict(
    w=218.0, h=200.0, big_cell=18.0, small_cell=3.75, inset=5.0,
    extra=[(-44.5, 80), (0, 80), (44.5, 80), (-44.5, -80), (0, -80), (44.5, -80),
           (-89, 36), (-89, -36), (89, 36), (89, -36)],
)

# Oracle mount D (70 mm ahead, 95 mm left, 100 mm below): the default mount A looks at the jaws
# from 0.5 m and sees almost no lid. 95 mm left is right_m = -0.095.
CAM_MOUNT_MM = (70.0, 95.0, -100.0)
MOUNT = Mount(fwd_m=0.070, right_m=-0.095, down_m=0.100, rot_deg=0.0)
