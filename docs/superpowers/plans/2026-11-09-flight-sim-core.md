# Flight Sim Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command on the Mac submits a cluster job in which ArduPilot SITL hovers the X650 over the box lid, steered by the team's own tag detector running on camera frames rendered by Isaac Sim, and brings the video and metrics back.

**Architecture:** Isaac Sim is the renderer only. The team's fitted rigid-body model (`backend/tools/sim/hover/physics.py`) stays the physics and already runs in lockstep with SITL over the JSON interface. A new camera class replaces that model's analytic lid measurement with: render the frame at the true pose in Isaac, run the real `LidFinder`, send the same `VISION_*` messages with the compute profile's delays. The physics loop blocks while a frame renders, so sim time stands still and render speed cannot change the result.

**Tech Stack:** Python 3.12 + uv, numpy, opencv >= 4.12, pymavlink, pytest (Mac side). Isaac Sim NGC container under Apptainer, ArduPilot SITL (JSON backend), Slurm (cluster side).

**Spec:** `docs/superpowers/specs/2026-11-09-flight-sim-design.md`. This plan covers the sim core only. The mission (hub, vendor, customer, gripper), the web app and the results views each get their own plan after this one works; they depend on what Tasks 2 and 6 find.

**Where to run it:** a fresh worktree branched from `origin/master` (this plan was written on a branch that predates `backend/`). Cherry-pick the spec and plan commits into it. Open a draft PR first.

## Global Constraints

- The repo is public. No cluster host names, account names, partition names, user names, real coordinates or addresses in code, docs, commit messages, PR text or screenshots. They live in the untracked `flight-sim/cluster.local.toml`.
- Strict typing: no `Any`, no `typing.cast`. Errors read `[Module:Function] Description — {context}`. No silent fallbacks.
- `backend/` changes are limited to the three seams named in Tasks 5, 7 and 8. No copies of backend code.
- Cluster: one GPU per job, jobs finish inside 30 minutes, container and builds live under the scratch dir and are re-creatable by `flight-sim/cluster/bootstrap.sh`.
- Every profile value carries a provenance of `measured`, `datasheet` or `estimate`.
- Conventional commits, no attribution lines, never push without the user saying so.
- New code lives in `flight-sim/`; Python package `flightsim`; tests in `flight-sim/tests/`, run with `uv run pytest -q -W error`.

## Review Focus

1. **A frame takes longer than 1 s to render.** SITL resends its servo packet; the physics must not step twice for one `frame_count`. (Task 8)
2. **No tags in view** (too high, off-frame, occluded by the jaws). No vision message is sent, nothing crashes, and `frames.csv` records the frame as not detected so the result shows why the drone lost position. (Task 7)
3. **The render server dies or never becomes ready.** The run fails within 60 s with a clear error and leaves no orphan SITL or physics process on the node. (Task 8)
4. **The shared SSH connection has expired.** Every Mac-side command fails at once with the one command to run, never a hanging password prompt. (Task 1)
5. **Scratch was purged.** A missing container or ArduPilot build is detected before `sbatch`, with the bootstrap command in the error. (Task 8)

---

### Task 1: Scaffold, cluster config, SSH helper

**Files:**
- Create: `flight-sim/pyproject.toml`, `flight-sim/.python-version` (3.12), `flight-sim/.gitignore` (`.venv/`, `results/`, `cluster.local.toml`), `flight-sim/cluster.example.toml`
- Create: `flight-sim/flightsim/__init__.py`, `flight-sim/flightsim/config.py`, `flight-sim/flightsim/remote.py`
- Test: `flight-sim/tests/test_config.py`, `flight-sim/tests/test_remote.py`

**Interfaces:**
- Produces:
  - `Cluster(ssh_alias: str, account: str, gpu_partition: str, cpu_partition: str, scratch_dir: str)` frozen dataclass
  - `load_cluster(path: Path | None = None) -> Cluster` (default `flight-sim/cluster.local.toml`)
  - `connection_live(cluster: Cluster) -> bool`
  - `ssh(cluster: Cluster, command: str, *, timeout_s: float = 60.0) -> str` (stdout)
  - `class RemoteError(RuntimeError)`

