import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "backend"

for _dir in (
    _BACKEND,
    _BACKEND / "companion",
    _BACKEND / "tools" / "sim",
    _BACKEND / "tools" / "sim" / "hover",
):
    if str(_dir) not in sys.path:
        sys.path.append(str(_dir))

import warnings  # noqa: E402

import pytest  # noqa: E402

import lid_stickers as LS  # noqa: E402
from lid_camera_sim import Scene  # noqa: E402
from oracle_setup import CAM_MOUNT_MM, LAYOUT, STICKER  # noqa: E402


@pytest.fixture(scope="module")
def scene():
    LS.configure(**STICKER)
    with warnings.catch_warnings():
        # LidFinder (backend/companion/lid_tags.py) never closes the layout file it reads; not ours to change.
        warnings.simplefilter("ignore", ResourceWarning)
        return Scene("C920", CAM_MOUNT_MM, 0.0, LAYOUT)
