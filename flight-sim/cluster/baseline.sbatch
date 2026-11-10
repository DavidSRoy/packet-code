#!/usr/bin/env bash
#SBATCH --job-name=flightsim-baseline
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
# Runs the unchanged hover sim (backend/tools/sim/hover/run.py) against the SITL built by bootstrap.sh.
# Arguments are the fin_nom1 run from RESULTS.md. Runs inside the build image because arducopter
# is linked against Ubuntu libraries. Results land in $run/out.
#
# The run directory is on tmpfs on purpose. ArduPilot loads lua/*.lua in readdir order, and
# hop_takeoff.lua needs the HOP_CH parameter that hop_guard.lua creates, so guard must load first.
# That works on a sorted or newest-first listing (macOS, tmpfs on this kernel) but not on the
# hashed order of the scratch filesystem, where arming is refused with "hop_takeoff.lua:78: No p...".
# Required env: SCRATCH, RUN_NAME, REPO_DIR (pushed repo holding backend/)
set -euo pipefail

: "${SCRATCH:?}" "${RUN_NAME:?}" "${REPO_DIR:?}"
run="$SCRATCH/runs/$RUN_NAME"
work="/dev/shm/flightsim-${SLURM_JOB_ID:-$$}"
mkdir -p "$run/out" "$work"
trap 'rm -rf "$work"' EXIT

export APPTAINER_CACHEDIR="$SCRATCH/.apptainer/cache"
status=0
apptainer exec --bind "$SCRATCH" --bind /dev/shm --env ARDUPILOT="$SCRATCH/ardupilot" \
  "$SCRATCH/containers/ardupilot-dev-base.sif" bash -c \
  "set -euo pipefail; cd '$REPO_DIR/backend'
   '$SCRATCH/venv/bin/python' tools/sim/hover/run.py --name baseline --height 0.02 --hold 30 --seed 1 \
     --parm tools/tune_v6.parm --set camera.tilt_attitude_lag_s=0.06 --set 'camera.pi_cam_pos_err=[0,0,0]' \
     --p SIM_ACC1_RND=0.8 --p SIM_ACC2_RND=0.8 --runs '$work'" || status=$?
cp -r "$work/baseline" "$run/out/baseline"
cp "$work/baseline/result.json" "$run/out/result.json"
exit "$status"
