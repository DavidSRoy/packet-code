"""Check whether restoring angle stiffness improves the damped candidate."""
import json
from pathlib import Path
from experiment import config,gains,model
H=Path(__file__).resolve().parent
nom=json.loads((H/'model_overrides.json').read_text())
rows=[]
for n,g in [('pd75',gains(p=.26,d=.008,ang=7.5)),('p30',gains(p=.30,d=.008,ang=7.5))]:
 for case,extra,seed in [('nom1',{},1),('nom2',{},2),('strong',{'inertia':[.1235,.1302,.0824],'motor_tau':.02,'motor_delay':.03},6),('weak',model,7)]:
  rows.append(config('v7ref_'+case+'_'+n,g,seed,{**nom,**extra}))
(H/'refinement.json').write_text(json.dumps(rows,indent=2)+'\n')
