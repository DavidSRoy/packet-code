import socket
import threading
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from flightsim.frames import Quat, Vec3
from flightsim.render_link import RenderClient, serve


def ramp(pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]:
    base = int(t * 10) % 256
    return ((np.arange(12 * 8).reshape(8, 12) + base) % 256).astype(np.uint8)


@pytest.fixture
def server(tmp_path: Path) -> Iterator[int]:
    ready = tmp_path / "ready"
    thread = threading.Thread(target=serve, args=(ramp, 0, ready), daemon=True)
    thread.start()
    for _ in range(500):
        if ready.exists() and ready.read_text():
            break
        threading.Event().wait(0.01)
    port = int(ready.read_text())
    yield port
    try:
        RenderClient("127.0.0.1", port, timeout_s=2.0).quit()
    except OSError:
        pass
    thread.join(timeout=5.0)


def test_render_round_trip(server: int):
    client = RenderClient("127.0.0.1", server, timeout_s=5.0)
    a = client.render((0, 0, 1), (1, 0, 0, 0), 1.25)
    assert a.shape == (8, 12)
    assert a.dtype == np.uint8
    assert np.array_equal(a, ramp((0, 0, 1), (1, 0, 0, 0), 1.25))
    first = client.last_frame_id
    client.render((0, 0, 1), (1, 0, 0, 0), 1.35)
    assert client.last_frame_id == first + 1
    client.close()


def test_render_client_times_out_with_context():
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(1)
    client = RenderClient("127.0.0.1", silent.getsockname()[1], timeout_s=0.2)
    with pytest.raises(TimeoutError, match=r"\[render_link:render\]"):
        client.render((0, 0, 1), (1, 0, 0, 0), 0.0)
    client.close()
    silent.close()


def test_server_rejects_bad_request(server: int):
    bad = socket.create_connection(("127.0.0.1", server), timeout=5.0)
    bad.sendall(b"not json\n")
    assert bad.recv(16) == b""
    bad.close()
    client = RenderClient("127.0.0.1", server, timeout_s=5.0)
    assert client.render((0, 0, 1), (1, 0, 0, 0), 0.0).shape == (8, 12)
    client.close()
