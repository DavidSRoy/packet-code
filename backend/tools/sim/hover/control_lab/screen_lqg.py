import json
from pathlib import Path
from screen import run
H=Path(__file__).resolve().parent
rows=[]
for name,args in [('nominal',{}),('weak',{'K':50}),('strong',{'K':100}),('slow',{'delay':.045,'tau':.025}),('fast',{'delay':.02,'tau':.01}),('noisy',{'noise':.01})]:
    for effort in (.001,.01,.1,1.):
        for rate_cost in (0.,.001,.01):
            r=run('lqg',effort=effort,rate_cost=rate_cost,**args)
            r.update(case=name,effort=effort,rate_cost=rate_cost);rows.append(r)
    good=sorted([r for r in rows if r['case']==name and r['status']=='stable'],key=lambda r:r['angle_rms_deg'])
    print(name,good[:2],flush=True)
(H/'lqg_screen.json').write_text(json.dumps(rows,indent=2)+'\n')
