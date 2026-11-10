import json
import signal
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVO16 = struct.Struct("<HHI16H")
RATE_HZ = 1200


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _is_bound(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return True
    return False


def _servo_packet(frame_count: int) -> bytes:
    return SERVO16.pack(18458, RATE_HZ, frame_count, *([1500] * 16))


def _replies(sock: socket.socket, wait_s: float) -> list[float]:
    stamps: list[float] = []
    deadline = time.monotonic() + wait_s
    while (left := deadline - time.monotonic()) > 0:
        sock.settimeout(left)
        try:
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            break
        stamps.append(float(json.loads(data)["timestamp"]))
    return stamps


def test_resent_servo_packet_during_a_slow_render_steps_physics_once(tmp_path: Path) -> None:
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "slow_render_physics.py"), "--out", str(tmp_path / "truth.npz"),
         "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    sitl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for _ in range(100):
            if _is_bound(port) or proc.poll() is not None:
                break
            time.sleep(0.1)
        assert proc.poll() is None, "physics exited at startup"
        sitl.sendto(_servo_packet(7), ("127.0.0.1", port))
        time.sleep(0.3)                                     # physics is now inside its 1.5 s render
        sitl.sendto(_servo_packet(7), ("127.0.0.1", port))  # SITL's resend of the same frame
        sitl.sendto(_servo_packet(8), ("127.0.0.1", port))
        replies = _replies(sitl, 3.0)
    finally:
        sitl.close()
        proc.send_signal(signal.SIGTERM)
        output = proc.communicate(timeout=20)[0].decode(errors="replace")
    assert len(replies) == 2, f"expected one reply per distinct frame — {{replies: {replies}, output: {output[-300:]!r}}}"
    assert abs(replies[1] - replies[0] - 1.0 / RATE_HZ) < 1e-9
