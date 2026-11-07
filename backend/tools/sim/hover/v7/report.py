"""Build the final report only after every final scenario has a scored result."""
import json
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent
R=H.parent/'runs'
cfg=json.loads((H/'final_validation.json').read_text())
final=[json.loads((R/c['name']/'result.json').read_text()) for c in cfg]
for r in final:
 assert r['status'].startswith('ok') and 'score' in r and 'error' not in r['score'],r['name']
base={r['name']:r for r in [json.loads((R/c['name']/'result.json').read_text()) for c in json.loads((H/'validation.json').read_text()) if c['name'].endswith('_v6')]}
nom=[r for r in final if 'nom' in r['name']]
old=[base[r['name'].replace('v7final_','v7val_')[:-3]+'_v6'] for r in nom]
def avg(rows,k):return float(np.mean([r['score'][k] for r in rows]))
lines=['# v7: simulation-only hover tuning','', '**Status: candidate tested in simulation; not installed or flown on the drone.**','',
'Only roll/pitch rate P changes, from **0.22 to 0.26**. The other 23 v6 parameters, angle gains, position controller and operational failsafes remain unchanged. The parameter file is `tools/tune_v7.parm`.', '',
'## Paired nominal results','',
'Three identical-seed comparisons, 10 cm hover, 30 s commanded hold (28 s scored after settling). Values below are simulator truth, not measured v7 flight performance.','',
'| Metric | v6 mean | v7 mean | Change |','|---|---:|---:|---:|']
for key,label in [('tilt_1_3_rms_deg','1–3 Hz rocking RMS, combined roll/pitch (°)'),('tilt_hp_rms_deg','Rocking above 1 Hz RMS (°)'),('roll_ptp_deg','Roll peak-to-peak (°)'),('pitch_ptp_deg','Pitch peak-to-peak (°)'),('xy_rms_mm','Horizontal position RMS (mm)'),('z_rms_mm','Vertical position RMS (mm)')]:
 a,b=avg(old,key),avg(nom,key);lines.append(f'| {label} | {a:.3f} | {b:.3f} | {100*(b/a-1):+.1f}% |')
lines+=['','![Paired nominal simulation comparison](v7-simulation.png)','','## Robustness results','','Each row uses the same seed and disturbance model for v6 and v7. “Completed” refers to hover plus the direct runner’s descent; that runner subsequently force-disarms and is not the landing validation.','','| Case | v6 rocking >1 Hz (° RMS) | v7 rocking (° RMS) | v6 XY RMS (mm) | v7 XY RMS (mm) |','|---|---:|---:|---:|---:|']
for r in final:
 n=r['name'].removeprefix('v7final_').removesuffix('_v7');b=base['v7val_'+n+'_v6'];s=r['score'];q=b['score'];lines.append(f"| {n} | {q['tilt_hp_rms_deg']:.3f} | {s['tilt_hp_rms_deg']:.3f} | {q['xy_rms_mm']:.2f} | {s['xy_rms_mm']:.2f} |")
lines+=['','Scenarios: nominal seeds 1–3; 2 cm hover; old plant; stronger motors; raw weak-response fit; increased processing/readout delay; camera noise; a 0.3 m/s² one-second gust; slower motors. See `final_validation.json` for exact values. These are separate stress cases, not exhaustive combinations.','',
'## Real-code landing checks','']
for n in ('nominal','camera_loss'):
 r=json.loads((R/('v7e2e_final_'+n)/'result.json').read_text());assert r['final_status']['state']=='done'
 e=r['events_rel_s'];lines.append(f"- **{n}:** {r['final_status']['reason']}. Landing began {e['descend']:.2f} s after press; FC disarmed at {e['disarmed']:.2f} s. The simulator ran at {r['sim_over_wall']:.3f}× wall time.")
lines+=['- Both use the actual ground-control server/hover code and the exact v7 file. All 25 candidate parameters were read back from each SITL DataFlash log and matched. Camera loss is a two-second blackout; the existing 0.5-second timeout requests LAND. No physical vehicle was connected by these tests.','',
'## Fit to the latest flight','',
'Log 49 is the latest substantial v6 flight; log 50 is too short for a comparable steady hover. The archive still ends at log 50. `fit.json` includes the log49 SHA256 and matching camera-recording timing statistics.','',
'The motor-response regression uses 150–180 s for fitting and 180–205 s for validation. Holdout R² is only 0.25 on roll and 0.47 on pitch. The raw estimate is not a uniquely identified physical plant: closed-loop disturbances and sensor filtering bias it. It overpredicts wobble when applied directly, so it is retained as a stress case.','',
'The calibrated nominal model uses effective torque-response gains of approximately 73.5/73.7 rad/s² per control unit, 15 ms motor lag and 30 ms pure delay. Its effective inertias are 0.1618/0.1613 kg·m²; these are response-equivalent values, not measured CAD inertias. Camera processing median is 68.7 ms versus the old 50 ms assumption. The measured 153.5 ms processing p95 is exercised in the latency stress case rather than claimed as a fitted nominal distribution.','',
'Calibration uses a fixed-target 11.136 s window (150.369345–161.505510 s), high-rate ANG spectra and position tracking. Real 1–3 Hz tilt RMS is 0.189° roll / 0.187° pitch; nominal seed-1 v6 simulation gives 0.182° / 0.222°. Its FC-estimated XY error is 3.53 mm versus real 4.57 mm, so the simulator still understates that measurement by about 23%. Matching one spectrum is calibration, not independent validation. Camera noise, geometry, force disturbances and exposure latency remain inherited assumptions.','',
'## Rejected candidates','',
'- Reducing angle P alone to 6 slightly worsened nominal rocking and position hold.',
'- Raising rate D from 0.006 to 0.008 improved nominal rocking but produced approximately 1.14° RMS rocking in the stronger-motor case, versus 0.21° with v6. Staying airborne was not enough to pass.',
'- Softer rate P or reduced D in the weak-response search triggered the simulated tilt motor-off guard. All rejected outcomes remain in `results.json`; they are not averaged out.','',
'## Verification and limits','',
'- 11/11 exact-v7-file hover scenarios completed and produced scores; both final-file real-code landing checks completed with FC disarm.',
'- Synthetic known-motion test: 1 passed; hover controls and flight pipeline: 26 passed. Python compilation passed. No configured static Python type checker was run.',
'- The original simulator model and v6 parameter file are preserved. No production flight-control code or live parameters were changed.',
'- This reduces simulated wobble; it does **not** establish a rock-still physical hover. Prop/frame flexibility, thermal effects, hardware vibration and long-duration flights are not qualified. No independent external position ground truth is available.',
'- Physical v7 performance and transfer of the predicted improvement remain unverified. The next physical comparison needs the same height, targets, battery/payload configuration and a sufficiently long stationary hold; compare ANG/RATE spectra and position error with log49.','',
'Reproduction: `README.md`; exact models/configurations and compact outcomes are kept beside this report. Tuning reference: [ArduPilot initial tuning](https://ardupilot.org/copter/docs/initial-tuning-flight.html).','']
(H/'RESULTS.md').write_text('\n'.join(lines))
print('\n'.join(lines[:20]))
