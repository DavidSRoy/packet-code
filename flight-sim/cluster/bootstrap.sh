#!/usr/bin/env bash
#SBATCH --job-name=flightsim-bootstrap
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
# mksquashfs is the slow step and scales with cores; a 1-CPU job was still squashing after 16 minutes.
# Idempotent: pull the Isaac Sim image into $SCRATCH/containers, build ArduPilot SITL into
# $SCRATCH/ardupilot and create the Python venv in $SCRATCH/venv, each only if absent.
# Run it inside a CPU job, never on the login node.
# Required env: SCRATCH (remote scratch dir), ISAAC_IMAGE (e.g. nvcr.io/nvidia/isaac-sim:6.2.0),
# ARDUPILOT_TAG, ARDUPILOT_DEV_IMAGE, UV_VERSION, OPENCV_REQUIREMENT (all from versions.toml),
# REPO_DIR (pushed repo holding backend/, see jobs.push_backend)
set -euo pipefail

: "${SCRATCH:?[bootstrap] SCRATCH is required}"
: "${ISAAC_IMAGE:?[bootstrap] ISAAC_IMAGE is required}"
: "${ARDUPILOT_TAG:?[bootstrap] ARDUPILOT_TAG is required}"
: "${ARDUPILOT_DEV_IMAGE:?[bootstrap] ARDUPILOT_DEV_IMAGE is required}"
: "${UV_VERSION:?[bootstrap] UV_VERSION is required}"
: "${OPENCV_REQUIREMENT:?[bootstrap] OPENCV_REQUIREMENT is required}"
: "${REPO_DIR:?[bootstrap] REPO_DIR is required}"

sif_name="$(printf '%s' "${ISAAC_IMAGE#*/*/}" | tr ':/' '__').sif"
sif="$SCRATCH/containers/$sif_name"

export APPTAINER_CACHEDIR="$SCRATCH/.apptainer/cache"
# The SIF is assembled in APPTAINER_TMPDIR. On scratch (a network filesystem) unpacking the
# ~100k small files did not finish inside the 30 minute limit, so build on node-local /tmp.
export APPTAINER_TMPDIR="/tmp/apptainer-${SLURM_JOB_ID:-$$}"
trap 'rm -rf "$APPTAINER_TMPDIR"' EXIT
mkdir -p "$SCRATCH/containers" "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR"

if [[ -s "$sif" ]]; then
  echo "[bootstrap] already present: $sif"
else
  start=$(date +%s)
  partial="$sif.partial"
  rm -f "$partial"
  apptainer pull "$partial" "docker://$ISAAC_IMAGE"
  mv "$partial" "$sif"
  echo "[bootstrap] pulled $sif in $(( $(date +%s) - start )) s"
fi

# ArduPilot: build inside the Ubuntu dev image (the binary needs the dev image's libraries), same container runs the sim later.
dev_sif="$SCRATCH/containers/ardupilot-dev-base.sif"
if [[ ! -s "$dev_sif" ]]; then
  rm -f "$dev_sif.partial"
  apptainer pull "$dev_sif.partial" "docker://$ARDUPILOT_DEV_IMAGE"
  mv "$dev_sif.partial" "$dev_sif"
fi

ardu="$SCRATCH/ardupilot"
# The stamp records the tag the build came from; a missing or different stamp rebuilds.
if [[ -x "$ardu/build/sitl/bin/arducopter" && "$(cat "$ardu/.built-tag" 2>/dev/null)" == "$ARDUPILOT_TAG" ]]; then
  echo "[bootstrap] already built: $ardu ($ARDUPILOT_TAG)"
else
  rm -rf "$ardu"
  git clone --depth 1 --branch "$ARDUPILOT_TAG" --recurse-submodules --shallow-submodules \
    https://github.com/ArduPilot/ardupilot "$ardu"
  pydeps="$SCRATCH/pydeps"
  apptainer exec --bind "$SCRATCH" "$dev_sif" bash -c \
    "set -euo pipefail; python3 -m pip install --quiet --target '$pydeps' empy==3.3.4;
     cd '$ardu'; PYTHONPATH='$pydeps' ./waf configure --board sitl; PYTHONPATH='$pydeps' ./waf -j\$(nproc) copter"
  echo "$ARDUPILOT_TAG" > "$ardu/.built-tag"
  echo "[bootstrap] built $ardu ($ARDUPILOT_TAG)"
fi

# Managed Python only: the host python3.12 does not exist inside the build container.
export UV_PYTHON_INSTALL_DIR="$SCRATCH/uv-python"
uv_bin="$SCRATCH/bin/uv"
if [[ ! -x "$uv_bin" ]]; then
  curl -LsSf https://astral.sh/uv/$UV_VERSION/install.sh | UV_INSTALL_DIR="$SCRATCH/bin" UV_NO_MODIFY_PATH=1 sh
fi
# The marker is written only after the install succeeds, so a failed install is redone next run.
# The stamp records the OpenCV requirement the venv was built with; a missing or different stamp rebuilds.
if [[ -f "$SCRATCH/venv/.complete" && "$(cat "$SCRATCH/venv/.opencv-requirement" 2>/dev/null)" == "$OPENCV_REQUIREMENT" ]]; then
  echo "[bootstrap] already present: $SCRATCH/venv ($OPENCV_REQUIREMENT)"
else
  rm -rf "$SCRATCH/venv"
  "$uv_bin" venv --managed-python --python 3.12 "$SCRATCH/venv"
  "$uv_bin" pip install --python "$SCRATCH/venv/bin/python" \
    -r "$REPO_DIR/backend/requirements.txt" "$OPENCV_REQUIREMENT"
  echo "$OPENCV_REQUIREMENT" > "$SCRATCH/venv/.opencv-requirement"
  touch "$SCRATCH/venv/.complete"
  echo "[bootstrap] created $SCRATCH/venv ($OPENCV_REQUIREMENT)"
fi
