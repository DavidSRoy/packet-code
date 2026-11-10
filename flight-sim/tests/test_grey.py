import numpy as np
import pytest

from flightsim.grey import to_grey


def frame(r: int, g: int, b: int) -> np.ndarray:
    return np.full((2, 3, 4), (r, g, b, 255), np.uint8)


def test_srgb_keeps_the_encoded_luma():
    assert (to_grey(frame(128, 128, 128), "srgb") == 128).all()
    assert (to_grey(frame(255, 0, 0), "srgb") == 76).all()  # 0.299 * 255


def test_linear_decodes_before_taking_luma():
    assert (to_grey(frame(0, 0, 0), "linear") == 0).all()
    assert (to_grey(frame(255, 255, 255), "linear") == 255).all()
    assert (to_grey(frame(128, 128, 128), "linear") == 55).all()  # 0.2158 linear
    assert (to_grey(frame(188, 188, 188), "linear") == 128).all()  # 0.5029 linear
    assert (to_grey(frame(255, 0, 0), "linear") == 76).all()


def test_output_is_2d_uint8_and_alpha_is_ignored():
    rgba = frame(200, 200, 200)
    rgba[..., 3] = 0
    out = to_grey(rgba, "linear")
    assert out.shape == (2, 3) and out.dtype == np.uint8


def test_rejects_a_grey_frame():
    with pytest.raises(ValueError, match=r"\[grey:to_grey\]"):
        to_grey(np.zeros((2, 3), np.uint8), "linear")
