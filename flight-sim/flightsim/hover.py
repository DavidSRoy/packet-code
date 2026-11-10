"""The `hover` command: one closed-loop hover on Isaac frames, from push to results folder."""
import math
import os
import shlex
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from flightsim import jobs
from flightsim.config import Cluster
from flightsim.remote import RemoteError, ssh

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_PATH = _SOURCE_ROOT / "versions.toml"
RESULTS_ROOT = _SOURCE_ROOT / "results"
JOB_TIME_FLOOR_MIN = 120    # about 700 frames at 3.2 s each, plus Isaac start and shader compile
_WAIT_SLACK_S = 600.0
_DEBUG_KILL_VAR = "FLIGHTSIM_DEBUG_KILL_RENDER_AFTER_S"


@dataclass(frozen=True)
class Versions:
    isaac_image: str
    ardupilot_tag: str
    ardupilot_dev_image: str
    uv_version: str
    opencv_requirement: str


@dataclass(frozen=True)
class HoverRun:
    camera: str
    compute: str
    height: float
    hold: float
    seed: int
    name: str


def load_versions(path: Path = VERSIONS_PATH) -> Versions:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    values: dict[str, str] = {}
    for key in ("isaac_image", "ardupilot_tag", "ardupilot_dev_image", "uv_version", "opencv_requirement"):
        value = data.get(key)
        if not isinstance(value, str):
            raise ValueError(f"[hover:load_versions] Missing or non-string key — {{key: {key}, path: {path}}}")
        values[key] = value
    return Versions(**values)


def job_time_min(run: "HoverRun") -> int:
    """Slurm limit: 15 min for Isaac start and shader compile, then 10 frames per flight second at up to 3.3 s each
    (flight is about 60 s of takeoff, settle and descent plus the hold and the climb at 0.05 m/s)."""
    flight_s = 60.0 + run.hold + run.height / 0.05
    return max(JOB_TIME_FLOOR_MIN, math.ceil(15 + flight_s * 10 * 3.3 / 60))


def isaac_sif_name(image: str) -> str:
    """The file name bootstrap.sh and the sbatch scripts give the pulled image."""
    return image.split("/", 2)[2].replace(":", "_").replace("/", "_") + ".sif"


def repo_commit(root: Path = _SOURCE_ROOT) -> str:
    """HEAD of the repo, with "-dirty" appended when flight-sim or backend has uncommitted changes."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=root, timeout=30.0, check=False
    )
    if head.returncode != 0:
        raise RemoteError(f"[hover:repo_commit] git rev-parse failed — {{stderr: {head.stderr[-300:]!r}}}")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", ".", "../backend"],
        capture_output=True, text=True, cwd=root, timeout=30.0, check=False,
    )
    if status.returncode != 0:
        raise RemoteError(f"[hover:repo_commit] git status failed — {{stderr: {status.stderr[-300:]!r}}}")
    return head.stdout.strip() + ("-dirty" if status.stdout.strip() else "")


def preflight(cluster: Cluster) -> None:
    """Raise RemoteError when the container, ArduPilot build or venv bootstrap.sh makes is missing."""
    scratch = cluster.scratch_dir
    required = [
        f"{scratch}/containers/{isaac_sif_name(load_versions().isaac_image)}",
        f"{scratch}/containers/ardupilot-dev-base.sif",
        f"{scratch}/ardupilot/build/sitl/bin/arducopter",
        f"{scratch}/venv/.complete",
    ]
    command = f"for p in {' '.join(shlex.quote(p) for p in required)}; do [ -e \"$p\" ] || {{ echo \"$p\"; exit 0; }}; done"
    missing = ssh(cluster, command).strip()
    if missing:
        raise RemoteError(
            f"[hover:preflight] Missing on scratch — {missing}; run: bash flight-sim/cluster/bootstrap.sh"
        )


def _check_profiles(run: HoverRun) -> None:
    for kind, name in (("camera", run.camera), ("compute", run.compute)):
        path = _SOURCE_ROOT / "profiles" / ("cameras" if kind == "camera" else "compute") / f"{name}.json"
        if not path.is_file():
            raise FileNotFoundError(f"[hover:run_hover] No such {kind} profile — {{path: {path}}}")


def run_hover(cluster: Cluster, run: HoverRun) -> Path:
    """preflight, push, submit, wait, fetch. Returns the local results folder."""
    _check_profiles(run)
    versions = load_versions()
    preflight(cluster)
    jobs.push_source(cluster, run.name)
    jobs.push_backend(cluster, run.name)
    run_dir = f"{cluster.scratch_dir}/runs/{run.name}"
    env = {
        "SCRATCH": cluster.scratch_dir, "RUN_NAME": run.name, "REPO_DIR": f"{run_dir}/repo",
        "ISAAC_IMAGE": versions.isaac_image, "ARDUPILOT_TAG": versions.ardupilot_tag,
        "ARDUPILOT_DEV_IMAGE": versions.ardupilot_dev_image, "REPO_COMMIT": repo_commit(),
        "CAMERA": run.camera, "COMPUTE": run.compute,
        "HEIGHT": str(run.height), "HOLD": str(run.hold), "SEED": str(run.seed),
    }
    kill_after = os.environ.get(_DEBUG_KILL_VAR)
    if kill_after:
        env["DEBUG_KILL_RENDER_AFTER_S"] = kill_after
    time_min = job_time_min(run)
    job_id = jobs.submit(cluster, f"{run_dir}/src/cluster/hover.sbatch", run.name, env, time_min=time_min)
    dest = RESULTS_ROOT / run.name
    try:
        jobs.wait(cluster, job_id, timeout_s=time_min * 60 + _WAIT_SLACK_S)
    except RemoteError:
        # a failed job still leaves its log tails and partial results; keep the job's error as the one raised
        try:
            jobs.fetch(cluster, run.name, dest)
            print(f"[hover:run_hover] Job failed, partial results fetched — {{dest: {dest}}}", file=sys.stderr)
        except RemoteError as fetch_error:
            print(f"[hover:run_hover] Job failed and the fetch failed too — {{fetch_error: {fetch_error}}}", file=sys.stderr)
        raise
    return jobs.fetch(cluster, run.name, dest)