- [ ] **Step 1: Write failing tests**

```python
def test_load_cluster_reads_all_fields(tmp_path): ...  # writes a toml, asserts each field
def test_load_cluster_missing_file_names_example(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"\[config:load_cluster\].*cluster\.example\.toml"):
        load_cluster(tmp_path / "nope.toml")
def test_load_cluster_missing_key_names_key(tmp_path): ...  # match=r"scratch_dir"
def test_ssh_argv_is_batch_mode(monkeypatch):
    # monkeypatch subprocess.run, assert argv starts ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", alias]
def test_ssh_exit_255_says_how_to_connect(monkeypatch):
    with pytest.raises(RemoteError, match=r"\[remote:ssh\] No live connection — run: ssh my-alias"): ...
def test_connection_live_uses_control_check(monkeypatch):  # argv == ["ssh", "-O", "check", alias]
```

- [ ] **Step 2: Run, expect import errors.** `cd flight-sim && uv run pytest -q -W error`
- [ ] **Step 3: Implement `config.py` and `remote.py`.** `tomllib` for config. `ssh` raises `RemoteError` on exit 255 and on any non-zero exit (`[remote:ssh] Command failed — {exit, stderr tail}`).
- [ ] **Step 4: Tests pass.**
- [ ] **Step 5: Write `cluster.example.toml`** with placeholder values (`ssh_alias = "my-cluster"` etc.) and a one-line comment per key. Create the real `cluster.local.toml` locally from the user's values; confirm `git status` does not show it.
- [ ] **Step 6: Commit** `feat(flight-sim): scaffold with cluster config and ssh helper`

### Task 2: Isaac Sim on the cluster renders one frame

This is the first gate. It decides the Isaac version every later task uses.

**Files:**
- Create: `flight-sim/cluster/bootstrap.sh`, `flight-sim/cluster/smoke_render.py`, `flight-sim/cluster/smoke.sbatch`, `flight-sim/versions.toml`
- Create: `flight-sim/flightsim/jobs.py`
- Test: `flight-sim/tests/test_jobs.py`

**Interfaces:**
- Consumes: `Cluster`, `ssh`
- Produces:
  - `versions.toml` keys: `isaac_image` (e.g. `nvcr.io/nvidia/isaac-sim:6.2.0`), `ardupilot_tag`
  - `push_source(cluster: Cluster, run_name: str) -> str` (remote dir `<scratch>/runs/<run_name>/src`, via `git archive HEAD | ssh ... tar x`)
  - `submit(cluster: Cluster, script: str, run_name: str, env: Mapping[str, str]) -> int` (job id, parsed from `sbatch --parsable`)
  - `wait(cluster: Cluster, job_id: int, *, poll_s: float = 15.0, timeout_s: float = 2400.0) -> str` (final Slurm state)
  - `fetch(cluster: Cluster, run_name: str, dest: Path) -> Path` (rsync `<scratch>/runs/<run_name>/out/` to `dest`)

