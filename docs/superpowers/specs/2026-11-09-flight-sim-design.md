# Flight sim for camera and compute experiments: design

Date: 2026-11-09. Status: approved in conversation, not yet planned.

## Intent

Give the team one repeatable way to test cameras, compute boards and vision
code on a simulated delivery mission before buying or flying hardware. A person
sets up a mission, the conditions and the hardware in a web app, presses Run,
and gets back what the camera saw and how the vision code did.

The earlier image-level tool (`vision-sim/`) does not meet this. It scores
generic markers on 2D-approximated frames, with no flight, no drone motion and
no real camera physics. It also overlaps `backend/tools/sim/lid_camera_sim.py`.
This design replaces it as the main sim. What happens to `vision-sim/` is an
open item below.

## What the team already has (the sim must fit this)

| Thing | Where | Role in the sim |
|---|---|---|
| ArduCopter 4.7.2, Pixhawk 6X, Holybro X650 | `backend/README.md` | The sim flies ArduPilot SITL, not PX4 |
| pymavlink only, no ROS 2 | `backend/requirements.txt` | The sim speaks MAVLink like the real drone |
| Box-lid tag localizer (centre ArUco 4x4_50, four corner AprilTag 36h11), sends `VISION_POSITION_ESTIMATE` | `backend/companion/lid_tags.py`, `cam_stream.py`, `imu_pose.py`, `stickers/lid_layout.json` | The vision code under test |
| Camera-only hover, Lua guards, pads and taught routes | `backend/ground_control/hop.py`, `autonomy.py`, `backend/lua/` | Mission format and flight behaviour to reuse |
| Arducam OV9281: 1280x800, mono, global shutter, 70 deg HFOV | `backend/companion/README.md` | First camera profile |
| Raspberry Pi Zero 2 W, about 5 detections per second | `backend/companion/README.md` | First compute profile |
| Servo gripper, land then release | `backend/companion/README.md` | Land-and-detach drop-off |
| X650 SITL physics model with fitted parameters, real flight logs | `backend/tools/sim/hover/`, `tools/sim/x650.json` | Vehicle model and tuning data |

## Goals (first version)

1. **Web app is the tool.** A teammate clones the repo, starts the app on their
   own machine and opens it on localhost. No hosted service, no shared server.
2. **Connect to the GPU cluster from the app.** The cluster uses interactive
   login, so the app never handles credentials. The user runs one `ssh <cluster-alias>` in a terminal, which
   opens a shared SSH connection (ControlMaster). The app reuses it, shows
   whether it is live, and shows the one command to run when it is not.
3. **Mission.** Hub -> vendor -> customer in a service-area model. The drone
   starts at the dispatch hub. The user places one vendor spot and one customer
   spot, and for each sets what it looks like (surface, surroundings,
   obstacles).
   - **Pickup at the vendor.** The box sits at the vendor spot. The drone lands
     on it using the lid tags and the gripper grabs it. The gripper is
     physically modelled (jaws, contact, a grab can fail). The box then rides
     with the drone and adds its mass.
   - **Hand-off at the customer**, set per location:
     - **land-and-detach**: descend, land, release, take off
     - **hover-and-release**: hold a hover at a set height for a set dwell, then
       release. Height and dwell are per-spot settings.
   - **Transit** between spots is flown on simulated GPS by the existing
     mission code (`autonomy.py` / `flyto.py`). Near each spot the flight
     controller switches to the vision position source, as `hop.py` does.
     The switch height is a setting; default it from the tag range in
     `backend/companion/README.md`.
4. **Conditions.** Time of day and sun angle, cloud cover, fog, rain, wind and
   gusts.
5. **Hardware profiles.** Camera (OV9281 first, plus at least one alternative
   to compare) and compute (Pi Zero 2 W first). Compute is modelled as that
   board's measured detection rate and delay applied to the vision pipeline.
6. **Run.** One Slurm job on RT-capable GPUs. Isaac Sim, in
   NVIDIA's container under Apptainer, renders the world and the camera.
   ArduPilot SITL flies the X650. **The vision code steers the drone.**
   The team's companion pipeline (`lid_tags.py` for detection, `imu_pose.py`
   and the `VISION_POSITION_ESTIMATE` sender in `cam_stream.py`) runs on the
   rendered frames and feeds the flight controller over MAVLink, unmodified
   except for a sim frame source. A worse camera or slower compute must be
   able to cause a worse landing. Every run also logs the vision estimate
   against sim truth.
7. **Results in the app.**
   - raw camera video, and the same video with detections drawn on it
   - per-frame image quality: sharpness, noise, overexposed fraction, motion
     blur, pixels on the lid
   - detection rate and position error by height
   - touchdown error or hover-hold error at each spot
   - 3D flight track, planned against flown
   - mission summary
8. **Repeatable.** Every test the app saves is also a plain file in the repo. A
   teammate can open it and rerun it on their own account. GPU rendering is
   not bit-identical across nodes, so "same result" means the same seed, the
   same pinned container and versions (all recorded in the results), and
   headline metrics within a stated tolerance. Test files can be reviewed in a
   pull request.
