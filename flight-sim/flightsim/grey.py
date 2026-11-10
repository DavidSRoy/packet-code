"""Turn a rendered RGBA frame into the 8-bit grey frame the detector sees."""
import numpy as np
from numpy.typing import NDArray

from flightsim.profiles import Tone

_LUMA = np.array([0.299, 0.587, 0.114])


def to_grey(rgba: NDArray[np.uint8], tone: Tone) -> NDArray[np.uint8]:
    """rgba holds sRGB-encoded 8-bit values (the renderer's LDR output).

    "srgb": luma of the encoded values as they are. "linear": decode each channel to linear light,
    take the luma, and store it as 8-bit linear, like a raw mono sensor.
    """
    if rgba.ndim != 3 or rgba.shape[2] < 3 or rgba.dtype != np.uint8:
        raise ValueError(
            f"[grey:to_grey] Expected an HxWx3+ uint8 frame — {{shape: {rgba.shape}, dtype: {rgba.dtype}}}"
        )
    encoded = rgba[..., :3].astype(np.float64) / 255.0
    if tone == "srgb":
        return np.rint(255.0 * (encoded @ _LUMA)).astype(np.uint8)
    linear = np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)
    return np.rint(255.0 * (linear @ _LUMA)).astype(np.uint8)
