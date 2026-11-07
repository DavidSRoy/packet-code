"""Paired controllers, identical seeds/models. No physical connection is used."""
import json
from pathlib import Path
from experiment import config,gains,model
H=Path(__file__).resolve().parent
nom={**model,'inertia':[.2022007/1.25,.24194888/1.5,.103],'motor_delay':.030}
(H/'model_overrides.json').write_text(json.dumps(nom,indent=2)+'\n')
scenarios=[('nom1',{},1,.10),('nom2',{},2,.10),('nom3',{},3,.10),('low',{},4,.02),
 ('old',{'inertia':[.1544,.1628,.103],'motor_tau':.02,'motor_delay':.03},5,.10),
 ('strong',{'inertia':[.1235,.1302,.0824],'motor_tau':.02,'motor_delay':.03},6,.10),
 ('weak',model,7,.10),
 ('latency',{'camera.detect_s':.15,'camera.detect_jitter_s':.02,'camera.exposure_to_readout_s':.075},8,.10),
 ('noise',{'camera.noise_xy_m':.0015},9,.10),
 ('gust',{'gust':{'t':15,'dur':1,'accel':[.3,0,0]}},10,.10),
 ('slow',{'motor_tau':.025,'motor_delay':.04},11,.10)]
rows=[]
for n,over,seed,h in scenarios:
 for label,g in [('v6',{}),('a6',gains(ang=6)),('pd',gains(p=.26,d=.008,ang=6))]:
  rows.append(config('v7val_'+n+'_'+label,g,seed,{**nom,**over},h))
(H/'validation.json').write_text(json.dumps(rows,indent=2)+'\n')
