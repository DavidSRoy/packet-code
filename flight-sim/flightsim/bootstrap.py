"""The `bootstrap` command: pull the images, build ArduPilot and make the Python environment on the cluster."""
import sys
from pathlib import Path

from flightsim import jobs
from flightsim.config import Cluster
from flightsim.hover import RESULTS_ROOT, load_versions
from flightsim.remote import RemoteError

BOOTSTRAP_NAME = "bootstrap"
BOOTSTRAP_TIME_MIN = 120    # image pull and squashfs build, ArduPilot compile, venv install


def run_bootstrap(cluster: Cluster) -> Path:
    """Push the source, run cluster/bootstrap.sh as a CPU job, wait, fetch its log. Returns the local log folder.

    Idempotent on the cluster: each step is skipped when its result is already there for the versions.toml values.
    """
    versions = load_versions()
    jobs.push_source(cluster, BOOTSTRAP_NAME)
    jobs.push_backend(cluster, BOOTSTRAP_NAME)
    run_dir = f"{cluster.scratch_dir}/runs/{BOOTSTRAP_NAME}"
    env = {
        "SCRATCH": cluster.scratch_dir, "REPO_DIR": f"{run_dir}/repo",
        "ISAAC_IMAGE": versions.isaac_image, "ARDUPILOT_TAG": versions.ardupilot_tag,
        "ARDUPILOT_DEV_IMAGE": versions.ardupilot_dev_image, "UV_VERSION": versions.uv_version,
        "OPENCV_REQUIREMENT": versions.opencv_requirement,
    }
    job_id = jobs.submit(cluster, f"{run_dir}/src/cluster/bootstrap.sh", BOOTSTRAP_NAME, env, gpu=False,
                         time_min=BOOTSTRAP_TIME_MIN)
    dest = RESULTS_ROOT / BOOTSTRAP_NAME
    try:
        jobs.wait(cluster, job_id, timeout_s=BOOTSTRAP_TIME_MIN * 60.0)
    except RemoteError:
        try:    # the log says why it failed; the job's error is the one raised
            jobs.fetch(cluster, BOOTSTRAP_NAME, dest)
            print(f"[bootstrap:run_bootstrap] Job failed, log fetched — {{dest: {dest}}}", file=sys.stderr)
        except RemoteError as fetch_error:
            print(f"[bootstrap:run_bootstrap] Job failed and the fetch failed too — {{fetch_error: {fetch_error}}}",
                  file=sys.stderr)
        raise
    jobs.fetch(cluster, BOOTSTRAP_NAME, dest)
    print(f"[bootstrap:run_bootstrap] Done — {{job_id: {job_id}, log: {dest}}}", file=sys.stderr)
    return dest
