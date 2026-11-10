import json
from pathlib import Path

import pytest

from flightsim.profiles import load_camera, load_compute

PROFILES = Path(__file__).resolve().parents[1] / "profiles"
CAMERA_NUMERIC = {"width", "height", "hfov_deg", "tone"}
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
    assert dict(cam.provenance) == {"width": "datasheet", "height": "datasheet", "hfov_deg": "estimate", "tone": "estimate"}
    assert dict(comp.provenance) == {
        "rate_hz": "measured",
        "detect_s": "measured",
        "exposure_to_readout_s": "estimate",
        "detect_jitter_s": "estimate",
        "link_s": "estimate",
        "detect_scale": "estimate",
    }
    assert set(cam.sources) == CAMERA_NUMERIC
    assert set(comp.sources) == COMPUTE_NUMERIC
    assert (cam.width, cam.height, cam.hfov_deg, cam.mono, cam.shutter) == (1280, 800, 70.0, True, "global")
    assert cam.tone == "linear"
    assert comp.rate_hz == 10.0 and comp.detect_scale == 0.4


def test_profile_unknown_provenance_raises(tmp_path: Path):
    data = json.loads((PROFILES / "compute" / "pi-zero-2w.json").read_text())
    data["provenance"]["rate_hz"] = "guess"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=r"\[profiles:load_compute\]"):
        load_compute(bad)


def test_missing_key_raises_with_context(tmp_path: Path):
    for fn, src, loader in (
        ("load_camera", PROFILES / "cameras" / "ov9281.json", load_camera),
        ("load_compute", PROFILES / "compute" / "pi-zero-2w.json", load_compute),
    ):
        data = json.loads(src.read_text())
        del data["name"]
        bad = tmp_path / f"{fn}.json"
        bad.write_text(json.dumps(data))
        with pytest.raises(ValueError, match=rf"\[profiles:{fn}\] Missing key"):
            loader(bad)


def test_unknown_tone_raises(tmp_path: Path):
    data = json.loads((PROFILES / "cameras" / "ov9281.json").read_text())
    data["tone"] = "gamma22"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=r"\[profiles:load_camera\] Unknown tone"):
        load_camera(bad)
