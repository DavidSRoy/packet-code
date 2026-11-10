"""Runs physics.main() with a camera whose first step blocks like a 1.5 s render (see test_lockstep.py)."""
import sys
import time
from pathlib import Path

_HOVER = Path(__file__).resolve().parents[2] / "backend" / "tools" / "sim" / "hover"
sys.path.insert(0, str(_HOVER))

import physics  # noqa: E402


class SlowCamera(physics.Camera):
    slept = False

    def connect(self, url: str) -> None:
        return None

    def step(self, t: float) -> None:
        if not SlowCamera.slept:
            SlowCamera.slept = True
            time.sleep(1.5)


physics.Camera = SlowCamera
physics.main()
