from pathlib import Path

import pytest

from flightsim import __main__ as cli
from flightsim import hover
from flightsim.config import Cluster
from flightsim.remote import RemoteError

CLUSTER = Cluster("my-alias", "acct", "gpu", "cpu", "/scratch/me")
RUN = hover.HoverRun(camera="ov9281", compute="pi-zero-2w", height=0.5, hold=30.0, seed=0, name="h1")


class Calls:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self.names: list[str] = []
        self.submit_args: tuple[str, str, dict[str, str], int] | None = None
        self.wait_timeout_s = 0.0
        self.fetch_dest: Path | None = None
        self.ssh_commands: list[str] = []
        self.ssh_reply: str | RemoteError = ""
        self.wait_error: RemoteError | None = None
        self.fetch_error: RemoteError | None = None
        monkeypatch.setattr(hover, "repo_commit", lambda: "abc123")
        monkeypatch.setattr(hover, "RESULTS_ROOT", tmp_path)
        monkeypatch.setattr(hover, "ssh", self._ssh)
        monkeypatch.setattr(hover.jobs, "push_source", self._push_source)
        monkeypatch.setattr(hover.jobs, "push_backend", self._push_backend)
        monkeypatch.setattr(hover.jobs, "submit", self._submit)
        monkeypatch.setattr(hover.jobs, "wait", self._wait)
        monkeypatch.setattr(hover.jobs, "fetch", self._fetch)

    def _ssh(self, _cluster: Cluster, command: str, *, timeout_s: float = 60.0) -> str:
        self.names.append("preflight")
        self.ssh_commands.append(command)
        if isinstance(self.ssh_reply, RemoteError):
            raise self.ssh_reply
        return self.ssh_reply

    def _push_source(self, _cluster: Cluster, run_name: str) -> str:
        self.names.append("push_source")
        return "src"

    def _push_backend(self, _cluster: Cluster, run_name: str) -> str:
        self.names.append("push_backend")
        return "repo"

    def _submit(self, _cluster: Cluster, script: str, run_name: str, env: dict[str, str], *, gpu: bool = True,
                time_min: int = 30) -> int:
        self.names.append("submit")
        assert gpu
        self.submit_args = (script, run_name, dict(env), time_min)
        return 77

    def _wait(self, _cluster: Cluster, job_id: int, *, poll_s: float = 15.0, timeout_s: float = 2400.0) -> str:
        self.names.append("wait")
        assert job_id == 77
        self.wait_timeout_s = timeout_s
        if self.wait_error is not None:
            raise self.wait_error
        return "COMPLETED"

    def _fetch(self, _cluster: Cluster, run_name: str, dest: Path) -> Path:
        self.names.append("fetch")
        self.fetch_dest = dest
        if self.fetch_error is not None:
            raise self.fetch_error
        return dest


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Calls:
    return Calls(monkeypatch, tmp_path)


def test_call_order_is_preflight_push_submit_wait_fetch(calls: Calls, tmp_path: Path) -> None:
    folder = hover.run_hover(CLUSTER, RUN)
    assert calls.names == ["preflight", "push_source", "push_backend", "submit", "wait", "fetch"]
    assert folder == tmp_path / "h1" == calls.fetch_dest


def test_submit_gets_versions_arguments_and_a_long_time_limit(calls: Calls) -> None:
    hover.run_hover(CLUSTER, RUN)
    assert calls.submit_args is not None
    script, name, env, time_min = calls.submit_args
    assert script == "/scratch/me/runs/h1/src/cluster/hover.sbatch" and name == "h1"
    versions = hover.load_versions()
    assert env == {
        "SCRATCH": "/scratch/me", "RUN_NAME": "h1", "REPO_DIR": "/scratch/me/runs/h1/repo",
        "ISAAC_IMAGE": versions.isaac_image, "ARDUPILOT_TAG": versions.ardupilot_tag,
        "ARDUPILOT_DEV_IMAGE": versions.ardupilot_dev_image, "REPO_COMMIT": "abc123",
        "CAMERA": "ov9281", "COMPUTE": "pi-zero-2w", "HEIGHT": "0.5", "HOLD": "30.0", "SEED": "0",
    }
    assert time_min == 120
    assert calls.wait_timeout_s > time_min * 60


