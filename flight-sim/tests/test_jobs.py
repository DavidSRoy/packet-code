import subprocess
from pathlib import Path

import pytest

from flightsim import jobs
from flightsim.config import Cluster
from flightsim.remote import RemoteError

CLUSTER = Cluster("my-alias", "acct", "gpu", "cpu", "/scratch/me")


def _record_ssh(monkeypatch: pytest.MonkeyPatch, replies: list[str]) -> list[str]:
    commands: list[str] = []

    def fake(_cluster: Cluster, command: str, *, timeout_s: float = 60.0) -> str:
        commands.append(command)
        return replies.pop(0) if replies else ""

    monkeypatch.setattr(jobs, "ssh", fake)
    return commands


def test_submit_gpu_builds_sbatch_and_parses_id(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = _record_ssh(monkeypatch, ["4242\n"])
    job_id = jobs.submit(CLUSTER, "/scratch/me/runs/r1/src/cluster/smoke.sbatch", "r1", {"K": "V", "N": "3"})
    assert job_id == 4242
    sbatch = commands[-1]
    assert "sbatch --parsable -A acct -p gpu --gpus=1 --time=30" in sbatch
    assert "--export=ALL,K=V,N=3" in sbatch
    assert "--output=/scratch/me/runs/r1/out/slurm-%j.log" in sbatch
    assert sbatch.endswith("/scratch/me/runs/r1/src/cluster/smoke.sbatch")
    assert "mkdir -p /scratch/me/runs/r1/out" in commands[0]
    assert len(commands) == 1


def test_submit_cpu_uses_cpu_partition_without_gpus(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = _record_ssh(monkeypatch, ["7\n"])
    assert jobs.submit(CLUSTER, "s.sbatch", "r1", {}, gpu=False) == 7
    assert "-p cpu" in commands[-1]
    assert "--gpus" not in commands[-1]
    assert "--export=ALL " in commands[-1]


def test_submit_rejects_unparsable_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _record_ssh(monkeypatch, ["Submitted batch job x\n"])
    with pytest.raises(RemoteError, match=r"\[jobs:submit\] Could not parse job id"):
        jobs.submit(CLUSTER, "s.sbatch", "r1", {})


@pytest.mark.parametrize("name", ["a b", "../x", "r;rm", "", "r/1"])
def test_run_name_is_validated(name: str) -> None:
    with pytest.raises(ValueError, match=r"\[jobs:"):
        jobs.submit(CLUSTER, "s.sbatch", name, {})
    with pytest.raises(ValueError, match=r"\[jobs:"):
        jobs.push_source(CLUSTER, name)
    with pytest.raises(ValueError, match=r"\[jobs:"):
        jobs.fetch(CLUSTER, name, Path("/tmp/x"))


@pytest.mark.parametrize("env", [{"A,B": "1"}, {"A": "x,y"}, {"1A": "x"}])
def test_env_with_commas_or_bad_keys_rejected(env: dict[str, str]) -> None:
    with pytest.raises(ValueError, match=r"\[jobs:submit\]"):
        jobs.submit(CLUSTER, "s.sbatch", "r1", env)


def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs.time, "sleep", lambda _s: None)


def test_wait_polls_until_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_sleep(monkeypatch)
    commands = _record_ssh(monkeypatch, ["", "PENDING\n", "RUNNING\n", "COMPLETED\n"])
    assert jobs.wait(CLUSTER, 9) == "COMPLETED"
    assert "sacct -j 9" in commands[0]
    assert len(commands) == 4


@pytest.mark.parametrize("state", ["FAILED", "TIMEOUT", "CANCELLED by 123", "PREEMPTED", "OUT_OF_MEMORY"])
def test_wait_raises_naming_terminal_failure(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    _no_sleep(monkeypatch)
    _record_ssh(monkeypatch, [f"{state}\n"])
    with pytest.raises(RemoteError, match=rf"\[jobs:wait\] Job did not complete — .*{state.split()[0]}"):
        jobs.wait(CLUSTER, 9)


def test_wait_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_sleep(monkeypatch)
    ticks = iter([0.0, 1.0, 100.0, 200.0])
    monkeypatch.setattr(jobs.time, "monotonic", lambda: next(ticks))
    _record_ssh(monkeypatch, ["RUNNING\n"] * 5)
    with pytest.raises(RemoteError, match=r"\[jobs:wait\] Timed out"):
        jobs.wait(CLUSTER, 9, timeout_s=50.0)


def test_push_source_pipes_git_archive_into_tar(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], bytes | None]] = []

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raw = kwargs.get("input")
        calls.append((argv, raw if isinstance(raw, bytes) else None))
        return subprocess.CompletedProcess(argv, 0, b"TARBYTES", b"")

    monkeypatch.setattr(subprocess, "run", run)
    assert jobs.push_source(CLUSTER, "r1") == "/scratch/me/runs/r1/src"
    assert calls[0][0][:3] == ["git", "archive", "HEAD"]
    assert calls[1][0][:5] == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    assert calls[1][0][5] == "my-alias"
    assert "tar x -C /scratch/me/runs/r1/src" in calls[1][0][-1]
    assert calls[1][1] == b"TARBYTES"


def test_push_source_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 3, b"", b"nope")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RemoteError, match=r"\[jobs:push_source\] .*nope"):
        jobs.push_source(CLUSTER, "r1")


def test_fetch_rsyncs_out_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    dest = tmp_path / "res"
    assert jobs.fetch(CLUSTER, "r1", dest) == dest
    assert calls[0][0] == "rsync"
    assert calls[0][-2] == "my-alias:/scratch/me/runs/r1/out/"
    assert calls[0][-1] == f"{dest}/"
    assert dest.is_dir()
