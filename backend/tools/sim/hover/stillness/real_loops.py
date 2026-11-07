"""Inspect commanded motion and position-loop terms in log49's fixed-target window."""
import json,sys
from pathlib import Path
import numpy as np
from pymavlink import mavutil
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent))
from compare import band
root=H.parents[3]
m=mavutil.mavlink_connection(str(root/'logs/pi/bin/00000049.BIN'))
rows={k:[] for k in ('ANG','PIDN','PIDE')}
while (x:=m.recv_match(type=list(rows))) is not None:
    if 150.369345<=x.TimeUS/1e6<=161.505510:
        rows[x.get_type()].append(x.to_dict())
out={}
for axis in ('Roll','Pitch'):
    a=np.array([[r[axis],r['Des'+axis]] for r in rows['ANG']])
    out[axis.lower()]={'actual_ptp_deg':float(np.ptp(a[:,0])),
                      'commanded_ptp_deg':float(np.ptp(a[:,1])),
                      'tracking_error_rms_deg':float(np.sqrt(np.mean((a[:,0]-a[:,1])**2)))}
(H/'real_command_motion.json').write_text(json.dumps(out,indent=2)+'\n')
out={}
for key in ('PIDN','PIDE'):
    a=np.array([[r['TimeUS']/1e6,r['P'],r['I']] for r in rows[key]])
    t=np.arange(a[0,0],a[-1,0],.0025);o={}
    for j,name in ((1,'P'),(2,'I')):
        # Small-angle equivalent for comparison, not a roll/pitch coordinate transform.
        x=np.degrees(np.interp(t,a[:,0],a[:,j])/9.80665)
        o[name]={'equivalent_tilt_std_deg':float(x.std()),
                 'slow_band_rms_deg':band(x,400,.15,.7),
                 'rocking_band_rms_deg':band(x,400,1,3)}
    o['P_I_correlation']=float(np.corrcoef(a[:,1],a[:,2])[0,1]);out[key]=o
(H/'real_position_loop.json').write_text(json.dumps(out,indent=2)+'\n')
