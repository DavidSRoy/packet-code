"""The lid sticker as an image, for the Isaac scene."""
import json
import sys
from pathlib import Path

import cv2

import lid_stickers as LS
from lid_camera_sim import sticker_raster

# Tag sizes and extra small tags of the 218x200 sticker (lid_camera_sim.py main defaults).
_TAGS = dict(
    big_cell=18.0, small_cell=3.75, inset=5.0,
    extra=[(-44.5, 80), (0, 80), (44.5, 80), (-44.5, -80), (0, -80), (44.5, -80),
           (-89, 36), (-89, -36), (89, 36), (89, -36)],
)


def write_lid_texture(
    layout_dir: Path, box: int, out_png: Path, px_per_mm: float = 6.0
) -> tuple[float, float]:
    """Write the sticker image (top row = sticker top) and return its width, height in metres."""
    layout = Path(layout_dir) / "lid_layout.json"
    if not layout.is_file():
        raise FileNotFoundError(f"[lid_texture:write_lid_texture] No layout file — {{path: {layout}}}")
    w_mm, h_mm = json.loads(layout.read_text())["sticker_mm"]
    LS.configure(w=w_mm, h=h_mm, **_TAGS)
    LS.CURRENT_BOX = box
    # Three channels: every texture loader reads those the same way.
    image = cv2.cvtColor(sticker_raster(px_per_mm), cv2.COLOR_GRAY2BGR)
    if not cv2.imwrite(str(out_png), image):
        raise OSError(f"[lid_texture:write_lid_texture] Could not write the image — {{path: {out_png}}}")
    return w_mm / 1000.0, h_mm / 1000.0


if __name__ == "__main__":
    # python -m flightsim.lid_texture <layout_dir> <box> <out.png>  ->  prints "width_m height_m"
    width_m, height_m = write_lid_texture(Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3]))
    print(width_m, height_m)
