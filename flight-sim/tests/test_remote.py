import subprocess

import pytest

from flightsim.config import Cluster
from flightsim.remote import RemoteError, connection_live, ssh

CLUSTER = Cluster("my-alias", "acct", "gpu", "cpu", "/scratch/me")


def _fake_run(calls: list[list[str]], returncode: int, stdout: str = "", stderr: str = ""):
    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    return run


def test_ssh_argv_is_batch_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_run(calls, 0, "out\n"))
    assert ssh(CLUSTER, "hostname") == "out\n"
    assert calls[0][:6] == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "my-alias"]
    assert calls[0][-1] == "hostname"


def test_ssh_exit_255_says_how_to_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run([], 255, stderr="denied"))
    with pytest.raises(RemoteError, match=r"\[remote:ssh\] No live connection — run: ssh my-alias"):
        ssh(CLUSTER, "hostname")


def test_ssh_nonzero_reports_exit_and_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run([], 2, stderr="boom"))
    with pytest.raises(RemoteError, match=r"\[remote:ssh\] Command failed — .*2.*boom"):
        ssh(CLUSTER, "false")


def test_ssh_timeout_becomes_remote_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, 1.0)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RemoteError, match=r"\[remote:ssh\] Timed out"):
        ssh(CLUSTER, "sleep 9", timeout_s=1.0)


def test_connection_live_uses_control_check(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_run(calls, 0))
    assert connection_live(CLUSTER) is True
    assert calls[0] == ["ssh", "-O", "check", "my-alias"]


def test_connection_live_false_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run([], 255))
    assert connection_live(CLUSTER) is False
