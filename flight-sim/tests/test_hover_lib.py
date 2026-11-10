import subprocess
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "cluster" / "hover_lib.sh"

# Fakes carry the command lines hover_lib.sh looks for; they are built from pieces so this script's own text never matches.
HARNESS = r"""
set -euo pipefail
source "$LIB"
shm="$1"; mode="$2"
mkdir -p "$shm/hover"
kill_group() { [[ -z "$1" ]] || kill -KILL "$1" 2>/dev/null || true; }
fake() { ( exec -a "$1" sleep 60 >/dev/null 2>&1 ) & echo $!; }
status=0; grace_s=2; startup_s=3
server=$(fake "render_server.py"); pids=("$server")
case "$mode" in
  all_alive|status_line|physics_missing|sitl_missing|physics_dies)
    [[ "$mode" == physics_missing ]] || pids+=("$(fake "sim_pi.py"" --out $shm/hover/truth.npz")")
    [[ "$mode" == sitl_missing ]] || pids+=("$(fake "x/bin/arducopter"" -w --defaults $shm/hover/flown.parm")")
    ;;
  sitl_late)
    pids+=("$(fake "sim_pi.py"" --out $shm/hover/truth.npz")")
    startup_s=8
    ( sleep 4; ( exec -a "x/bin/arducopter -w --defaults $shm/hover/flown.parm" sleep 60 >/dev/null 2>&1 ) ) &
    ;;
esac
[[ "$mode" != physics_dies ]] || ( sleep 1; kill "${pids[1]}" ) &
[[ "$mode" != status_line ]] || { pids=("$server"); kill "${pids[0]}"; echo "status: ok" > "$shm/hover/run.log"; }
if [[ "$mode" == all_alive || "$mode" == status_line || "$mode" == sitl_late ]]; then ( sleep 4 ) & else ( sleep 30 ) & fi
runner=$!
start=$SECONDS
watch_run
wait "$runner" 2>/dev/null || true
echo "status=$status elapsed=$((SECONDS - start))"
kill "${pids[@]}" 2>/dev/null || true
pkill -f "$shm" 2>/dev/null || true
"""


def _watch(tmp_path: Path, mode: str) -> tuple[int, int]:
    result = subprocess.run(
        ["bash", "-c", HARNESS, "harness", str(tmp_path), mode],
        capture_output=True, text=True, timeout=60, env={"LIB": str(LIB), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
    )
    assert result.returncode == 0, result.stderr
    fields = dict(part.split("=") for part in result.stdout.split()[-2:])
    return int(fields["status"]), int(fields["elapsed"])


def test_run_that_ends_by_itself_with_everything_alive_is_not_touched(tmp_path: Path) -> None:
    status, elapsed = _watch(tmp_path, "all_alive")
    assert status == 0 and 4 <= elapsed <= 6


def test_missing_physics_process_ends_the_run_after_the_grace(tmp_path: Path) -> None:
    status, elapsed = _watch(tmp_path, "physics_missing")
    assert status == 1 and 2 <= elapsed < 10


def test_physics_that_dies_after_being_seen_ends_the_run_after_the_grace(tmp_path: Path) -> None:
    status, elapsed = _watch(tmp_path, "physics_dies")
    assert status == 1 and 3 <= elapsed < 10


def test_process_that_starts_late_but_inside_the_startup_allowance_is_not_killed(tmp_path: Path) -> None:
    status, elapsed = _watch(tmp_path, "sitl_late")
    assert status == 0 and 4 <= elapsed <= 6


def test_missing_sitl_ends_the_run_after_the_grace(tmp_path: Path) -> None:
    status, elapsed = _watch(tmp_path, "sitl_missing")
    assert status == 1 and 2 <= elapsed < 10


def test_everything_gone_after_the_final_status_line_is_a_normal_end(tmp_path: Path) -> None:
    status, elapsed = _watch(tmp_path, "status_line")
    assert status == 0 and 4 <= elapsed <= 6


def test_scrub_paths_replaces_the_cluster_prefixes(tmp_path: Path) -> None:
    src = tmp_path / "result.json"
    src.write_text('{"flown": "/fs/user1/repo/x.parm", "dflog": "/dev/shm/flightsim-7/logs/a.BIN", "k": 1}')
    out = subprocess.run(
        ["bash", "-c", 'source "$LIB"; scrub_paths "$1" /fs/user1 /dev/shm/flightsim-7', "t", str(src)],
        capture_output=True, text=True, env={"LIB": str(LIB), "PATH": "/usr/bin:/bin"}, check=True,
    ).stdout
    assert "user1" not in out and "flightsim-7" not in out and '"k": 1' in out and "<path>/repo/x.parm" in out
