"""Measure the simulated FC sensor path against recorded physics truth.
No new physical actuator identification or flight qualification is implied.
"""
import json
from pathlib import Path
import numpy as np
from pymavlink import mavutil
from scipy.optimize import minimize_scalar
from scipy.signal import lfilter
H=Path(__file__).resolve().parent
out=[]
for name in ('lqg_full_reference','lqg_full_bank0','lqg_full_bank1'):
 root=H.parent/'runs'/name;r=json.loads((root/'result.json').read_text())
 m=mavutil.mavlink_connection(r['dflog']);rates=[];sim=[];angles=[]
 while (x:=m.recv_match(type=['RATE','SIM2','ANG'])) is not None:
  if not 34<x.TimeUS/1e6<61:continue
  if x.get_type()=='RATE':rates.append([x.TimeUS/1e6,x.R,x.P,x.Y])
  elif x.get_type()=='SIM2':sim.append([x.TimeUS/1e6,x.PN,x.PE,x.PD])
  else:angles.append([x.TimeUS/1e6,x.Roll,x.Pitch])
 m.close();rates=np.array(rates);sim=np.array(sim);angles=np.array(angles)
 T=np.load(root/'truth.npz')['truth']
 def loss(shift):
  p=np.column_stack([np.interp(sim[:,0]+shift,T[:,0],T[:,i+1]) for i in range(3)])
  return np.mean((p-sim[:,1:])**2)
 # Match position clocks independently before fitting gyro phase.
 offsets=np.arange(-.1,.101,.0005);shift=offsets[np.argmin([loss(d) for d in offsets])]
 dt=.0025;t=np.arange(34,61,dt);rows=[]
 for axis in range(2):
  w=np.interp(t,T[:,0],T[:,10+axis])
  measured=np.radians(np.interp(t-shift,rates[:,0],rates[:,1+axis]))
  best=None
  for hz in (5,8,10,12,15,20,30,40,60,80):
   a=np.exp(-2*np.pi*hz*dt);f=lfilter([1-a],[1,-a],w)
   for delay in np.arange(0,.031,.001):
    pred=np.interp(t-delay,t,f);keep=(t>35)&(t<60)
    error=float(np.mean((pred[keep]-measured[keep])**2))
    if best is None or error<best[0]:best=(error,hz,float(delay))
  atrue=np.interp(angles[:,0]+shift,T[:,0],np.degrees(T[:,7+axis]))
  rows.append({'axis':axis,'effective_gyro_hz':best[1],'extra_delay_s':best[2],
   'rate_residual_rms_dps':float(np.degrees(np.sqrt(best[0]))),
   'angle_error_std_deg':float(np.std(angles[:,1+axis]-atrue))})
 out.append({'name':name,'truth_clock_offset_s':float(shift),'clock_position_rms_mm':float(np.sqrt(loss(shift))*1000),'axes':rows})
(H/'sitl_sensor_fit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
