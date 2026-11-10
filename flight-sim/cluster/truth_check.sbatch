#!/usr/bin/env bash
#SBATCH --job-name=flightsim-truth
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
# Isaac renders the lid at every pose in flightsim.truth_check.pose_grid(); the real detector must recover
# each pose. Exits non-zero when any pose fails. Results land in $run/out (frames/, contact-sheet.png,
# truth-results.json). Account, partition, GPU count, time limit and log path come from flightsim.jobs.submit.
# Required env: SCRATCH, RUN_NAME, ISAAC_IMAGE, REPO_DIR (pushed repo holding backend/)
# Optional env: RENDERER, SUBFRAMES (render_server defaults otherwise)
set -euo pipefail

: "${SCRATCH:?}" "${RUN_NAME:?}" "${ISAAC_IMAGE:?}" "${REPO_DIR:?}"
sif_name="$(printf '%s' "${ISAAC_IMAGE#*/*/}" | tr ':/' '__').sif"
sif="$SCRATCH/containers/$sif_name"
run="$SCRATCH/runs/$RUN_NAME"
out="$run/out"
mkdir -p "$out"

# Isaac writes caches, logs and data under /isaac-sim; the image is read-only, so bind
# node-local writable dirs over each of them.
state="/tmp/isaac-${SLURM_JOB_ID}"
server=""
cleanup() {
  [[ -z "$server" ]] || kill "$server" 2>/dev/null || true
  rm -rf "$state"
}
trap cleanup EXIT
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
export PYTHONPATH="$run/src:$REPO_DIR/backend:$REPO_DIR/backend/companion:$REPO_DIR/backend/tools/sim"
py="$SCRATCH/venv/bin/python"
layout_dir="$REPO_DIR/backend/companion/stickers_218x200"

nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
read -r lid_w lid_h < <("$py" -m flightsim.lid_texture "$layout_dir" 1 "$out/lid.png")

rm -f "$out/ready"
apptainer exec --nv --env ACCEPT_EULA=Y --env OMNI_KIT_ACCEPT_EULA=YES \
  "${binds[@]}" --bind "$run:/run-dir" \
  "$sif" /isaac-sim/python.sh -u /run-dir/src/isaac/render_server.py \
  --camera /run-dir/src/profiles/cameras/ov9281.json --lid-png /run-dir/out/lid.png \
  --lid-size-m "$lid_w" "$lid_h" --port 0 --ready-file /run-dir/out/ready \
  ${RENDERER:+--renderer "$RENDERER"} ${SUBFRAMES:+--subframes "$SUBFRAMES"} &
server=$!

# The first render compiles shaders (about 4.5 minutes); allow 20.
for _ in $(seq 1 240); do
  [[ -s "$out/ready" ]] && break
  kill -0 "$server" 2>/dev/null || { echo "[truth_check] render server exited before it was ready" >&2; exit 1; }
  sleep 5
done
[[ -s "$out/ready" ]] || { echo "[truth_check] render server not ready after 20 minutes" >&2; exit 1; }

status=0
"$py" -m flightsim.truth_check --port "$(cat "$out/ready")" --out "$out" --layout-dir "$layout_dir" || status=$?
# The client sends quit when it can; if it died first, the server must not hold the GPU until the time limit.
for _ in $(seq 1 30); do
  kill -0 "$server" 2>/dev/null || break
  sleep 1
done
kill "$server" 2>/dev/null || true
wait "$server" 2>/dev/null || true
server=""
exit "$status"