- [ ] **Step 1: Failing tests for `jobs.py`** with `ssh`/`subprocess.run` monkeypatched: `submit` builds `sbatch --parsable -A <account> -p <gpu_partition> --gpus=1 --time=30 --export=ALL,K=V...` and returns the int; `wait` returns `"COMPLETED"` after polling `sacct`/`squeue`, raises `RemoteError` naming the state for `FAILED`, `TIMEOUT`, `CANCELLED`, `PREEMPTED`; `run_name` containing anything outside `[A-Za-z0-9_.-]` raises `ValueError`.
- [ ] **Step 2: Implement `jobs.py`; tests pass.**
- [ ] **Step 3: Write `bootstrap.sh`** (runs on the cluster, idempotent, takes `SCRATCH` and `ISAAC_IMAGE`): `apptainer pull` the image to `$SCRATCH/containers/` if absent, with `APPTAINER_CACHEDIR` and `APPTAINER_TMPDIR` on scratch. Run it inside a CPU job, not on the login node.
- [ ] **Step 4: Write `smoke_render.py`** (Isaac standalone, headless): empty stage, ground plane, one cube, one distant light, a 1280x800 camera 2 m above looking down, render, write `out/smoke.png`, print the Isaac version and GPU name. `smoke.sbatch` runs it with `apptainer exec --nv --env ACCEPT_EULA=Y` and writable binds for Isaac's cache, log and data dirs pointed at node-local `/tmp`.
- [ ] **Step 5: Run it.** Submit, wait, fetch. Expected: `COMPLETED`, and `smoke.png` is 1280x800 with a visible cube (mean pixel between 20 and 235, standard deviation above 10).
- [ ] **Step 6: If the newest image fails on the node's GPU driver**, retry with `isaac-sim:5.1.0`. Record the image that works in `versions.toml` with a one-line comment giving the failure seen. If neither renders, stop and report BLOCKED with the log tail.
- [ ] **Step 7: Commit** `feat(flight-sim): cluster bootstrap and smoke render`

### Task 3: ArduPilot SITL on the cluster reproduces the existing hover sim

**Files:**
- Modify: `flight-sim/cluster/bootstrap.sh`, `flight-sim/versions.toml`
- Create: `flight-sim/cluster/baseline.sbatch`

**Interfaces:**
- Produces: on the cluster, `$SCRATCH/ardupilot` (with `build/sitl/bin/arducopter`) and `$SCRATCH/venv` (Python 3.12 via uv with `backend/requirements.txt` plus `opencv-python-headless>=4.12`). Later sbatch scripts export `ARDUPILOT=$SCRATCH/ardupilot`.

- [ ] **Step 1: Confirm the tag.** `backend/README.md` says ArduCopter 4.7.2. Run `git ls-remote --tags https://github.com/ArduPilot/ardupilot 'Copter-4.7*'`. If `Copter-4.7.2` is missing, or the team flies a patched tree, stop and ask which commit to build.
- [ ] **Step 2: Extend `bootstrap.sh`**: clone the tag with submodules, build inside an Ubuntu build container pulled with Apptainer (`ardupilot/ardupilot-dev-base`), `./waf configure --board sitl && ./waf copter`. `empy==3.3.4` in the build environment. Install uv and create the venv.
- [ ] **Step 3: `baseline.sbatch`** (CPU partition) runs the existing sim unchanged: `python backend/tools/sim/hover/run.py` with the arguments from the "reproduce" section of `backend/tools/sim/hover/RESULTS.md`, output to `out/`.
- [ ] **Step 4: Run it.** Expected: `result.json` has `status` starting `ok` and `score.xy_rms_mm` below 10 (RESULTS.md reports 4.0 to 5.7).
- [ ] **Step 5: Commit** `feat(flight-sim): build ArduPilot SITL on the cluster and run the hover baseline`

### Task 4: Frame conventions, render link, profiles

Pure Python, tested on the Mac.

**Files:**
- Create: `flight-sim/flightsim/frames.py`, `flight-sim/flightsim/render_link.py`, `flight-sim/flightsim/profiles.py`
- Create: `flight-sim/profiles/cameras/ov9281.json`, `flight-sim/profiles/compute/pi-zero-2w.json`
- Test: `flight-sim/tests/test_frames.py`, `test_render_link.py`, `test_profiles.py`

