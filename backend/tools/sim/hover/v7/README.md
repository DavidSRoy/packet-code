# v7 simulation-only development

**Stillness requirement update:** v7 does not meet the user’s absolute, visually imperceptible
hover goal. It remains an experimental baseline. See `../stillness/RESULTS.md`.

No command in this directory connects to the physical vehicle. The existing v6 remains
installed. This work uses `logs/pi/bin/00000049.BIN` and the matching Pi camera recording
`20261106-205327`. The log49 parameter snapshot is `../flown_log49.parm`.

Run from `backend`, using Python with `requirements.txt` plus scipy for the fit:

```sh
uv run --with-requirements requirements.txt --with scipy python tools/sim/hover/v7/fit.py
uv run --with-requirements requirements.txt python tools/sim/hover/v7/experiment.py
uv run --with-requirements requirements.txt python tools/sim/hover/batch.py tools/sim/hover/v7/search.json --jobs 5
uv run --with-requirements requirements.txt python tools/sim/hover/v7/calibrate.py
uv run --with-requirements requirements.txt python tools/sim/hover/batch.py tools/sim/hover/v7/calibration.json --jobs 5
uv run --with-requirements requirements.txt python tools/sim/hover/v7/validate.py
uv run --with-requirements requirements.txt python tools/sim/hover/batch.py tools/sim/hover/v7/validation.json --jobs 8
```

Do not run batches concurrently: they reuse local SITL instance ports. Each run name is
overwritten by the runner. Raw BIN and truth trajectories stay in ignored `../runs/`.

## Model fitting and limitations

The rate fit integrates measured RATE angular velocity over 20 ms and regresses against
lagged, integrated RATE control output plus a constant disturbance. It searches lag
2–40 ms and delay 0–60 ms; train 150–180 s, validation 180–205 s. `fit.json` preserves
coefficients and validation scores. The 5%-loss parameter ranges are sensitivity ranges,
not statistical confidence intervals. This is closed-loop data: noise and feedback can
bias the gain, and delay includes gyro filtering. It cannot uniquely identify the plant.

The raw fit substantially overpredicts the observed 1–3 Hz wobble in SITL. It is retained
as a weak-response stress case, not silently accepted as ground truth. The calibration
grid checks v6 with effective gain 1–1.5 times the regression gain and pure delay 25–35 ms.
The final nominal model is selected against the measured stationary window
150.369345–161.505510 s, comparing high-rate ANG spectra and position tracking.
The old model and raw regression model remain validation scenarios.

`model_overrides.json` is separate from the old `model.json`; original v6 simulation
results remain reproducible. Effective inertia represents the fitted torque response,
not a new CAD mass estimate. Camera processing median comes from the latest recording;
its large latency tail is tested separately, not represented by nominal Gaussian jitter.
Camera noise, force disturbances, exposure/readout delay and geometry remain inherited
assumptions, not freshly identified values. No independent physical position ground truth
is available. Simulator truth metrics and FC-estimated real metrics are distinct.

Position-loop gains and all operational failsafes are held unchanged. Search deliberately
includes rejected candidates; failures must remain in reported results. Direct runner
landing can force-disarm after descent: those runs establish hover behavior only. The
real-code e2e runner is required to establish the separate landing behavior in simulation.


## Final candidate

`tools/tune_v7.parm` retains all 25 v6 parameters, changing only `ATC_RAT_RLL_P`
and `ATC_RAT_PIT_P` from 0.22 to 0.26. Rate I/D, angle gains, vision/EKF and
position gains are unchanged. This file has **not been installed on the drone**.
A softer angle controller alone did not improve nominal motion. Raising D to 0.008
improved the nominal model but produced much worse fast rocking in the stronger-motor
case, despite staying airborne; those candidates were rejected. Passing the motor-off
guards alone is insufficient for accepting a tune.

Final-file verification commands (run sequentially; e2e instances 20–21 are isolated):

```sh
uv run --with-requirements requirements.txt python tools/sim/hover/batch.py tools/sim/hover/v7/final_validation.json --jobs 6
uv run --with-requirements requirements.txt python tools/sim/hover/v7/e2e_validation.py
uv run --with-requirements requirements.txt python tools/sim/hover/v7/test_metrics.py
uv run --with-requirements requirements.txt python -m unittest tools.test_hover_controls tools.test_flight_pipeline
uv run --with-requirements requirements.txt python -m compileall -q tools/sim/hover/v7 tools/sim/hover/run.py
uv run --with-requirements requirements.txt python tools/sim/hover/v7/summarize.py
```

See `RESULTS.md` for final measured outcomes and limitations. `results.json` preserves
compact outcomes including rejected runs; `final_validation.json` freezes the exact
11 scenarios and seeds. `refinement.json` and `conservative.json` preserve additional
candidate searches and can be run with the same batch runner.

Reference tuning guidance: https://ardupilot.org/copter/docs/initial-tuning-flight.html
(establish an oscillation-free attitude tune before further flight testing). Nothing here
qualifies the physical drone or substitutes for a controlled flight comparison.
