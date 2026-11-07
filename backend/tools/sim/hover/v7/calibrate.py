"""Calibration grid: compare v6 motion with log49, before choosing v7 gains."""
import json
from pathlib import Path
from experiment import config
H=Path(__file__).resolve().parent
rows=[]
for scale in (1.,1.25,1.5):
 for delay in (.025,.030,.035):
  rows.append(config(f'v7cal_k{scale}_d{delay}',extra={'inertia':[.2022007/scale,.24194888/scale,.103],'motor_delay':delay}))
(H/'calibration.json').write_text(json.dumps(rows,indent=2)+'\n')
