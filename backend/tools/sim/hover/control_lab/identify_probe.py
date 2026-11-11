"""Simulation-only closed-loop identification with an independent known excitation.
No MAVLink, hardware output, or proposed live calibration command is present.
"""
import json,math
from collections import deque
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from predictor import ReferencePID
H=Path(__file__).resolve().parent

def identify(K,delay,tau,seed,duration=80):
    dt=.0025;steps=int(duration/dt);rng=np.random.default_rng(seed)
    frequencies=np.array([2.5,5.5,8.5]);amplitude=.0015
    innovation=rng.normal(size=(steps,2));noise=rng.normal(size=steps)
    controller=ReferencePID(dt);queue=deque([0.]*round(delay/dt),maxlen=round(delay/dt))
    theta=omega=motor=gyro=0.;dist=np.zeros(2);data=[]
    for i in range(steps):
        t=i*dt;a=np.exp(-dt/np.array([.25,.025]))
        dist=a*dist+np.array([.25,.4])*np.sqrt(1-a*a)*innovation[i]
        gyro+=(1-math.exp(-2*math.pi*40*dt))*(omega-gyro)
        measured=gyro+.003*noise[i]
        probe=amplitude*np.sin(2*np.pi*frequencies*t).sum()*min(max((t-5)/2,0),1)
        u=float(np.clip(controller.update(theta,measured)+probe,-.35,.35))
        applied=queue[0];queue.append(u);motor+=(1-math.exp(-dt/tau))*(applied-motor)
        acc=K*motor+dist.sum();theta+=omega*dt+.5*acc*dt*dt;omega+=acc*dt
        data.append((t,u,measured,theta,probe))
    A=np.array(data);A=A[A[:,0]>=10]
    wave=np.exp(-2j*np.pi*frequencies[:,None]*A[:,0])
    U=wave@A[:,1];Y=wave@A[:,2];response=Y/U
    def model(p):
        gain,lag_delay,motor_tau=p;z=np.exp(-2j*np.pi*frequencies*dt)
        ma=np.exp(-dt/motor_tau);ga=np.exp(-2*np.pi*40*dt)
        # Includes sample/update ordering and the measured gyro's low-pass response.
        return gain*dt*(1-ma)*z*np.exp(-2j*np.pi*frequencies*lag_delay)/((1-z)*(1-ma*z))*(1-ga)/(1-ga*z)
    def residual(p):
        error=(model(p)-response)/abs(response)
        return np.r_[error.real,error.imag]
    fit=least_squares(residual,[73.5,.03,.015],bounds=([30,.005,.002],[130,.065,.05]))
    return {'truth':{'K':K,'delay':delay,'tau':tau},'seed':seed,'estimate':dict(zip(['K','delay','tau'],fit.x.tolist())),
            'normalized_fit_rms':float(np.sqrt(np.mean(residual(fit.x)**2))),
            'full_motion_ptp_deg':float(np.degrees(np.ptp(A[:,3]))),
            'probe_amplitude_per_tone':amplitude,'frequencies_hz':frequencies.tolist(),
            'duration_s':duration,'caveat':'Single-axis synthetic plant only; this does not identify or qualify the physical drone.'}
if __name__=='__main__':
    rows=[]
    for K,d,tau in [(73.5,.03,.015),(50,.03,.015),(100,.03,.015),(73.5,.045,.025)]:
        for seed in (1,2,3):
            r=identify(K,d,tau,seed);rows.append(r);print(r,flush=True)
    (H/'identification.json').write_text(json.dumps(rows,indent=2)+'\n')