**Interfaces:**
- Produces:
  - `Vec3 = tuple[float, float, float]`, `Quat = tuple[float, float, float, float]` (w, x, y, z)
  - `camera_pose_world(p_ned: Vec3, q_body_to_ned: Quat, cam_pos_frd: Vec3, mount_rot_deg: float = 0.0) -> tuple[Vec3, Quat]`. World is north-west-up metres (x = N, y = -E, z = -D), origin at the lid top centre. The quaternion orients a USD camera (looks along its -Z, +Y is image up) so it looks along body down with image top toward the nose.
  - `RenderClient(host: str, port: int, *, timeout_s: float = 120.0)` with `render(pos: Vec3, quat: Quat, t: float) -> NDArray[np.uint8]` (shape `(h, w)`) and `close()`
  - `serve(render_fn: Callable[[Vec3, Quat, float], NDArray[np.uint8]], port: int, ready_file: Path) -> None` (blocks until a quit request; writes the bound port to `ready_file` once listening)
  - Wire format: request is one JSON line `{"pos":[x,y,z],"quat":[w,x,y,z],"t":1.25}` or `{"op":"quit"}`. Response is `struct "<III"` (width, height, frame_id) then `width*height` bytes.
  - `CameraProfile(name, width, height, hfov_deg, mono, shutter, provenance)`, `ComputeProfile(name, rate_hz, exposure_to_readout_s, detect_s, detect_jitter_s, link_s, detect_scale, provenance)`; `load_camera(path) -> CameraProfile`, `load_compute(path) -> ComputeProfile`. `provenance: Mapping[str, Literal["measured", "datasheet", "estimate"]]`.

- [ ] **Step 1: Failing tests**

```python
def test_level_camera_looks_down_with_north_up():
    pos, q = camera_pose_world((0, 0, -1.0), (1, 0, 0, 0), (0, 0, 0))
    assert pos == pytest.approx((0, 0, 1.0))
    assert rotate(q, (0, 0, -1)) == pytest.approx((0, 0, -1))   # view axis is world down
    assert rotate(q, (0, 1, 0)) == pytest.approx((1, 0, 0))     # image up is north
def test_yaw_east_turns_image_up_east():   # yaw +90 deg: image up == (0, -1, 0)
def test_lever_arm_moves_camera_forward(): # cam_pos_frd (0.127, 0, 0.101), level, at 1 m: pos == (0.127, 0, 0.899)
def test_render_round_trip():              # serve() in a thread with a stub returning a ramp image; client gets identical bytes; frame_id increments
def test_render_client_times_out_with_context():  # no server reply -> TimeoutError matching r"\[render_link:render\]"
def test_server_rejects_bad_request():     # malformed JSON -> connection closed, server keeps serving the next client
def test_every_profile_field_has_provenance():    # for both shipped profiles, set(provenance) == set(numeric fields)
def test_profile_unknown_provenance_raises():
```

- [ ] **Step 2: Implement; tests pass.**
- [ ] **Step 3: Write the profiles.** `ov9281.json`: 1280, 800, hfov 70, mono true, shutter `global`; all `datasheet`. `pi-zero-2w.json`: `rate_hz` 10, `exposure_to_readout_s` 0.06, `detect_s` 0.05, `detect_jitter_s` 0.004, `link_s` 0.005, `detect_scale` 0.4; all `measured` (source: `backend/tools/sim/hover/IDENT.md`).
- [ ] **Step 4: Commit** `feat(flight-sim): frame conventions, render link and hardware profiles`

### Task 5: Make the companion's pose math importable (backend seam 1)

`lid_pose` and `imu_fix` sit inside `backend/companion/cam_stream.py`, which opens a camera and starts servers at import. The sim needs the same math without that.

**Files:**
- Create: `backend/companion/lid_pose.py`
- Modify: `backend/companion/cam_stream.py` (the bodies of `lid_pose` at ~134-165 and `imu_fix` at ~196 move out; `cam_stream.py` calls the new module)
- Test: `flight-sim/tests/test_lid_pose.py`

**Interfaces:**
- Produces: `backend/companion/lid_pose.py` with `Mount(fwd_m: float, right_m: float, down_m: float, rot_deg: float)`, `lid_pose(r: dict, mount: Mount) -> dict` and `imu_fix(r: dict, att: tuple[float, float, float] | None, K: np.ndarray, imu: ImuPose, mount: Mount) -> dict`. Return keys are exactly what `cam_stream.py` produces today (`drone_m`, `camera_m`, `yaw_deg`, `tilt_deg`, `range_m`, `pose`, ...). Module globals the old bodies read become these parameters; nothing else changes.

