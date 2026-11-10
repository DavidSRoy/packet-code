"""Per-run recording of the rendered camera: camera.mp4, overlay.mp4 and frames.csv.

Truth and estimate columns share one frame and sign convention (the physics world, NED metres
from the hover simulator, which is what the VISION_POSITION_ESTIMATE carries), so err_xy_mm is
the plain horizontal difference of estimate minus truth, in millimetres.
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

Point = tuple[float, float]
Position = tuple[float, float, float]
COLUMNS = ["frame", "t_exposure", "detected", "tags", "est_x", "est_y", "est_z",
           "true_x", "true_y", "true_z", "err_xy_mm"]


@dataclass(frozen=True)
class FrameRow:
    frame: int
    t_exposure: float
    detected: int
    tags: int
    est: Position | None
    true: Position
    outlines: tuple[tuple[Point, ...], ...] = ()   # tag corners in frame pixels, for the overlay only


class Recorder:
    def __init__(self, record_dir: Path, fps: float) -> None:
        record_dir.mkdir(parents=True, exist_ok=True)
        self._fps = fps
        self._dir = record_dir
        self._writers: dict[str, cv2.VideoWriter] = {}
        self._csv_file = (record_dir / "frames.csv").open("w", newline="")
        self._csv = csv.writer(self._csv_file)
        self._csv.writerow(COLUMNS)

    def _write(self, name: str, image: NDArray[np.uint8]) -> None:
        writer = self._writers.get(name)
        if writer is None:
            height, width = image.shape[:2]
            writer = cv2.VideoWriter(str(self._dir / name), cv2.VideoWriter.fourcc("m", "p", "4", "v"), self._fps,
                                     (width, height))
            if not writer.isOpened():
                raise OSError(f"[recorder:write] Cannot open video writer — {{path: {str(self._dir / name)!r}}}")
            self._writers[name] = writer
        writer.write(image)

    def add(self, frame: NDArray[np.uint8], row: FrameRow) -> None:
        colour = np.asarray(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR), dtype=np.uint8)
        self._write("camera.mp4", colour)
        overlay: NDArray[np.uint8] = colour.copy()
        for outline in row.outlines:
            cv2.polylines(overlay, [np.round(np.array(outline)).astype(np.int32)], True, (0, 255, 0), 2)
        est = "no detection" if row.est is None else "est %.3f %.3f %.3f" % row.est
        cv2.putText(overlay, f"{row.frame} t={row.t_exposure:.2f} {est}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 255), 2)
        self._write("overlay.mp4", overlay)
        if row.est is None:
            est_cells, err = ["", "", ""], ""
        else:
            est_cells = [repr(v) for v in row.est]
            err = repr(round(math.hypot(row.est[0] - row.true[0], row.est[1] - row.true[1]) * 1000.0, 3))
        self._csv.writerow([row.frame, row.t_exposure, row.detected, row.tags, *est_cells,
                            *(repr(v) for v in row.true), err])

    def close(self) -> None:
        for writer in self._writers.values():
            writer.release()
        self._csv_file.close()
