import re
import shlex
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from flightsim.config import Cluster
from flightsim.remote import RemoteError, ssh

_RUN_NAME = re.compile(r"[A-Za-z0-9_.-]+")
_ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ACTIVE_STATES = frozenset(
    {"PENDING", "RUNNING", "COMPLETING", "REQUEUED", "SUSPENDED", "CONFIGURING", "RESIZING"}
)
_MAX_POLL_FAILURES = 3
_SOURCE_ROOT = Path(__file__).resolve().parents[1]
_STDERR_TAIL = 500


def _run_local(
    caller: str, step: str, argv: list[str], run_name: str, *, input: bytes | None = None, timeout_s: float = 60.0
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(argv, input=input, capture_output=True, cwd=_SOURCE_ROOT, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise RemoteError(
            f"[jobs:{caller}] Timed out — {{step: {step}, timeout_s: {timeout_s}, run_name: {run_name}}}"
        ) from exc


def _validate_run_name(caller: str, run_name: str) -> None:
    if run_name in {".", ".."} or _RUN_NAME.fullmatch(run_name) is None:
        raise ValueError(
            f"[jobs:{caller}] run_name must match [A-Za-z0-9_.-]+ — {{run_name: {run_name!r}}}"
        )


def _run_dir(cluster: Cluster, run_name: str) -> str:
    return f"{cluster.scratch_dir}/runs/{run_name}"


def _export_arg(env: Mapping[str, str]) -> str:
    parts = ["ALL"]
    for key, value in env.items():
        if _ENV_KEY.fullmatch(key) is None or "," in value:
            raise ValueError(
                f"[jobs:submit] Env entry cannot go through --export — {{key: {key!r}, has_comma: {',' in value}}}"
            )
        parts.append(f"{key}={value}")
    return ",".join(parts)


def push_source(cluster: Cluster, run_name: str) -> str:
    """Copy the committed tree (git archive HEAD) to the run's remote src dir."""
    _validate_run_name("push_source", run_name)
    remote = f"{_run_dir(cluster, run_name)}/src"
    status = _run_local("push_source", "git status", ["git", "status", "--porcelain", "--", str(_SOURCE_ROOT)], run_name)
    if status.returncode != 0:
        raise RemoteError(
            f"[jobs:push_source] git status failed — {{exit: {status.returncode}, "
            f"stderr: {status.stderr[-_STDERR_TAIL:]!r}}}"
        )
    dirty = status.stdout.decode(errors="replace").strip()
    if dirty:
        raise RemoteError(
            f"[jobs:push_source] Uncommitted changes would not ship; commit first — {{paths: {dirty.splitlines()!r}}}"
        )
    archive = _run_local("push_source", "git archive", ["git", "archive", "HEAD"], run_name)
    if archive.returncode != 0:
        raise RemoteError(
            f"[jobs:push_source] git archive failed — {{exit: {archive.returncode}, "
            f"stderr: {archive.stderr[-_STDERR_TAIL:]!r}}}"
        )
    command = f"rm -rf {shlex.quote(remote)} && mkdir -p {shlex.quote(remote)} && tar x -C {shlex.quote(remote)}"
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", cluster.ssh_alias, command]
    pushed = _run_local("push_source", "ssh untar", argv, run_name, input=archive.stdout, timeout_s=300.0)
    if pushed.returncode != 0:
        raise RemoteError(
            f"[jobs:push_source] Remote untar failed — {{exit: {pushed.returncode}, "
            f"stderr: {pushed.stderr[-_STDERR_TAIL:]!r}}}"
        )
    return remote


def submit(
    cluster: Cluster, script: str, run_name: str, env: Mapping[str, str], *, gpu: bool = True
) -> int:
    """sbatch a remote script; the job log lands in the run's out dir. Returns the job id."""
    _validate_run_name("submit", run_name)
    export = _export_arg(env)
    out_dir = f"{_run_dir(cluster, run_name)}/out"
    partition = cluster.gpu_partition if gpu else cluster.cpu_partition
    gpus = " --gpus=1" if gpu else ""
    sbatch = (
        f"sbatch --parsable -A {shlex.quote(cluster.account)} -p {shlex.quote(partition)}{gpus}"
        f" --time=30 --export={shlex.quote(export)}"
        f" --output={shlex.quote(out_dir)}/slurm-%j.log {shlex.quote(script)}"
    )
    stdout = ssh(cluster, f"mkdir -p {shlex.quote(out_dir)} && {sbatch}")
    first = stdout.strip().split(";")[0]
    if not first.isdigit():
        raise RemoteError(f"[jobs:submit] Could not parse job id — {{stdout: {stdout[-_STDERR_TAIL:]!r}}}")
    return int(first)


def wait(cluster: Cluster, job_id: int, *, poll_s: float = 15.0, timeout_s: float = 2400.0) -> str:
    """Poll sacct until the job ends. Returns COMPLETED, raises RemoteError for any other end state.

    Tolerates up to 2 consecutive ssh failures; the third raises so the caller can resume waiting.
    """
    deadline = time.monotonic() + timeout_s
    failures = 0
    while True:
        try:
            out = ssh(cluster, f"sacct -j {job_id} -X -n -P -o State")
        except RemoteError as exc:
            failures += 1
            if failures >= _MAX_POLL_FAILURES:
                raise RemoteError(
                    f"[jobs:wait] Lost connection — {{job_id: {job_id}, failures: {failures}, last: {exc}}}"
                ) from exc
            time.sleep(poll_s)
            continue
        failures = 0
        lines = out.strip().splitlines()
        state = lines[0].split()[0] if lines else ""
        if state == "COMPLETED":
            return state
        if state and state not in _ACTIVE_STATES:
            raise RemoteError(f"[jobs:wait] Job did not complete — {{job_id: {job_id}, state: {state}}}")
        if time.monotonic() > deadline:
            raise RemoteError(
                f"[jobs:wait] Timed out, job left running — {{job_id: {job_id}, "
                f"timeout_s: {timeout_s}, last_state: {state or 'unknown'}}}"
            )
        time.sleep(poll_s)


def fetch(cluster: Cluster, run_name: str, dest: Path) -> Path:
    """rsync the run's out dir into dest."""
    _validate_run_name("fetch", run_name)
    dest.mkdir(parents=True, exist_ok=True)
    argv = [
        "rsync", "-az", "-e", "ssh -o BatchMode=yes",
        f"{cluster.ssh_alias}:{_run_dir(cluster, run_name)}/out/", f"{dest}/",
    ]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=300.0)
    except subprocess.TimeoutExpired as exc:
        raise RemoteError(f"[jobs:fetch] Timed out — {{timeout_s: 300.0, run_name: {run_name}}}") from exc
    if result.returncode != 0:
        raise RemoteError(
            f"[jobs:fetch] rsync failed — {{exit: {result.returncode}, stderr: {result.stderr[-_STDERR_TAIL:]!r}}}"
        )
    return dest
