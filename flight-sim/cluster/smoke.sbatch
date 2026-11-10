#!/usr/bin/env bash
#SBATCH --job-name=flightsim-smoke
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
# Account, partition, GPU count, time limit and log path come from flightsim.jobs.submit.
# Required env: SCRATCH, RUN_NAME, ISAAC_IMAGE
set -euo pipefail

: "${SCRATCH:?}" "${RUN_NAME:?}" "${ISAAC_IMAGE:?}"
sif_name="$(printf '%s' "${ISAAC_IMAGE#*/*/}" | tr ':/' '__').sif"
sif="$SCRATCH/containers/$sif_name"
run="$SCRATCH/runs/$RUN_NAME"
mkdir -p "$run/out"

# Isaac writes caches, logs and data under /isaac-sim; the image is read-only, so bind
# node-local writable dirs over each of them.
state="/tmp/isaac-${SLURM_JOB_ID}"
trap 'rm -rf "$state"' EXIT
dirs=(
  "/isaac-sim/.cache"
  "/isaac-sim/.nv/ComputeCache"
  "/isaac-sim/kit/cache"
  "/isaac-sim/.nvidia-omniverse/logs"
  "/isaac-sim/.nvidia-omniverse/config"
  "/isaac-sim/.local/share/ov/data"
  "/isaac-sim/.local/share/ov/pkg"
)
binds=()
for d in "${dirs[@]}"; do
  host="$state$d"
  mkdir -p "$host"
  binds+=(--bind "$host:$d")
done

export APPTAINER_CACHEDIR="$SCRATCH/.apptainer/cache"
export APPTAINER_TMPDIR="$SCRATCH/.apptainer/tmp"

nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
apptainer exec --nv --env ACCEPT_EULA=Y --env OMNI_KIT_ACCEPT_EULA=YES \
  "${binds[@]}" --bind "$run:/run-dir" \
  "$sif" /isaac-sim/python.sh -u /run-dir/src/cluster/smoke_render.py /run-dir/out