- [ ] **Step 1: Failing test.** Use the team's own 2D renderer as the oracle: build `backend/tools/sim/lid_camera_sim.Scene`, render the lid from a known drone pose (0.5 m up, 30 mm off, yaw 10 deg), run `LidFinder.find`, pass the result through `lid_pose`, assert `drone_m` is within 5 mm of truth. Second case with a 5 deg tilt and the true attitude through `imu_fix`: within 5 mm and `pose == "imu"`.
- [ ] **Step 2: Run, expect ImportError.**
- [ ] **Step 3: Move the two bodies.** `cam_stream.py` keeps thin wrappers that pass its globals. `companion/setup.sh` installs `*.py`, so the new file deploys with no change there; confirm by reading it.
- [ ] **Step 4: Tests pass.** Also `python -m py_compile backend/companion/cam_stream.py`.
- [ ] **Step 5: Commit** `refactor(companion): move lid pose math into an importable module`

This task touches code that runs on the drone. Flag it in the PR for the hardware owner to review; it cannot be flight-tested here.

### Task 6: Isaac render server and the lid scene

Second gate: the real detector must recover the true pose from Isaac frames.

**Files:**
- Create: `flight-sim/flightsim/lid_texture.py`, `flight-sim/isaac/scene.py`, `flight-sim/isaac/render_server.py`, `flight-sim/cluster/truth_check.sbatch`, `flight-sim/flightsim/truth_check.py`
- Test: `flight-sim/tests/test_lid_texture.py`, `flight-sim/tests/test_truth_check.py`

**Interfaces:**
- Consumes: `serve`, `RenderClient`, `camera_pose_world`, `CameraProfile`, `lid_pose`
- Produces:
  - `write_lid_texture(layout_dir: Path, box: int, out_png: Path, px_per_mm: float = 6.0) -> tuple[float, float]` (returns sticker width, height in metres). Built from `lid_camera_sim.sticker_raster`.
  - `render_server.py --camera <profile.json> --lid-png <png> --lid-size-m W H --port 0 --ready-file <path> [--sun-elevation-deg 60]`
  - `pose_grid() -> list[TruthPose]` and `check(frames_dir: Path) -> list[TruthResult]` in `truth_check.py`

- [ ] **Step 1: Failing Mac tests.** `write_lid_texture` output decodes with `LidFinder` when viewed head-on (warp it into a synthetic 1280x800 frame at 0.5 m); `pose_grid()` has heights 0.3, 0.5, 1.0, 2.0, 3.0 m crossed with offsets and yaws; `check` on frames from the 2D oracle renderer passes its own thresholds.
- [ ] **Step 2: Implement `lid_texture.py` and `truth_check.py`; tests pass.** Default layout: `backend/companion/stickers_218x200`, box 1.
- [ ] **Step 3: `scene.py`** builds: concrete-like ground at z = -box_height, a box whose top face is the lid (225.6 x 206.4 mm) at z = 0 with the sticker texture centred on it, a dome light plus a sun at the given elevation, and a camera from the profile (focal length and aperture chosen so HFOV matches; square pixels). Under a `drone` transform that moves with the camera, add matte cuboids for the gripper housing, both jaws, battery plate and the two landing legs, using the dimensions in `backend/tools/sim/lid_camera_sim.py:38-43` converted from that file's frame (x nose, y left, z up, mm).
- [ ] **Step 4: `render_server.py`** builds the scene, renders two warm-up frames, then calls `serve(render_fn, ...)`. `render_fn` sets the camera rig pose, renders, returns the frame as 8-bit grey. Use the camera API of the Isaac version chosen in Task 2.
- [ ] **Step 5: `truth_check.sbatch`** starts the server, renders every pose in `pose_grid()` through `RenderClient`, saves PNGs plus a contact sheet, runs `check`.
- [ ] **Step 6: Run it.** Expected, with zero tilt: every pose at or below 1.0 m detected with position error under 5 mm; at 2.0 and 3.0 m detected with error under 2 % of range. Fetch the contact sheet and look at it: sticker upright, jaws and legs where `lid_camera_sim` draws them.
- [ ] **Step 7: Commit** `feat(flight-sim): Isaac render server with the lid scene and truth check`

