"""Compare two hover result folders: position error and detection rate."""
import csv
import json
from pathlib import Path

HOLD_MARGIN_M = 0.05    # a frame is in the hold when it is within this of the target height


def _read(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"[compare:summarize] Missing result file — {{path: {str(path)!r}}}")
    return path.read_text()


def _number(raw: object, key: str, folder: Path) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    raise ValueError(f"[compare:summarize] Not a number — {{folder: {str(folder)!r}, key: {key!r}, value: {raw!r}}}")


def _load(folder: Path) -> tuple[dict[str, float], str, bool]:
    """Stats, the run's status, and whether the detection rate used the hold window."""
    result = json.loads(_read(folder / "result.json"))
    rows = list(csv.DictReader(_read(folder / "frames.csv").splitlines()))
    try:
        score = result.get("score") or {}
        nan = float("nan")
        rms = _number(score["xy_rms_mm"], "xy_rms_mm", folder) if "xy_rms_mm" in score else nan
        peak = _number(score["xy_max_mm"], "xy_max_mm", folder) if "xy_max_mm" in score else nan
        status = str(result["status"])
        start = result.get("events", {}).get("start_fc")
        in_hold = False
        if start:
            floor = _number(start[2], "start_fc.z", folder) - _number(result["height"], "height", folder) + HOLD_MARGIN_M
            hold = [r for r in rows if float(r["true_z"]) < floor]
            if hold:
                rows, in_hold = hold, True
        if not rows:
            raise ValueError(f"[compare:summarize] No frames to rate — {{folder: {str(folder)!r}}}")
        rate = sum(int(r["detected"]) for r in rows) / len(rows)
    except KeyError as exc:
        raise ValueError(f"[compare:summarize] Missing key — {{folder: {str(folder)!r}, key: {exc.args[0]!r}}}") from exc
    return {"xy_rms_mm": rms, "xy_max_mm": peak, "detection_rate": rate}, status, in_hold


def summarize(folder: Path) -> dict[str, float]:
    """xy_rms_mm, xy_max_mm (nan when the run has no score, e.g. the flight controller disarmed) and
    detection_rate over the hold window, or over every frame when no frame reached the hold."""
    return _load(folder)[0]


def describe(folder: Path) -> tuple[str, bool]:
    """The run's status and whether its detection rate is over the hold window (False: all frames)."""
    _, status, in_hold = _load(folder)
    return status, in_hold


def compare(a: Path, b: Path) -> dict[str, float]:
    """Differences, b minus a (nan where either run has no score)."""
    sa, sb = summarize(a), summarize(b)
    return {key: sb[key] - sa[key] for key in sa}
