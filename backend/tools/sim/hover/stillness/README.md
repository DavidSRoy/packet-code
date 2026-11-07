# Absolute hover stillness

The user requires visually imperceptible motion. The previous v7 percentage improvement
is not acceptance of that requirement. V7 remains an experimental baseline, not a completed
stillness solution, and has not been deployed.

Provisional engineering gate (not yet a measured human-visibility threshold): at least
20 seconds of settled hold, each XYZ axis under 2 mm peak-to-peak and each roll/pitch/yaw
axis under 0.1 degree peak-to-peak. `acceptance.py` rejects short, missing, nonfinite and
out-of-range data. All axes count, including slow motion and altitude bobbing.

The diagnostic configurations are counterfactual experiments, **not parameter files to
load on hardware**. They remove sensor noise, modeled force/torque disturbances or latency
to expose limitations. The ideal-camera case also changes the FC vision delay setting to
match its synthetic timing. The ideal-all case has neither physical disturbances nor
sensor noise and is not a realistic flight prediction.

Run from backend:

```sh
uv run --with-requirements requirements.txt python tools/sim/hover/stillness/generate.py
uv run --with-requirements requirements.txt python tools/sim/hover/batch.py tools/sim/hover/stillness/diagnostics.json --jobs 5
uv run --with-requirements requirements.txt python tools/sim/hover/stillness/measure.py diagnostics.json --require-target
uv run --with-requirements requirements.txt python tools/sim/hover/batch.py tools/sim/hover/stillness/confirmation.json --jobs 5
uv run --with-requirements requirements.txt python tools/sim/hover/stillness/measure.py confirmation.json --require-target
uv run --with-requirements requirements.txt python tools/sim/hover/stillness/test_acceptance.py
```

The `--require-target` commands are expected to **exit 1** for the current results. A
successful takeoff/hover or lower RMS does not pass the absolute-motion gate.

The first nine runs are exploratory. Removing disturbance lists changes random-number
consumption, so their differences are not exact paired causal percentages. The ten
confirmation runs use two additional seeds and zero the existing disturbance amplitudes
instead of removing processes, preserving random-number draws for the remaining model
sources. Still, SITL startup timing introduces small run-to-run variation. Effects are
nonlinear and not additive. The disturbance amplitudes themselves remain inherited,
partly fitted assumptions; this does not establish a physical propeller/frame/motor fault.

See `RESULTS.md` for observations and the gap to the target. All tests use localhost SITL;
no physical flight, parameter update or service restart is performed.
