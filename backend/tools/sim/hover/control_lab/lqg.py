"""Experimental single-axis LQG with motor delay and two disturbance states.
Offline simulation only. Uses angle/rate measurements and its own command history.
"""
import math
import numpy as np
from scipy.linalg import solve_discrete_are
class LQG:
    def __init__(self,dt,K=73.5,delay=.03,tau=.015,effort=.01,rate_cost=.001):
        count=max(1,round(delay/dt));n=6+count
        A=np.zeros((n,n));B=np.zeros((n,1));W=np.zeros((n,2))
        motor_a=math.exp(-dt/tau);gyro_a=math.exp(-2*math.pi*40*dt)
        da=np.exp(-dt/np.array([.25,.025]));ds=np.array([.25,.4])*np.sqrt(1-da*da)
        acceleration=np.zeros(n);acceleration[2]=K*motor_a;acceleration[6]=K*(1-motor_a);acceleration[3:5]=da
        A[0,0]=1;A[0,1]=dt;A[0]+=.5*dt*dt*acceleration
        A[1,1]=1;A[1]+=dt*acceleration
        A[2,2]=motor_a;A[2,6]=1-motor_a
        A[3,3],A[4,4]=da
        A[5]=(1-gyro_a)*A[1];A[5,5]+=gyro_a
        for i in range(6,n-1):A[i,i+1]=1
        B[-1,0]=1
        W[0]=.5*dt*dt*ds;W[1]=dt*ds;W[3,0]=ds[0];W[4,1]=ds[1];W[5]=(1-gyro_a)*dt*ds
        C=np.zeros((2,n));C[0,0]=1;C[1,5]=1
        Q=np.zeros((n,n));Q[0,0]=1;Q[1,1]=rate_cost
        R=np.array([[effort]])
        P=solve_discrete_are(A,B,Q,R)
        self.feedback=np.linalg.solve(R+B.T@P@B,B.T@P@A)
        covariance=W@W.T+np.eye(n)*1e-16
        measurement_noise=np.diag([.0003**2,.003**2])
        Pobs=solve_discrete_are(A.T,C.T,covariance,measurement_noise)
        self.gain=Pobs@C.T@np.linalg.inv(C@Pobs@C.T+measurement_noise)
        self.A,self.B,self.C=A,B,C;self.state=np.zeros(n)
    def update(self,angle,rate,target=0.):
        if target!=0:raise ValueError('This screening implementation supports zero-angle regulation only')
        posterior=self.state+self.gain@(np.array([angle,rate])-self.C@self.state)
        output=float(np.clip(-(self.feedback@posterior)[0],-.35,.35))
        self.state=self.A@posterior+self.B[:,0]*output
        return output
