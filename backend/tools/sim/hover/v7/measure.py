"""Compare identical 11.136 s stationary windows using ANG (400 Hz), not ATT (10 Hz)."""
import json,sys
from pathlib import Path
import numpy as np
from pymavlink import mavutil
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent))
from compare import band

def measure(path,start,end):
 m=mavutil.mavlink_connection(str(path)); rows=[]; pos={k:[] for k in ('PSCN','PSCE','PSCD')}
 while (x:=m.recv_match(type=['ANG',*pos])) is not None:
  t=x.TimeUS/1e6
  if start<=t<=end:
   if x.get_type()=='ANG': rows.append([t,x.Roll,x.Pitch,x.DesRoll,x.DesPitch])
   else:
    ax=x.get_type()[-1]; pos[x.get_type()].append(getattr(x,'TP'+ax)-getattr(x,'P'+ax))
 a=np.array(rows); fs=1/np.median(np.diff(a[:,0])); out={}
 for i,n in enumerate(['roll','pitch','desired_roll','desired_pitch'],1):
  out[n]={'std_deg':float(a[:,i].std()),'ptp_deg':float(np.ptp(a[:,i])), 'band_1_3_deg':band(a[:,i],fs,1,3),'band_015_07_deg':band(a[:,i],fs,.15,.7)}
 out['xy_tracking_rms_mm']=float(1000*np.sqrt(sum(np.mean(np.array(pos[k])**2) for k in ('PSCN','PSCE'))))
 return out
if __name__=='__main__':
 result={'real49':measure(H.parents[3]/'logs/pi/bin/00000049.BIN',150.369345,161.505510)}
 for f in sorted((H.parent/'runs').glob(sys.argv[1]+'/result.json')):
  r=json.loads(f.read_text())
  if not r.get('status','').startswith('ok'): continue
  t=r['events']['at height']['fc_t']+5
  result[r['name']]=measure(r['dflog'],t,t+11.136165)
 print(json.dumps(result,indent=2))
