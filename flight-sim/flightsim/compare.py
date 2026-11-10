"""Compare two hover result folders: position error and detection rate."""
import csv
import json
from pathlib import Path

HOLD_MARGIN_M = 0.05    # a frame is in the hold when it is within this of the target height


def _read(fn: str, path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"[compare:{fn}] Missing result file — {{path: {str(path)!r}}}")
    return path.read_text()


def _number(fn: str, raw: object, key: str) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    raise ValueError(f"[compare:{fn}] Not a number — {{key: {key!r}, value: {raw!r}}}")


def summarize(folder: Path) -> dict[str, float]:
    """xy_rms_mm, xy_max_mm and detection_rate. The rate counts frames in the hold window (true height within
    HOLD_MARGIN_M of the target), or every frame when result.json has no start position."""
    result = json.loads(_read("summarize", folder / "result.json"))
    score = result["score"]
    rows = list(csv.DictReader(_read("summarize", folder / "frames.csv").splitlines()))
    start = result.get("events", {}).get("start_fc")
    if start:
        floor = _number("summarize", start[2], "start_fc.z") - _number("summarize", result["height"], "height") + HOLD_MARGIN_M
        rows = [r for r in rows if float(r["true_z"]) < floor]
    if not rows:
        raise ValueError(f"[compare:summarize] No frames to rate — {{folder: {str(folder)!r}}}")
    return {
        "xy_rms_mm": _number("summarize", score["xy_rms_mm"], "xy_rms_mm"),
        "xy_max_mm": _number("summarize", score["xy_max_mm"], "xy_max_mm"),
        "detection_rate": sum(int(r["detected"]) for r in rows) / len(rows),
    }


def compare(a: Path, b: Path) -> dict[str, float]:
    """Differences, b minus a."""
    sa, sb = summarize(a), summarize(b)
    return {key: sb[key] - sa[key] for key in sa}
