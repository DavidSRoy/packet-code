"""Absolute stillness metrics over the simulator's complete settled hold window."""
import json,sys
from pathlib import Path
import numpy as np
from acceptance import meets_target
H=Path(__file__).resolve().parent
rows=[]
for c in json.loads((H/sys.argv[1]).read_text()):
 p=H.parent/'runs'/c['name']; r=json.loads((p/'result.json').read_text())
 item={'name':c['name'],'status':r['status']}
 if not r['status'].startswith('ok'):
  rows.append(item);continue
 T=np.load(p/'truth.npz')['truth'];wm=np.loadtxt(p/'wallmap.txt');e=r['events']
 start=np.interp(e['at height']['wall'],wm[:,0],wm[:,1])+2
 end=np.interp(e['descend']['wall'],wm[:,0],wm[:,1]);s=T[(T[:,0]>=start)&(T[:,0]<=end)]
 item.update({'hold_s':float(end-start),'position_ptp_mm':(np.ptp(s[:,1:4],axis=0)*1000).tolist(),'tilt_ptp_deg':np.ptp(np.degrees(np.unwrap(s[:,7:10],axis=0)),axis=0).tolist(),'score':r['score']})
 item['meets_provisional_target']=meets_target(item['position_ptp_mm'], item['tilt_ptp_deg'], item['hold_s'])
 rows.append(item)
(H/(Path(sys.argv[1]).stem+'_metrics.json')).write_text(json.dumps(rows,indent=2)+'\n')
for r in rows:print(r['name'],r.get('position_ptp_mm'),r.get('tilt_ptp_deg'),r.get('meets_provisional_target'))

if '--require-target' in sys.argv and not all(r.get('meets_provisional_target',False) for r in rows):
    raise SystemExit(1)
