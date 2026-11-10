import csv
import json
from pathlib import Path

import pytest

from flightsim import __main__ as cli
import math

from flightsim.compare import compare, describe, summarize


def make_run(folder: Path, rms: float | None, mx: float | None, rows: list[tuple[float, int]],
             with_start: bool = True) -> Path:
    folder.mkdir()
    events = {"start_fc": [0.0, 0.0, -0.3]} if with_start else {}
    result: dict[str, object] = {"height": 0.5, "events": events, "status": "ok"}
    if rms is not None and mx is not None:
        result["score"] = {"xy_rms_mm": rms, "xy_max_mm": mx}
    else:
        result["status"] = "disarmed in the hold"
    (folder / "result.json").write_text(json.dumps(result))
    with (folder / "frames.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame", "t_exposure", "detected", "tags", "est_x", "est_y", "est_z",
                         "true_x", "true_y", "true_z", "err_xy_mm"])
        for i, (z, hit) in enumerate(rows):
            writer.writerow([i, i * 0.1, hit, 0, "", "", "", 0, 0, z, ""])
    return folder


def test_summarize_counts_only_frames_in_the_hold_window(tmp_path: Path) -> None:
    run = make_run(tmp_path / "a", 5.0, 10.0, [(-0.3, 0), (-0.8, 1), (-0.8, 1), (-0.8, 0), (-0.2, 0)])
    s = summarize(run)
    assert s == {"xy_rms_mm": 5.0, "xy_max_mm": 10.0, "detection_rate": pytest.approx(2 / 3)}


def test_summarize_uses_all_frames_without_a_start_event(tmp_path: Path) -> None:
    run = make_run(tmp_path / "a", 5.0, 10.0, [(-0.3, 0), (-0.8, 1)], with_start=False)
    assert summarize(run)["detection_rate"] == 0.5


def test_compare_is_b_minus_a(tmp_path: Path) -> None:
    a = make_run(tmp_path / "a", 5.0, 10.0, [(-0.8, 1), (-0.8, 1)])
    b = make_run(tmp_path / "b", 7.5, 14.0, [(-0.8, 1), (-0.8, 0)])
    assert compare(a, b) == {"xy_rms_mm": 2.5, "xy_max_mm": 4.0, "detection_rate": -0.5}


def test_compare_names_the_folder_when_a_file_is_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"\[compare:summarize\].*result.json"):
        summarize(tmp_path)


def test_cli_compare_prints_both_runs_and_the_difference(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a = make_run(tmp_path / "a", 5.0, 10.0, [(-0.8, 1)])
    b = make_run(tmp_path / "b", 6.0, 12.0, [(-0.8, 1)])
    assert cli.main(["compare", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "xy_rms_mm" in out and "1.000" in out


def test_killed_run_has_no_score_so_errors_are_nan_and_the_rate_uses_all_frames(tmp_path: Path) -> None:
    run = make_run(tmp_path / "k", None, None, [(-0.3, 1), (-0.3, 1), (-0.3, 0), (-0.3, 1)])
    s = summarize(run)
    assert math.isnan(s["xy_rms_mm"]) and math.isnan(s["xy_max_mm"]) and s["detection_rate"] == 0.75
    assert describe(run) == ("disarmed in the hold", False)


def test_describe_reports_hold_window_use(tmp_path: Path) -> None:
    assert describe(make_run(tmp_path / "a", 5.0, 10.0, [(-0.8, 1)])) == ("ok", True)


def test_compare_with_a_killed_run_gives_nan_errors(tmp_path: Path) -> None:
    a = make_run(tmp_path / "a", 5.0, 10.0, [(-0.8, 1)])
    k = make_run(tmp_path / "k", None, None, [(-0.3, 1), (-0.3, 0)])
    d = compare(a, k)
    assert math.isnan(d["xy_rms_mm"]) and d["detection_rate"] == -0.5


def test_malformed_result_raises_the_formatted_error(tmp_path: Path) -> None:
    run = make_run(tmp_path / "a", 5.0, 10.0, [(-0.8, 1)])
    (run / "result.json").write_text("{}")
    with pytest.raises(ValueError, match=r"\[compare:summarize\] Missing key"):
        summarize(run)
