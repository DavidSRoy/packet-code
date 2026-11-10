import csv
from pathlib import Path

import cv2
import numpy as np

from flightsim.recorder import FrameRow, Recorder

COLUMNS = ["frame", "t_exposure", "detected", "tags", "est_x", "est_y", "est_z",
           "true_x", "true_y", "true_z", "err_xy_mm"]


def test_recorder_writes_three_files_and_closes(tmp_path: Path):
    rec = Recorder(tmp_path, fps=10.0)
    img = np.full((120, 160), 90, np.uint8)
    outline = ((10.0, 10.0), (50.0, 10.0), (50.0, 50.0), (10.0, 50.0))
    rec.add(img, FrameRow(0, 0.5, 1, 2, (0.003, 0.004, -0.5), (0.0, 0.0, -0.5), (outline,)))
    rec.add(img, FrameRow(1, 0.6, 0, 0, None, (0.0, 0.0, -20.0)))
    rec.close()

    for name in ("camera.mp4", "overlay.mp4"):
        cap = cv2.VideoCapture(str(tmp_path / name))
        assert cap.isOpened()
        n = 0
        while cap.read()[0]:
            n += 1
        cap.release()
        assert n == 2, name

    rows = list(csv.DictReader((tmp_path / "frames.csv").read_text().splitlines()))
    assert list(rows[0].keys()) == COLUMNS
    assert rows[0]["detected"] == "1" and rows[0]["tags"] == "2"
    assert float(rows[0]["err_xy_mm"]) == 5.0
    assert rows[1]["detected"] == "0" and rows[1]["est_x"] == "" and rows[1]["err_xy_mm"] == ""
