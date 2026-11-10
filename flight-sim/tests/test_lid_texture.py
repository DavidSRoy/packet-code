import warnings
from pathlib import Path

import cv2
import numpy as np

from flightsim.lid_texture import write_lid_texture
from lid_tags import LidFinder, camera_matrix

LAYOUT_DIR = Path(__file__).resolve().parents[2] / "backend" / "companion" / "stickers_218x200"
PX_PER_MM = 6.0


def test_texture_decodes_head_on_at_half_a_metre(tmp_path):
    png = tmp_path / "lid.png"
    w_m, h_m = write_lid_texture(LAYOUT_DIR, 1, png, PX_PER_MM)
    assert (w_m, h_m) == (0.218, 0.200)
    tex = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    # Camera 0.5 m above the sticker centre looking down: image right = lid +x, image down = lid -y.
    K = camera_matrix(1280, 800, 70.0)
    z_m = 0.5
    tex_to_lid = np.array([[1 / PX_PER_MM, 0, -w_m * 500], [0, -1 / PX_PER_MM, h_m * 500], [0, 0, 1.0]])
    lid_to_img = K @ np.array([[1e-3 / z_m, 0, 0], [0, -1e-3 / z_m, 0], [0, 0, 1.0]])
    frame = cv2.warpPerspective(tex, lid_to_img @ tex_to_lid, (1280, 800), flags=cv2.INTER_AREA, borderValue=95)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)  # LidFinder never closes its layout file
        found = LidFinder(str(LAYOUT_DIR / "lid_layout.json")).find(frame, K)
    assert [r["box"] for r in found] == [1]
    assert np.linalg.norm(np.array(found[0]["xyz_m"]) - [0, 0, z_m]) < 0.005
