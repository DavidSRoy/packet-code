#!/usr/bin/env bash
#SBATCH --job-name=flightsim-bootstrap
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
# mksquashfs is the slow step and scales with cores; 1 CPU did not finish in 30 minutes.
# Idempotent: pull the Isaac Sim image into $SCRATCH/containers if absent.
# Run it inside a CPU job, never on the login node.
# Required env: SCRATCH (remote scratch dir), ISAAC_IMAGE (e.g. nvcr.io/nvidia/isaac-sim:6.2.0)
set -euo pipefail

: "${SCRATCH:?[bootstrap] SCRATCH is required}"
: "${ISAAC_IMAGE:?[bootstrap] ISAAC_IMAGE is required}"

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
  exit 0
fi

start=$(date +%s)
partial="$sif.partial"
rm -f "$partial"
apptainer pull "$partial" "docker://$ISAAC_IMAGE"
mv "$partial" "$sif"
echo "[bootstrap] pulled $sif in $(( $(date +%s) - start )) s"
