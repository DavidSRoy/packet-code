"""Held-out torque/noise realizations, controller fitted from separate probe runs."""
import json
from pathlib import Path
from screen import run
H=Path(__file__).resolve().parent
out=[]
for fit in json.loads((H/'identification.json').read_text()):
    plant=fit['truth'];estimated=fit['estimate']
    for effort in (.001,.01):
        r=run('lqg',seed=41+fit['seed'],effort=effort,rate_cost=.001,controller_model=estimated,**plant)
        r.update(identified_model=estimated,calibration_seed=fit['seed'],effort=effort,rate_cost=.001)
        out.append(r)
(H/'identified_validation.json').write_text(json.dumps(out,indent=2)+'\n')
for effort in (.001,.01):
    a=[r for r in out if r['effort']==effort];ok=[r for r in a if r['status']=='stable']
    print('effort',effort,'stable',len(ok),'/',len(a),'range RMS',[min(r['angle_rms_deg'] for r in ok),max(r['angle_rms_deg'] for r in ok)],'range ptp',[min(r['angle_ptp_deg'] for r in ok),max(r['angle_ptp_deg'] for r in ok)],'max output',max(r['output_max'] for r in ok))
