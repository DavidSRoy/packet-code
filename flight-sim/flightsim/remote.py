import subprocess

from flightsim.config import Cluster

_STDERR_TAIL = 500


class RemoteError(RuntimeError):
    pass


def connection_live(cluster: Cluster) -> bool:
    result = subprocess.run(
        ["ssh", "-O", "check", cluster.ssh_alias],
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    return result.returncode == 0


def ssh(cluster: Cluster, command: str, *, timeout_s: float = 60.0) -> str:
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", cluster.ssh_alias, command]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise RemoteError(
            f"[remote:ssh] Timed out — {{timeout_s: {timeout_s}, command: {command!r}}}"
        ) from exc
    if result.returncode == 255:
        raise RemoteError(f"[remote:ssh] No live connection — run: ssh {cluster.ssh_alias}")
    if result.returncode != 0:
        raise RemoteError(
            f"[remote:ssh] Command failed — {{exit: {result.returncode}, "
            f"stderr: {result.stderr[-_STDERR_TAIL:]!r}}}"
        )
    return result.stdout