9. **Results record everything; views are configurable.** The run stores all
   outputs. The app lets each person choose what to look at. First-version
   views are aimed at camera and compute experiments.

## Non-goals (first version)

Failure injection, a weather go/no-go chart, power estimates, a real companion
board in the loop, a live 3D view during a run, sweeps over many scenarios, and
a model of the real service area.

## Anti-goals

- **Precise-looking numbers from guessed specs.** Every camera and compute
  profile records whether each value was measured or taken from a datasheet,
  and results show that next to the numbers.
- **Publishing locations.** This repo is public. Real hub, vendor and customer
  locations, and cluster host names, never go in the repo, in test files, or in
  screenshots.
- **A fork of the flight code.** The sim runs the code in `backend/` as it is.
  If the sim needs a change there, it is a small seam (such as a frame source),
  not a copy.

## Constraints

- **Public repo.** The repo ships the tool and a made-up demo area. The real
  area loads from a private folder outside the repo. Cluster host, account and
  partition names live in an untracked local config; the repo carries only an
  example file.
- **Cluster access.** Interactive login only, per user. The shared
  connection lasts about an hour. Jobs keep running without it; only the app's
  status checks and result downloads need it.
- **GPUs.** Isaac Sim needs RT cores. The GPUs are shared with others.
  Jobs must be short and safe to rerun.
- **Storage.** Persistent storage is limited. The container and
  caches (tens of GB) go on scratch space and must be re-creatable by one
  command. Results are copied back to the user's machine.
- **Mac.** Isaac Sim does not run on the Mac. The Mac runs only the web app.
- **Repo conventions.** Strict typing, one component per file, errors as
  `[Module:Function] Description — {context}`.

## Decided

| Decision | By |
|---|---|
| Isaac Sim on the cluster, not Gazebo or the image-level tool | User |
| Web app run locally is the tool; it also sets job parameters | User |
| Saved tests are also files in the repo | User (confirmed my proposal) |
| Mission is hub -> vendor -> customer, with configurable spots | User |
| Both hand-off methods, set per location | User |
| First version targets camera and compute experiments | User |
| ArduPilot, to match the hardware | User |
| Vision code steers the drone near each spot (closed loop) | User |
| Pickup is landing on the box and gripping it; gripper physically modelled; user supplies the gripper and box models | User |
| App reuses the user's SSH shared connection, never handles passwords | Me, confirmed |
| Demo area in the repo, real area outside it | Me, confirmed |
| Results after the job finishes, no live view | Me, confirmed |

## Calls made after the builder check (mine, not the user's)

- Transit on simulated GPS with the existing mission code; vision takes over
  near each spot. GPS error is not modelled in the first version.
- "Same result" means within tolerance with pinned versions, not bit-identical.
- The camera is rendered only near the spots. Transit runs physics without
  rendering, so a run stays short. Size the demo area so a full mission is a
  few minutes of flight and a job fits well inside 30 minutes.
- The hover hand-off routine starts from `hop.py`'s camera hover and lives on
  the sim side first. Moving it into `backend/` is a later request.
- The comparison camera is the Logitech C920, since `backend/tools/sim/`
  already has data for it. It is rolling shutter, so the camera profile needs
  a shutter type and readout time.
- The gripper and box models arrive from the user in an unknown CAD format and
  need converting to USD. Until they arrive, build against a stand-in box with
  the real lid layout and a simple attach, behind the same interface.

## Left to the builder

- **How ArduPilot SITL joins Isaac Sim.** Pegasus Simulator's ArduPilot backend,
  or the JSON physics interface that `backend/tools/sim/hover/` already uses.
  Trial both on the cluster first; this is the first task and the biggest risk.
  If neither works on the installed Isaac version, stop and report.
- **Isaac Sim version**, chosen by what the ArduPilot bridge supports.
- **How the demo area is built**: a small procedural block, or OpenStreetMap
  buildings over flat ground. It only has to look plausible.
- **How the real area would load** (photoreal 3D tiles or OSM plus elevation).
  The first version only needs the private-folder seam, not the importer.
- **Web app stack.** Follow what the repo already uses where sensible
  (`landing/` is Next.js; `backend/ground_control/` is a Python server with a
  static page). A small local server is needed to run `ssh` and `sbatch`.
- **Test file format** and where test files and results live.
- **How weather is rendered** in Isaac (fog volumes, rain particles, sun and
  sky) and which lens effects are post-render.
- **Image-quality metric definitions.**
- **What happens to `vision-sim/`**: keep as a quick local check, fold its
  effects into the post-render pass, or drop it.

## Risks

1. The ArduPilot to Isaac bridge is the least proven piece, and closed-loop
   vision makes lockstep timing between Isaac and SITL mandatory.
2. Cluster GPUs are shared; a run may queue.
3. Sim camera output is only as good as the profile. The OV9281 profile should
   be checked against a few real frames from the drone before results are
   trusted.
4. Gripper contact physics may need tuning before grabs behave like the real
   one; there is no real grab data in the repo to tune against.
5. `hop.py` assumes real-time. The sim must run in step with ArduPilot's clock
   or the vision timing is meaningless.
