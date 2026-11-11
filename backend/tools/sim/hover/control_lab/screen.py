"""Screen predictive control with nonzero torque disturbances and uncertain actuators.
Single-axis linear lab only; no position, thrust mixer, estimator or full flight claim.
"""
import json,math
from collections import deque
from pathlib import Path
import numpy as np
from predictor import Predictor,ReferencePID
H=Path(__file__).resolve().parent

def run(kind,seed=1,K=73.5,delay=.03,tau=.015,noise=.003,wn=16,observer_hz=3,effort=.01,rate_cost=.001,controller_model=None):
    dt=.0025;steps=int(35/dt);rng=np.random.default_rng(seed)
    # Pre-generated disturbances and noise keep every candidate's inputs identical.
    innovations=rng.normal(size=(steps,2));sensor_noise=rng.normal(size=(steps,2))
    state=np.zeros(2);dist=[]
    for xi in innovations:
        a=np.exp(-dt/np.array([.25,.025]));state=a*state+np.array([.25,.4])*np.sqrt(1-a*a)*xi
        dist.append(state.sum())
    if kind=='lqg':
        from lqg import LQG
        controller=LQG(dt,effort=effort,rate_cost=rate_cost,**(controller_model or {}))
    else:
        controller=ReferencePID(dt) if kind=='pid' else Predictor(dt,wn=wn,observer_hz=observer_hz)
    queue=deque([0.]*max(1,round(delay/dt)),maxlen=max(1,round(delay/dt)))
    angle=rate=motor=gyro_f=0.;trace=[]
    for i in range(steps):
        gyro_f+=(1-math.exp(-2*math.pi*40*dt))*(rate-gyro_f)
        u=controller.update(angle+.0003*sensor_noise[i,0],gyro_f+noise*sensor_noise[i,1])
        applied=queue[0];queue.append(u)
        motor+=(1-math.exp(-dt/tau))*(applied-motor)
        a=K*motor+dist[i];angle+=rate*dt+.5*a*dt*dt;rate+=a*dt
        trace.append((i*dt,angle,rate,u,dist[i]))
        if abs(angle)>math.radians(25):
            return {'kind':kind,'seed':seed,'K':K,'delay':delay,'tau':tau,'wn':wn,'observer_hz':observer_hz,'status':'unstable','time_s':i*dt}
    t=np.array(trace);s=t[t[:,0]>=5]
    return {'kind':kind,'seed':seed,'K':K,'delay':delay,'tau':tau,'wn':wn,'observer_hz':observer_hz,'status':'stable',
            'angle_rms_deg':float(np.degrees(np.std(s[:,1]))),'angle_ptp_deg':float(np.degrees(np.ptp(s[:,1]))),
            'output_max':float(np.max(abs(s[:,3]))),'output_rms':float(np.std(s[:,3]))}
if __name__=='__main__':
    results=[]
    for name,args in [('nominal',{}),('weak',{'K':50}),('strong',{'K':100}),('slow',{'delay':.045,'tau':.025}),('fast',{'delay':.02,'tau':.01}),('noisy',{'noise':.01})]:
        configs=[('pid',16,3)]+[('predictor',wn,hz) for wn in (12,16,20,24) for hz in (1,3,5)]
        for kind,wn,hz in configs:
            r=run(kind,wn=wn,observer_hz=hz,**args);r['case']=name;results.append(r)
    (H/'screen.json').write_text(json.dumps(results,indent=2)+'\n')
    for name in ('nominal','weak','strong','slow','fast','noisy'):
        rows=[r for r in results if r['case']==name];print(name,'reference',rows[0])
        good=sorted([r for r in rows[1:] if r['status']=='stable'],key=lambda r:r['angle_rms_deg'])
        print('best',good[:2])
