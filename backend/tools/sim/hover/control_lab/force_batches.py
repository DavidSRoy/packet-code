"""Horizontal force-residual diagnostic from raw/post-filter accelerometer batches.
Window means avoid treating downsampled motor vibration as low-frequency forcing.
Not a complete or independently validated disturbance identification.
"""
import json
from pathlib import Path
import numpy as np
from pymavlink import mavutil
H=Path(__file__).resolve().parent;root=H.parents[3]
m=mavutil.mavlink_connection(str(root/'logs/pi/bin/00000049.BIN'))
headers={};chunks={};rates=[]
while (x:=m.recv_match(type=['ISBH','ISBD','RATE'])) is not None:
    if x.get_type()=='ISBH':headers[x.N]=x.to_dict()
    elif x.get_type()=='ISBD':chunks.setdefault(x.N,{})[x.seqno]=np.array([x.x,x.y,x.z],float).T
    else:rates.append([x.TimeUS/1e6,x.R,x.P,x.Y])
rates=np.array(rates);omega=np.radians(rates[:,1:]);alpha=np.column_stack([np.gradient(omega[:,i],rates[:,0]) for i in range(3)])
rows=[];lever=np.array([-.007,-.001,-.058]);axis_xy=np.array([.0153,.004])
for n,h in headers.items():
    if h['type']!=0 or h['instance'] not in (0,3):continue
    sample_start=h['SampleUS']/1e6
    if not 148<=sample_start<=216:continue
    parts=chunks.get(n,{})
    if not parts or sorted(parts)!=list(range(len(parts))):continue
    acc=np.concatenate([parts[i] for i in sorted(parts)])[:h['smp_cnt']]/h['mul']
    if len(acc)!=h['smp_cnt']:continue
    t=sample_start+np.arange(len(acc))/h['smp_rate'];window=np.hanning(len(acc));window/=window.sum()
    w=np.column_stack([np.interp(t,rates[:,0],omega[:,i]) for i in range(3)])
    a=np.column_stack([np.interp(t,rates[:,0],alpha[:,i]) for i in range(3)])
    cg=acc-np.cross(a,lever)-np.cross(w,np.cross(w,lever))
    residual=cg[:,:2]+cg[:,2,None]*axis_xy
    rows.append({'t':float((t*window).sum()),'instance':h['instance'],
        'residual_body_xy_mps2':(residual*window[:,None]).sum(0).tolist(),
        'accel_cg_mean_mps2':(cg*window[:,None]).sum(0).tolist()})
values=np.array([r['residual_body_xy_mps2'] for r in rows])
out={'source':'00000049.BIN','window_start_s':148,'window_end_s':216,'batches':len(rows),
 'batch_window_s':1024/3208.2,'lever_frd_m':lever.tolist(),'assumed_thrust_axis_xy':axis_xy.tolist(),
 'residual_centered_std_mps2':values.std(0).tolist(),
 'caveat':'Sparse ~0.32 s batches cannot reconstruct a continuous force history or identify its spectrum. Lever geometry, thrust alignment, filtering and sensor calibration are assumed; residual is not independent external-force ground truth.',
 'rows':rows}
(H/'force_batches.json').write_text(json.dumps(out,indent=2)+'\n')
print({k:v for k,v in out.items() if k!='rows'})
