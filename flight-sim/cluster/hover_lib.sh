#!/usr/bin/env bash
# Functions for hover.sbatch, kept apart so tests/test_hover_lib.py can run them against fake processes.
# Sourced; expects the caller's set -euo pipefail.

# scrub_paths FILE SRC...: print FILE with every cluster-specific string (the arguments after FILE) replaced by <path>.
scrub_paths() {
  local file="$1"; shift
  local expr=() p
  for p in "$@"; do [[ -z "$p" ]] || expr+=(-e "s#$p#<path>#g"); done
  sed "${expr[@]}" "$file"
}

# watch_run: wait for the run (runner) to end by itself. Ends it (and sets status=1) when the render server, the
# physics process (sim_pi) or SITL has been gone (after it was seen alive, or never seen startup_s after launch) for grace_s seconds while run.py has not yet written its final
# "status:" line. Once that line is there the run is ending normally (processes exit on purpose, scoring may be
# slow) and nothing is killed. Also kills the render server DEBUG_KILL_RENDER_AFTER_S seconds in, if set.
# Globals: runner server shm status grace_s startup_s; needs kill_group.
watch_run() {
  local started=$SECONDS killed=0 gone_at="" dead seen_physics=0 seen_sitl=0
  while kill -0 "$runner" 2>/dev/null; do
    if [[ -n "${DEBUG_KILL_RENDER_AFTER_S:-}" && "$killed" -eq 0 && $((SECONDS - started)) -ge "$DEBUG_KILL_RENDER_AFTER_S" ]]; then
      echo "[hover] $(date +%T) debug: killing the render server" >&2
      kill_group "$server"
      killed=1
    fi
    dead=""
    kill -0 "$server" 2>/dev/null || dead="render server"
    # Physics and SITL only exist once the container, imports and run.py have started: they count as gone once seen
    # alive and then missing, or if never seen startup_s after launch.
    if pgrep -f "sim_pi.py --out $shm" >/dev/null; then seen_physics=1; elif (( seen_physics || SECONDS - started >= startup_s )); then dead="${dead:-physics process}"; fi
    if pgrep -f "bin/arducopter .*$shm" >/dev/null; then seen_sitl=1; elif (( seen_sitl || SECONDS - started >= startup_s )); then dead="${dead:-SITL}"; fi
    if [[ -n "$dead" ]] && ! grep -q '^status:' "$shm/hover/run.log" 2>/dev/null; then
      [[ -n "$gone_at" ]] || { gone_at=$SECONDS; echo "[hover] $dead is not running during the run" >&2; }
      if (( SECONDS - gone_at >= grace_s )); then
        echo "[hover] $dead still missing $grace_s s later; ending the run" >&2
        kill_group "$runner"
        pkill -KILL -f "$shm" 2>/dev/null || true
        status=1
        break
      fi
    else
      gone_at=""
    fi
    sleep 1
  done
}
