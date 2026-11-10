import json
import socket
import struct
from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from flightsim.frames import Quat, Vec3

_HEADER = struct.Struct("<III")


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(
                f"[render_link:recv_exact] Peer closed mid-frame — {{wanted: {n}, got: {len(buf)}}}"
            )
        buf.extend(chunk)
    return bytes(buf)


class RenderClient:
    def __init__(self, host: str, port: int, *, timeout_s: float = 120.0) -> None:
        self._timeout_s = timeout_s
        self._sock = socket.create_connection((host, port), timeout=timeout_s)
        self._sock.settimeout(timeout_s)
        self.last_frame_id = -1

    def render(self, pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]:
        request = json.dumps({"pos": list(pos), "quat": list(quat), "t": t}) + "\n"
        try:
            self._sock.sendall(request.encode())
            width, height, frame_id = _HEADER.unpack(_recv_exact(self._sock, _HEADER.size))
            data = _recv_exact(self._sock, width * height)
        except TimeoutError as exc:
            raise TimeoutError(
                f"[render_link:render] No reply from renderer — {{timeout_s: {self._timeout_s}, t: {t}}}"
            ) from exc
        self.last_frame_id = frame_id
        return np.frombuffer(data, dtype=np.uint8).reshape(height, width)

    def quit(self) -> None:
        self._sock.sendall(b'{"op":"quit"}\n')
        self.close()

    def close(self) -> None:
        self._sock.close()


def _parse(line: bytes) -> tuple[Vec3, Quat, float] | None:
    """None means a quit request; a malformed request raises ValueError."""
    try:
        req = json.loads(line)
        if req == {"op": "quit"}:
            return None
        px, py, pz = (float(v) for v in req["pos"])
        qw, qx, qy, qz = (float(v) for v in req["quat"])
        return (px, py, pz), (qw, qx, qy, qz), float(req["t"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"[render_link:parse] Malformed request — {{line: {line[:80]!r}}}") from exc


def serve(
    render_fn: Callable[[Vec3, Quat, float], NDArray[np.uint8]], port: int, ready_file: Path
) -> None:
    frame_id = 0
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen(1)
        ready_file.write_text(str(listener.getsockname()[1]))
        while True:
            conn, _ = listener.accept()
            with conn, conn.makefile("rb") as lines:
                for line in lines:
                    try:
                        request = _parse(line)
                    except ValueError:
                        break  # drop this client, keep serving
                    if request is None:
                        return
                    image = render_fn(*request)
                    height, width = image.shape
                    conn.sendall(_HEADER.pack(width, height, frame_id) + image.tobytes())
                    frame_id += 1
