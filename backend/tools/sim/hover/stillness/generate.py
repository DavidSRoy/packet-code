"""Diagnostic ablations, not proposed hardware or flight-ready configurations."""
import json,sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'v7'))
from experiment import config
nom=json.loads((H.parent/'v7/model_overrides.json').read_text())
quiet={'camera.noise_xy_m':0,'camera.noise_z_m':0,'camera.noise_yaw_rad':0}
ideal={**quiet,'camera.rate_hz':30,'camera.drop_frac':0,'camera.exposure_to_readout_s':0,'camera.detect_s':0,'camera.detect_jitter_s':0,'camera.link_s':.005,'camera.tilt_attitude_lag_s':0}
sensors={f'SIM_{s}{i}_RND':0 for s in ('ACC','GYR') for i in (1,2)}
scenarios=[('baseline',{},{}),('quiet_camera',quiet,{}),('no_torque',{'dist_alpha':[]},{}),('no_force',{'dist_accel':[]},{}),('no_disturbance',{'dist_alpha':[],'dist_accel':[]},{}),('quiet_imu',{},sensors),('ideal_camera',ideal,{'VISO_DELAY_MS':0}),('ideal_all',{**ideal,'dist_alpha':[],'dist_accel':[]},{**sensors,'VISO_DELAY_MS':0}),('gentler_position',{}, {'PSC_NE_POS_P':1.5,'PSC_NE_VEL_P':2,'PSC_NE_VEL_I':1})]
rows=[]
for n,m,p in scenarios:
 c=config('still_'+n,p,1,{**nom,**m});c['parm']=['tools/tune_v7.parm'];rows.append(c)
(H/'diagnostics.json').write_text(json.dumps(rows,indent=2)+'\n')
