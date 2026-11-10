#!/usr/bin/env bash
#SBATCH --job-name=flightsim-hover
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
# Closed-loop hover: ArduPilot SITL + backend/tools/sim/hover/run.py with flightsim/sim_pi.py as the physics
# process, which asks the Isaac render server (started here) for a frame at every camera exposure. Account,
# partition, GPU count, time limit and log path come from flightsim.jobs.submit.
# Results land in $run/out (small): result.json, frames.csv, camera.mp4, overlay.mp4, versions.json, *.tail.
# The bulky run directory (SITL logs, truth.npz) stays in /dev/shm and is deleted.
# Required env: SCRATCH, RUN_NAME, REPO_DIR (pushed repo holding backend/), ISAAC_IMAGE, ARDUPILOT_TAG,
#   ARDUPILOT_DEV_IMAGE, REPO_COMMIT, CAMERA, COMPUTE (profile names), HEIGHT, HOLD, SEED
# Optional env: DEBUG_KILL_RENDER_AFTER_S (kills the render server that many seconds into the run)
set -euo pipefail

: "${SCRATCH:?}" "${RUN_NAME:?}" "${REPO_DIR:?}" "${ISAAC_IMAGE:?}" "${ARDUPILOT_TAG:?}" "${ARDUPILOT_DEV_IMAGE:?}"
: "${REPO_COMMIT:?}" "${CAMERA:?}" "${COMPUTE:?}" "${HEIGHT:?}" "${HOLD:?}" "${SEED:?}"
sif_name="$(printf '%s' "${ISAAC_IMAGE#*/*/}" | tr ':/' '__').sif"
isaac_sif="$SCRATCH/containers/$sif_name"
dev_sif="$SCRATCH/containers/ardupilot-dev-base.sif"
run="$SCRATCH/runs/$RUN_NAME"
out="$run/out"
wd="$run/work"                      # render server files (small)
# WORKAROUND, not a fix (same as baseline.sbatch). ArduPilot loads lua/*.lua in directory-listing order and
# hop_takeoff.lua needs the HOP_CH parameter that hop_guard.lua creates, so guard must be listed first. tmpfs on
# these nodes lists newest first, which happens to work; the scratch filesystem's hashed order does not. This
# depends on the kernel's tmpfs listing order. The real fix is in backend/lua (or run.py's copy order).
shm="/dev/shm/flightsim-${SLURM_JOB_ID:-$$}"
state="/tmp/isaac-${SLURM_JOB_ID:-$$}"
mkdir -p "$out" "$wd" "$shm/rec"
rm -f "$wd/ready"

server=""
runner=""
status=0

# Kill a process group, then anything that carries this job's tmpfs directory in its command line
# (run.py starts SITL and physics in sessions of their own).
kill_group() { [[ -z "$1" ]] || kill -KILL -- "-$1" 2>/dev/null || true; }
cleanup() {
  kill_group "$runner"
  kill_group "$server"
  pkill -KILL -f "$shm" 2>/dev/null || true
  # Evidence first, even for a failed or killed run.
  cp "$shm/rec/frames.csv" "$shm/rec/camera.mp4" "$shm/rec/overlay.mp4" "$out/" 2>/dev/null || true
  cp "$shm/hover/result.json" "$out/" 2>/dev/null || true
  for f in "$shm/hover/run.log" "$shm/hover/physics.log" "$shm/hover/sitl.log" "$wd/render_server.log"; do
    [[ -f "$f" ]] && tail -n 200 "$f" > "$out/$(basename "$f").tail" || true
  done
  rm -rf "$shm" "$state"
}
trap cleanup EXIT
trap 'exit 143' TERM INT

export APPTAINER_CACHEDIR="$SCRATCH/.apptainer/cache"
export PYTHONPATH="$run/src:$REPO_DIR/backend:$REPO_DIR/backend/companion:$REPO_DIR/backend/tools/sim:$REPO_DIR/backend/tools/sim/hover"
py="$SCRATCH/venv/bin/python"
layout_dir="$REPO_DIR/backend/companion/stickers_218x200"
model="$REPO_DIR/backend/tools/sim/hover/model.json"

nvidia-smi --query-gpu=name,driver_version --format=csv,noheader

# What produced the results. No host names or paths.
isaac_digest="$(apptainer inspect --labels "$isaac_sif" | sed -n 's/^org.opencontainers.image.base.digest: //p')"
ardupilot_commit="$(git -C "$SCRATCH/ardupilot" rev-parse HEAD)"
ISAAC_DIGEST="$isaac_digest" ARDUPILOT_COMMIT="$ardupilot_commit" "$py" - "$out/versions.json" <<'PY'
import json, os, sys
keys = {
    "isaac_image": "ISAAC_IMAGE", "isaac_digest": "ISAAC_DIGEST", "ardupilot_dev_image": "ARDUPILOT_DEV_IMAGE",
    "ardupilot_tag": "ARDUPILOT_TAG", "ardupilot_commit": "ARDUPILOT_COMMIT", "repo_commit": "REPO_COMMIT",
    "camera_profile": "CAMERA", "compute_profile": "COMPUTE",
}
data = {name: os.environ[var] for name, var in keys.items()}
data["seed"] = int(os.environ["SEED"])
data["height_m"] = float(os.environ["HEIGHT"])
data["hold_s"] = float(os.environ["HOLD"])
json.dump(data, open(sys.argv[1], "w"), indent=1)
PY

read -r lid_w lid_h < <("$py" -m flightsim.lid_texture "$layout_dir" 1 "$wd/lid.png")
# The physics model's lens position (model.json camera.cam_pos) decides where the occluders sit.
read -r mount_x mount_y mount_z < <("$py" -m flightsim.drone_geometry "$model")

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
  mkdir -p "$state$d"
  binds+=(--bind "$state$d:$d")
done

setsid apptainer exec --nv --env ACCEPT_EULA=Y --env OMNI_KIT_ACCEPT_EULA=YES \
  "${binds[@]}" --bind "$run:/run-dir" \
  "$isaac_sif" /isaac-sim/python.sh -u /run-dir/src/isaac/render_server.py \
  --camera "/run-dir/src/profiles/cameras/$CAMERA.json" --lid-png /run-dir/work/lid.png \
  --lid-size-m "$lid_w" "$lid_h" --port 0 --ready-file /run-dir/work/ready \
  --mount-mm "$mount_x" "$mount_y" "$mount_z" > "$wd/render_server.log" 2>&1 &
server=$!

# The first render compiles shaders (about 4.5 minutes) after Isaac starts, so 300 s is not enough; allow 20 minutes.
for _ in $(seq 1 240); do
  [[ -s "$wd/ready" ]] && break
  kill -0 "$server" 2>/dev/null || break
  sleep 5
done
if [[ ! -s "$wd/ready" ]]; then
  echo "[hover] render server not ready (exited or 20 minutes passed); log tail:" >&2
  tail -n 40 "$wd/render_server.log" >&2 || true
  exit 1
fi

# run.py: the baseline's arguments (fin_nom1) with the rendered camera in place of the noise model.
setsid apptainer exec --bind "$SCRATCH" --bind /dev/shm --env ARDUPILOT="$SCRATCH/ardupilot" \
  "$dev_sif" bash -c \
  "set -euo pipefail; cd '$REPO_DIR/backend'
   '$py' tools/sim/hover/run.py --name hover --height '$HEIGHT' --hold '$HOLD' --seed '$SEED' \
     --parm tools/tune_v6.parm --set camera.tilt_attitude_lag_s=0.06 --set 'camera.pi_cam_pos_err=[0,0,0]' \
     --p SIM_ACC1_RND=0.8 --p SIM_ACC2_RND=0.8 --runs '$shm' \
     --physics '$run/src/flightsim/sim_pi.py' \
     --physics-arg=--render-ready-file --physics-arg '$wd/ready' \
     --physics-arg=--camera --physics-arg '$run/src/profiles/cameras/$CAMERA.json' \
     --physics-arg=--compute --physics-arg '$run/src/profiles/compute/$COMPUTE.json' \
     --physics-arg=--layout --physics-arg '$layout_dir/lid_layout.json' \
     --physics-arg=--record-dir --physics-arg '$shm/rec'" &
runner=$!

# Watch the render server while the run lives: with it gone the physics process dies, SITL waits for it
# forever and run.py waits in FC time, so nothing would ever end by itself.
started=$SECONDS
killed=0
while kill -0 "$runner" 2>/dev/null; do
  if [[ -n "${DEBUG_KILL_RENDER_AFTER_S:-}" && "$killed" -eq 0 && $((SECONDS - started)) -ge "$DEBUG_KILL_RENDER_AFTER_S" ]]; then
    echo "[hover] debug: killing the render server" >&2
    kill_group "$server"
    killed=1
  fi
  if ! kill -0 "$server" 2>/dev/null; then
    echo "[hover] render server exited during the run; ending it" >&2
    kill_group "$runner"
    pkill -KILL -f "$shm" 2>/dev/null || true
    status=1
    break
  fi
  sleep 2
done
rc=0
wait "$runner" 2>/dev/null || rc=$?
[[ "$status" -ne 0 ]] || status=$rc
runner=""

# The client sends quit when it can; if it died first, the server must not hold the GPU until the time limit.
for _ in $(seq 1 30); do
  kill -0 "$server" 2>/dev/null || break
  sleep 1
done

if grep -qE 'hop_takeoff\.lua|arming refused' "$shm/hover/result.json" 2>/dev/null; then
  echo "[hover] Lua scripts loaded in the wrong order on this node: hop_takeoff.lua needs a parameter hop_guard.lua creates, and ArduPilot loads scripts in directory-listing order." >&2
  [[ "$status" -ne 0 ]] || status=1
fi
grep -q '"status": "ok' "$shm/hover/result.json" 2>/dev/null || {
  echo "[hover] run did not end with status ok" >&2
  [[ "$status" -ne 0 ]] || status=1
}
exit "$status"
