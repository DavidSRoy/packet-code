import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "cluster.local.toml"
_KEYS = ("ssh_alias", "account", "gpu_partition", "cpu_partition", "scratch_dir")


@dataclass(frozen=True)
class Cluster:
    ssh_alias: str
    account: str
    gpu_partition: str
    cpu_partition: str
    scratch_dir: str


def load_cluster(path: Path | None = None) -> Cluster:
    target = path if path is not None else DEFAULT_PATH
    if not target.is_file():
        raise FileNotFoundError(
            f"[config:load_cluster] Config file not found — {{path: {target}}}; "
            "copy cluster.example.toml to cluster.local.toml and fill it in"
        )
    with target.open("rb") as handle:
        data = tomllib.load(handle)
    values: dict[str, str] = {}
    for key in _KEYS:
        if key not in data:
            raise KeyError(f"[config:load_cluster] Missing key — {{key: {key}, path: {target}}}")
        value = data[key]
        if not isinstance(value, str):
            raise TypeError(
                f"[config:load_cluster] Expected a string — {{key: {key}, got: {type(value).__name__}}}"
            )
        values[key] = value
    return Cluster(**values)
