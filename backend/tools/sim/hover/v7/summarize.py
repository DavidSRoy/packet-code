"""Archive compact results, retaining failed runs rather than averaging them away."""
import json
from pathlib import Path
H=Path(__file__).resolve().parent
out=[]
for f in sorted((H.parent/'runs').glob('v7*/result.json')):
 r=json.loads(f.read_text())
 out.append({k:r[k] for k in ('name','seed','height','hold','parm','p','set','status','final_status','score','score_error','events_rel_s') if k in r})
(H/'results.json').write_text(json.dumps(out,indent=2)+'\n')
for group in ('v6','a6','pd'):
 rows=[r for r in out if r['name'].startswith('v7val_') and r['name'].endswith('_'+group)]
 bad=[r['name'] for r in rows if not r.get('status','').startswith('ok') or 'error' in r.get('score',{})]
 nom=[r['score'] for r in rows if 'nom' in r['name'] and r.get('score')]
 print(group,len(rows),'failures',bad)
 if nom:
  for key in ('tilt_hp_rms_deg','tilt_1_3_rms_deg','roll_ptp_deg','pitch_ptp_deg','xy_rms_mm','z_rms_mm'):
   v=[s[key] for s in nom];print(' ',key,round(sum(v)/len(v),4),[round(x,3) for x in v])
