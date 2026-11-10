import dataclasses
import json
from pathlib import Path

import pytest

from flightsim.profiles import CameraProfile, ComputeProfile, load_camera, load_compute

PROFILES = Path(__file__).resolve().parents[1] / "profiles"
CAMERA_NUMERIC = {"width", "height", "hfov_deg"}
COMPUTE_NUMERIC = {
    "rate_hz",
    "exposure_to_readout_s",
    "detect_s",
    "detect_jitter_s",
    "link_s",
    "detect_scale",
}


def test_every_profile_field_has_provenance():
    cam = load_camera(PROFILES / "cameras" / "ov9281.json")
    comp = load_compute(PROFILES / "compute" / "pi-zero-2w.json")
    assert set(cam.provenance) == CAMERA_NUMERIC
    assert set(comp.provenance) == COMPUTE_NUMERIC
    assert cam.provenance and all(v == "datasheet" for v in cam.provenance.values())
    assert all(v == "measured" for v in comp.provenance.values())
    assert (cam.width, cam.height, cam.hfov_deg, cam.mono, cam.shutter) == (1280, 800, 70.0, True, "global")
    assert comp.rate_hz == 10.0 and comp.detect_scale == 0.4
    assert dataclasses.is_dataclass(CameraProfile) and dataclasses.is_dataclass(ComputeProfile)


def test_profile_unknown_provenance_raises(tmp_path: Path):
    data = json.loads((PROFILES / "compute" / "pi-zero-2w.json").read_text())
    data["provenance"]["rate_hz"] = "guess"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=r"\[profiles:load_compute\]"):
        load_compute(bad)