### Task 7: Rendered-frame companion

**Files:**
- Create: `flight-sim/flightsim/sim_pi.py`, `flight-sim/flightsim/recorder.py`
- Modify: `backend/tools/sim/hover/physics.py` only if `Camera` needs a hook to override the measurement (backend seam 2; keep it to one overridable method)
- Test: `flight-sim/tests/test_sim_pi.py`, `flight-sim/tests/test_recorder.py`

**Interfaces:**
- Consumes: `physics.Camera`, `RenderClient` (or any object with the same `render` method), `LidFinder`, `ImuPose`, `lid_pose`, `imu_fix`, `CameraProfile`, `ComputeProfile`
- Produces:
  - `class RenderedCamera(physics.Camera)`: at each exposure it takes the true pose, renders, detects, and hands the pose to the parent's existing send path with the compute profile's delays in place of `model.json`'s camera block. No detection means no message for that frame.
  - `sim_pi.py` is runnable the way `e2e/fake_pi.py` is (sets `physics.Camera`, calls `physics.main()`), with extra args `--render-ready-file`, `--camera`, `--compute`, `--layout`, `--record-dir`.
  - `Recorder(record_dir: Path, fps: float)` with `add(frame: NDArray[np.uint8], row: FrameRow) -> None` and `close()`. Writes `camera.mp4`, `overlay.mp4` (tag outlines and estimate drawn) and `frames.csv` with columns `frame,t_exposure,detected,tags,est_x,est_y,est_z,true_x,true_y,true_z,err_xy_mm`.

- [ ] **Step 1: Failing tests** with a stub renderer backed by `lid_camera_sim.Scene.render`:

```python
def test_estimate_matches_truth_over_lid():        # pose 0.5 m up -> sent position within 5 mm of truth
def test_no_tags_sends_nothing_and_records_row():  # pose 20 m up -> no send, frames.csv row has detected == 0
def test_compute_profile_delay_is_applied():       # send time - exposure time == 0.06 + 0.05 + 0.005 (jitter seeded to 0)
def test_attitude_comes_from_parent_lagged_truth() # imu_fix receives the attitude physics.Camera already models
def test_recorder_writes_three_files_and_closes():
```

- [ ] **Step 2: Implement.** The attitude passed to `imu_fix` is the lagged true attitude the parent class already computes. `# ponytail: true attitude with lag, not the FC's estimate; switch to ATTITUDE from the MAVLink link if estimator error matters`.
- [ ] **Step 3: Tests pass.**
- [ ] **Step 4: Commit** `feat(flight-sim): companion that detects on rendered frames`

### Task 8: Closed-loop hover job and the `hover` command

Third gate: the hover is steered by vision on Isaac frames.

**Files:**
- Modify: `backend/tools/sim/hover/run.py` (backend seam 3: `--physics PATH`, default the existing `physics.py`, plus pass-through `--physics-arg`)
- Modify: `backend/tools/sim/hover/physics.py` if Step 1 shows a double step (ignore a servo packet whose `frame_count` equals the last one handled)
- Create: `flight-sim/cluster/hover.sbatch`, `flight-sim/flightsim/__main__.py`, `flight-sim/flightsim/hover.py`
- Test: `flight-sim/tests/test_lockstep.py`, `flight-sim/tests/test_hover_cli.py`

**Interfaces:**
- Consumes: everything above
- Produces: `uv run python -m flightsim hover --camera ov9281 --compute pi-zero-2w --height 0.5 --hold 30 --seed 0 [--name NAME]`, which runs `preflight`, `push_source`, `submit`, `wait`, `fetch` and prints the results folder. `preflight(cluster: Cluster) -> None` raises `RemoteError` when the container, ArduPilot build or venv is missing: `[hover:preflight] Missing on scratch — {path}; run: bash flight-sim/cluster/bootstrap.sh`.

