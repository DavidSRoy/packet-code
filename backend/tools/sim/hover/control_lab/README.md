# V7 control experiments — unfinished

Offline single-axis linear experiments only. These scripts do not connect to
hardware, replace ArduPilot, or qualify a controller for flight. V6 remains the
physical baseline.

## Acceptance

The user accepts **smooth gust correction, then stillness**. Brief leaning during
an externally specified gust is allowed. Settled hover retains the provisional
absolute limits: each roll/pitch/yaw axis below 0.1 degrees peak-to-peak and each
XYZ axis below 2 mm peak-to-peak for at least 20 seconds. Ordinary sustained
rocking must not be relabelled as gust response. Gust tests must report peak
displacement, recovery time and residual rocking separately. A numerical gust
recovery deadline has not yet been established.

These experiments have no position dynamics or gust-recovery qualification;
none demonstrates those requirements.

## Findings

- The fixed motor-delay predictor improves nominal motion but deteriorates or
  becomes unstable with slower actuators. It is rejected as a flight candidate.
- A simulation-only multisine probe fits actuator gain, delay and lag using a
  known independent excitation. This is not an authorized physical probe.
- LQG with models fitted from those probes stays below the bench's 25-degree
  instability cutoff in 12/12 held-out disturbance/noise runs for each of two
  control-effort weights. This is a finite-run screen, not proof of stability.
- With effort weight 0.001, peak-to-peak angle is 0.217–0.476 degrees; maximum
  normalized output reaches 0.310. With weight 0.01, motion is 0.315–0.592
  degrees and maximum output 0.060. **Both fail the 0.1-degree target.** Physical
  mixer authority and motor headroom have not been tested.

The reference PID is an approximation, not bit-exact ArduPilot. Sensor noise is
independent and simplified; real AHRS correlations, outer-loop commands, yaw,
thrust coupling, motor mixing, saturation allocation and camera outages are
absent. No improvement percentage here establishes a real-flight improvement.

`force_batches.py` inspects sparse high-rate accelerometer windows from log 49.
Its force residual is sensitive to alignment and calibration and is averaged
over short windows separated by gaps. It is not independent continuous force
ground truth and must not justify reducing disturbance strength just to pass.

## Reproduce

From `backend`, with requirements plus SciPy installed:

```sh
python -m unittest discover -s tools/sim/hover/control_lab -p 'test_*.py'
python tools/sim/hover/control_lab/screen.py
python tools/sim/hover/control_lab/identify_probe.py
python tools/sim/hover/control_lab/screen_lqg.py
python tools/sim/hover/control_lab/validate_identified.py
```

JSON files retain failed cases as well as successful finite-run screens.