def test_debug_kill_variable_is_passed_through(calls: Calls, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLIGHTSIM_DEBUG_KILL_RENDER_AFTER_S", "10")
    hover.run_hover(CLUSTER, RUN)
    assert calls.submit_args is not None and calls.submit_args[2]["DEBUG_KILL_RENDER_AFTER_S"] == "10"


def test_missing_scratch_path_raises_before_submit(calls: Calls) -> None:
    calls.ssh_reply = "/scratch/me/ardupilot/build/sitl/bin/arducopter\n"
    with pytest.raises(RemoteError) as info:
        hover.run_hover(CLUSTER, RUN)
    assert str(info.value) == (
        "[hover:preflight] Missing on scratch — /scratch/me/ardupilot/build/sitl/bin/arducopter; "
        "run: bash flight-sim/cluster/bootstrap.sh"
    )
    assert calls.names == ["preflight"]


def test_preflight_checks_container_ardupilot_and_venv(calls: Calls) -> None:
    hover.preflight(CLUSTER)
    command = calls.ssh_commands[0]
    versions = hover.load_versions()
    for needle in ("/scratch/me/containers/ardupilot-dev-base.sif", "/scratch/me/ardupilot/build/sitl/bin/arducopter",
                   "/scratch/me/venv/.complete", "/scratch/me/containers/" + hover.isaac_sif_name(versions.isaac_image)):
        assert needle in command


def test_isaac_sif_name_matches_the_sbatch_scripts() -> None:
    assert hover.isaac_sif_name("nvcr.io/nvidia/isaac-sim:6.2.0") == "isaac-sim_6.2.0.sif"


def test_dead_connection_raises_the_connection_error_before_anything_else(calls: Calls) -> None:
    calls.ssh_reply = RemoteError("[remote:ssh] No live connection — run: ssh my-alias")
    with pytest.raises(RemoteError, match=r"\[remote:ssh\] No live connection — run: ssh my-alias"):
        hover.run_hover(CLUSTER, RUN)
    assert calls.names == ["preflight"]


def test_failed_job_still_fetches_what_it_left_then_raises(calls: Calls) -> None:
    calls.wait_error = RemoteError("[jobs:wait] Job did not complete — {job_id: 77, state: FAILED}")
    with pytest.raises(RemoteError, match="state: FAILED"):
        hover.run_hover(CLUSTER, RUN)
    assert calls.names[-2:] == ["wait", "fetch"]


def test_failed_job_error_survives_a_failing_fetch(calls: Calls) -> None:
    calls.wait_error = RemoteError("[jobs:wait] Job did not complete — {job_id: 77, state: FAILED}")
    calls.fetch_error = RemoteError("[jobs:fetch] rsync failed — {exit: 255}")
    with pytest.raises(RemoteError, match="state: FAILED"):
        hover.run_hover(CLUSTER, RUN)


def test_unknown_profile_is_rejected_before_any_cluster_call(calls: Calls) -> None:
    with pytest.raises(FileNotFoundError, match=r"\[hover:run_hover\] No such camera profile"):
        hover.run_hover(CLUSTER, hover.HoverRun("nope", "pi-zero-2w", 0.5, 30.0, 0, "h1"))
    assert calls.names == []


def test_main_prints_the_results_folder(calls: Calls, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                                        tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "load_cluster", lambda: CLUSTER)
    code = cli.main(["hover", "--camera", "ov9281", "--compute", "pi-zero-2w", "--height", "0.5", "--hold", "30",
                     "--seed", "0", "--name", "h1"])
    assert code == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "h1")


def test_main_reports_remote_errors_without_a_traceback(calls: Calls, monkeypatch: pytest.MonkeyPatch,
                                                       capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "load_cluster", lambda: CLUSTER)
    calls.ssh_reply = RemoteError("[remote:ssh] No live connection — run: ssh my-alias")
    code = cli.main(["hover", "--camera", "ov9281", "--compute", "pi-zero-2w", "--height", "0.5", "--hold", "30",
                     "--seed", "0"])
    assert code == 1
    assert "[remote:ssh] No live connection" in capsys.readouterr().err