- [ ] **Step 1: Failing lockstep test (Mac, no SITL).** Start the physics main loop on a free port with a camera whose render sleeps 1.5 s. A fake SITL sends servo packet `frame_count=7`, then the same packet again, then `frame_count=8`. Assert exactly two replies and that the reply timestamps differ by one step.
- [ ] **Step 2: Fix until it passes** (the guard in `physics.py` if needed).
- [ ] **Step 3: Failing CLI tests** with `jobs` monkeypatched: call order is preflight, push, submit, wait, fetch; missing scratch path raises the preflight error before `submit`; a dead SSH connection raises the Task 1 error before anything else.
- [ ] **Step 4: Implement `hover.py`, `__main__.py`; tests pass.**
- [ ] **Step 5: `hover.sbatch`**: start `render_server.py` in the Isaac container; wait up to 300 s for the ready file, else exit 1 with the server log tail; run `run.py --physics flight-sim/flightsim/sim_pi.py ...` in the venv with `ARDUPILOT` set; `trap` kills the render server and all children on any exit. Write `versions.json` (container image and digest, ArduPilot commit, repo commit, seed, profile names).
- [ ] **Step 6: Run the gate.** `hover --height 0.5 --hold 30 --seed 0`. Expected: `result.json` `status` starts `ok`; `score.xy_rms_mm` below 15; `frames.csv` shows `detected == 1` on more than 95 % of hold-window frames; `overlay.mp4` shows the lid with outlines tracking it.
- [ ] **Step 7: Kill test.** Rerun with the render server killed 10 s in (a debug env var in the sbatch). Expected: job ends within 60 s, non-zero, and `squeue` shows nothing left.
- [ ] **Step 8: Commit** `feat(flight-sim): closed-loop hover on Isaac frames with one command`

### Task 9: Repeatability, a worse camera, README

**Files:**
- Create: `flight-sim/profiles/cameras/ov9281-quarter.json` (320x200, same lens; every field `estimate`; a test fixture, named as such in the file), `flight-sim/README.md`
- Create: `flight-sim/flightsim/compare.py`
- Test: `flight-sim/tests/test_compare.py`

**Interfaces:**
- Produces: `compare(a: Path, b: Path) -> dict[str, float]` (differences in `xy_rms_mm`, `xy_max_mm`, detection rate) and `python -m flightsim compare A B`.

- [ ] **Step 1: Failing test, implement `compare`, tests pass.**
- [ ] **Step 2: Repeatability.** Run the Task 8 gate twice with the same seed. Expected: `xy_rms_mm` differs by less than 2 mm, detection rate by less than 2 points. Record the measured differences in the README as the stated tolerance.
- [ ] **Step 3: Worse camera.** Run with `--camera ov9281-quarter`. Expected: a clearly worse outcome than the full-resolution run (lower detection rate, larger `xy_rms_mm`, or a kill). If it is not worse, report that as a finding; do not tune until it is.
- [ ] **Step 4: README.** What this is, the one-time setup (copy `cluster.example.toml`, connect, bootstrap), the `hover` and `compare` commands, where results land, what each output file is, known limits (attitude source, no weather yet, no motion blur or rolling shutter, one lid layout), and the three numbers from Steps 2 and 3. No host names.
- [ ] **Step 5: Full suite** `uv run pytest -q -W error`, then commit `docs(flight-sim): README with repeatability and camera comparison results`

---

## Not in this plan

Mission legs and GPS transit, vendor and customer spots, the physically modelled gripper, hover-and-release, weather and lighting conditions, the C920 profile and rolling shutter, per-frame image-quality metrics, the web app, and the service-area model. Each is a later plan built on the `hover` command and the render server.

The gripper will need contact physics. This plan keeps the drone's motion in the team's fitted model and uses Isaac only to render. When the gripper plan starts, decide whether Isaac's physics engine simulates only the jaws and box around a drone that is moved by the fitted model, or takes over the airframe too.
