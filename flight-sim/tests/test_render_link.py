import socket
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from flightsim.frames import Quat, Vec3
from flightsim.render_link import RenderClient, serve

RenderFn = Callable[[Vec3, Quat, float], NDArray[np.uint8]]
POS: Vec3 = (0.0, 0.0, 1.0)
QUAT: Quat = (1.0, 0.0, 0.0, 0.0)


def ramp(pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]:
    base = int(t * 10) % 256
    return ((np.arange(12 * 8).reshape(8, 12) + base) % 256).astype(np.uint8)


def wrong_dtype(pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]:
    return np.zeros((4, 4), dtype=np.float32)  # type: ignore[return-value]


def start(render_fn: RenderFn, tmp_path: Path) -> tuple[threading.Thread, int]:
    ready = tmp_path / "ready"
    thread = threading.Thread(target=serve, args=(render_fn, 0, ready), daemon=True)
    thread.start()
    for _ in range(500):
        if ready.exists() and ready.read_text():
            break
        threading.Event().wait(0.01)
    return thread, int(ready.read_text())


def stop(thread: threading.Thread, port: int) -> None:
    try:
        RenderClient("127.0.0.1", port, timeout_s=2.0).quit()
    except OSError:
        pass
    thread.join(timeout=5.0)


@pytest.fixture
def server(tmp_path: Path) -> Iterator[int]:
    thread, port = start(ramp, tmp_path)
    yield port
    stop(thread, port)


def test_render_round_trip(server: int):
    client = RenderClient("127.0.0.1", server, timeout_s=5.0)
    try:
        a = client.render(POS, QUAT, 1.25)
        assert a.shape == (8, 12)
        assert a.dtype == np.uint8
        assert np.array_equal(a, ramp(POS, QUAT, 1.25))
        first = client.last_frame_id
        client.render(POS, QUAT, 1.35)
        assert client.last_frame_id == first + 1
    finally:
        client.close()


def test_render_client_times_out_with_context():
    silent = socket.socket()
    try:
        silent.bind(("127.0.0.1", 0))
        silent.listen(1)
        client = RenderClient("127.0.0.1", silent.getsockname()[1], timeout_s=0.2)
        try:
            with pytest.raises(TimeoutError, match=r"\[render_link:render\]"):
                client.render(POS, QUAT, 0.0)
            with pytest.raises(OSError):  # socket was closed so a late reply cannot be read
                client.render(POS, QUAT, 0.0)
        finally:
            client.close()
    finally:
        silent.close()


def test_server_rejects_bad_request(server: int, capsys: pytest.CaptureFixture[str]):
    bad = socket.create_connection(("127.0.0.1", server), timeout=5.0)
    try:
        bad.sendall(b"not json\n")
        assert bad.recv(16) == b""
    finally:
        bad.close()
    assert "[render_link:parse]" in capsys.readouterr().err
    client = RenderClient("127.0.0.1", server, timeout_s=5.0)
    try:
        assert client.render(POS, QUAT, 0.0).shape == (8, 12)
    finally:
        client.close()


def test_server_survives_client_that_drops_without_reading(server: int):
    dropper = socket.create_connection(("127.0.0.1", server), timeout=5.0)
    try:
        dropper.sendall(b'{"pos":[0,0,1],"quat":[1,0,0,0],"t":0.0}\n')
    finally:
        dropper.close()
    client = RenderClient("127.0.0.1", server, timeout_s=5.0)
    try:
        assert client.render(POS, QUAT, 0.0).shape == (8, 12)
    finally:
        client.close()


def test_server_drops_client_when_callback_returns_wrong_array(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    thread, port = start(wrong_dtype, tmp_path)
    try:
        client = RenderClient("127.0.0.1", port, timeout_s=5.0)
        try:
            with pytest.raises(ConnectionError):
                client.render(POS, QUAT, 0.0)
        finally:
            client.close()
        assert "[render_link:serve]" in capsys.readouterr().err
    finally:
        stop(thread, port)
