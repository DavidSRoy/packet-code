"""Simulation-only delay predictor and torque-disturbance observer.
Not connected to MAVLink and not a deployable flight controller.
"""
from collections import deque
import math
import numpy as np

class Predictor:
    def __init__(self,dt,K=73.5,delay=.03,tau=.015,wn=16,zeta=1,pole=50,observer_hz=3):
        self.dt,self.K,self.tau=dt,K,tau
        self.delay_steps=max(1,round(delay/dt))
        self.commands=deque([0.]*self.delay_steps,maxlen=self.delay_steps)
        self.motor=0.;self.prev_rate=0.;self.accel_f=0.;self.model_f=0.
        self.obs_alpha=1-math.exp(-2*math.pi*observer_hz*dt)
        c2=2*zeta*wn+pole;c1=wn*wn+2*zeta*wn*pole;c0=wn*wn*pole
        self.kt=tau*c0/K;self.kw=tau*c1/K;self.km=tau*c2-1
        self.motor_alpha=1-math.exp(-dt/tau)

    def update(self,angle,rate,target=0.):
        # Prediction state uses only past commanded output, never true plant state.
        accel=(rate-self.prev_rate)/self.dt;self.prev_rate=rate
        self.accel_f+=self.obs_alpha*(accel-self.accel_f)
        self.model_f+=self.obs_alpha*(self.K*self.motor-self.model_f)
        disturbance=self.accel_f-self.model_f
        theta,omega,motor=angle,rate,self.motor
        for command in self.commands:
            motor+=self.motor_alpha*(command-motor)
            a=self.K*motor+disturbance
            theta+=self.dt*omega+.5*self.dt*self.dt*a
            omega+=self.dt*a
        # State feedback places a damped angle/rate pair plus a motor pole.
        # Constant disturbance cancellation accounts for the motor-state feedback.
        output=self.kt*(target-theta)-self.kw*omega-self.km*motor-(1+self.km)*disturbance/self.K
        output=float(np.clip(output,-.35,.35))
        self.motor+=self.motor_alpha*(self.commands[0]-self.motor)
        self.commands.append(output)
        return output

class ReferencePID:
    """Approximation to v7 angle/rate PID for screening, not ArduPilot equivalence."""
    def __init__(self,dt):
        self.dt=dt;self.integral=0.;self.previous=0.;self.derivative=0.;self.target_rate=0.
        self.alpha=1-math.exp(-2*math.pi*20*dt)
    def update(self,angle,rate,target=0.):
        self.target_rate+=self.alpha*(7.5*(target-angle)-self.target_rate)
        error=self.target_rate-rate
        self.integral=float(np.clip(self.integral+.3*error*self.dt,-.5,.5))
        self.derivative+=self.alpha*((error-self.previous)/self.dt-self.derivative)
        self.previous=error
        return float(np.clip(.26*error+self.integral+.006*self.derivative,-.35,.35))
