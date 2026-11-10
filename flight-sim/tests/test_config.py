from pathlib import Path

import pytest

from flightsim.config import Cluster, load_cluster

FULL = """
ssh_alias = "my-alias"
account = "my-account"
gpu_partition = "my-gpu"
cpu_partition = "my-cpu"
scratch_dir = "/scratch/me"
"""


def test_load_cluster_reads_all_fields(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text(FULL)
    assert load_cluster(path) == Cluster(
        ssh_alias="my-alias",
        account="my-account",
        gpu_partition="my-gpu",
        cpu_partition="my-cpu",
        scratch_dir="/scratch/me",
    )


def test_load_cluster_missing_file_names_example(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"\[config:load_cluster\].*cluster\.example\.toml"):
        load_cluster(tmp_path / "nope.toml")


def test_load_cluster_missing_key_names_key(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text(FULL.replace('scratch_dir = "/scratch/me"\n', ""))
    with pytest.raises(KeyError, match=r"\[config:load_cluster\].*scratch_dir"):
        load_cluster(path)


def test_load_cluster_non_string_value_rejected(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text(FULL.replace('account = "my-account"', "account = 5"))
    with pytest.raises(TypeError, match=r"\[config:load_cluster\].*account"):
        load_cluster(path)
