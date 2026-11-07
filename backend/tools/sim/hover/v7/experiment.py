#!/usr/bin/env python3
"""Generate paired SITL experiments; run from backend with batch.py."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
fit=json.loads((HERE/'fit.json').read_text())
# Effective inertia reproduces measured output-to-rate gain, not CAD inertia.
model={'inertia':[11.89/fit['roll']['K'],11.89/fit['pitch']['K'],.103], 'motor_tau':.015,'motor_delay':.040,
       'camera.tilt_attitude_lag_s':.06,'camera.pi_cam_pos_err':[0,0,0],
       'camera.detect_s':fit['camera']['processing_median_s']-.004*.798,
       'camera.detect_jitter_s':.004}
# Regression estimate is retained as a stress case, not accepted as a validated plant.
def config(name,changes=None,seed=1,extra=None,height=.10):
    M={**model,**(extra or {})}
    return {'name':name,'flown':'tools/sim/hover/flown_log49.parm','parm':['tools/tune_v6.parm'], 'height':height,'hold':30,'seed':seed,
            'set':[k+'='+json.dumps(v,separators=(',',':')) for k,v in M.items()],
            'p':['SIM_ACC1_RND=0.8','SIM_ACC2_RND=0.8']+[k+'='+str(v) for k,v in (changes or {}).items()]}
def gains(p=.22,d=.006,ang=7.5,i=.3):
    return {**{f'ATC_RAT_{ax}_{k}':v for ax in ('RLL','PIT') for k,v in [('P',p),('I',i),('D',d)]},**{f'ATC_ANG_{ax}_P':ang for ax in ('RLL','PIT')}}
if __name__=='__main__':
    (HERE/'regression_model.json').write_text(json.dumps(model,indent=2)+'\n')
    candidates={'v6':{},'a6':gains(ang=6),'a45':gains(ang=4.5),'p18a6':gains(p=.18,ang=6),'p26a6':gains(p=.26,ang=6),'d8a6':gains(d=.008,ang=6),'d4a6':gains(d=.004,ang=6),'d8a45':gains(d=.008,ang=4.5),'p26d8a6':gains(p=.26,d=.008,ang=6),'i2a6':gains(i=.2,ang=6)}
    (HERE/'search.json').write_text(json.dumps([config('v7search_'+n,c) for n,c in candidates.items()],indent=2)+'\n')
