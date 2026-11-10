import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

Provenance = Literal["measured", "datasheet", "estimate"]
_VALID = set(get_args(Provenance))


@dataclass(frozen=True)
class CameraProfile:
    name: str
    width: int
    height: int
    hfov_deg: float
    mono: bool
    shutter: str
    provenance: Mapping[str, Provenance]
    sources: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ComputeProfile:
    name: str
    rate_hz: float
    exposure_to_readout_s: float
    detect_s: float
    detect_jitter_s: float
    link_s: float
    detect_scale: float
    provenance: Mapping[str, Provenance]
    sources: Mapping[str, str] = field(default_factory=dict)


def _provenance(fn: str, path: Path, raw: Mapping[str, str]) -> dict[str, Provenance]:
    out: dict[str, Provenance] = {}
    for key, value in raw.items():
        if value == "measured" or value == "datasheet" or value == "estimate":
            out[key] = value
        else:
            raise ValueError(
                f"[profiles:{fn}] Unknown provenance — {{path: {str(path)!r}, field: {key!r}, "
                f"value: {value!r}, allowed: {sorted(_VALID)}}}"
            )
    return out


def _missing(fn: str, path: Path, exc: KeyError) -> ValueError:
    return ValueError(f"[profiles:{fn}] Missing key — {{path: {str(path)!r}, key: {exc.args[0]!r}}}")


def load_camera(path: Path) -> CameraProfile:
    d = json.loads(Path(path).read_text())
    try:
        return CameraProfile(
            name=str(d["name"]),
            width=int(d["width"]),
            height=int(d["height"]),
            hfov_deg=float(d["hfov_deg"]),
            mono=bool(d["mono"]),
            shutter=str(d["shutter"]),
            provenance=_provenance("load_camera", path, d["provenance"]),
            sources=dict(d.get("sources", {})),
        )
    except KeyError as exc:
        raise _missing("load_camera", path, exc) from exc


def load_compute(path: Path) -> ComputeProfile:
    d = json.loads(Path(path).read_text())
    try:
        return ComputeProfile(
            name=str(d["name"]),
            rate_hz=float(d["rate_hz"]),
            exposure_to_readout_s=float(d["exposure_to_readout_s"]),
            detect_s=float(d["detect_s"]),
            detect_jitter_s=float(d["detect_jitter_s"]),
            link_s=float(d["link_s"]),
            detect_scale=float(d["detect_scale"]),
            provenance=_provenance("load_compute", path, d["provenance"]),
            sources=dict(d.get("sources", {})),
        )
    except KeyError as exc:
        raise _missing("load_compute", path, exc) from exc
