"""Necessary-bound diagnostic, NOT a flight controller or hardware feasibility proof.
Small-angle, per-world-axis ideal control with no sensing/motor lag or rate limits.
Disturbance reconstructed from simulator truth and logged motor thrust.
Finite differences and small-angle dynamics introduce approximation error.
"""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
def solve_bound(disturbance, dt, angle_amp, drag=.3/2.92):
    n=len(disturbance);size=3*n+2;bias=3*n;rho=bias+1
    # x, v, angle deviation, constant mean angle, common target scaling rho.
    A=lil_matrix((2*(n-1),size));b=np.zeros(2*(n-1));g=9.80665
    for i in range(n-1):
     j=2*i;A[j,i+1]=1;A[j,i]=-1;A[j,n+i]=-dt*(1-.5*dt*drag);A[j,2*n+i]=.5*dt*dt*g;A[j,bias]=.5*dt*dt*g;b[j]=.5*dt*dt*disturbance[i]
     A[j+1,n+i+1]=1;A[j+1,n+i]=-(1-dt*drag);A[j+1,2*n+i]=dt*g;A[j+1,bias]=dt*g;b[j+1]=dt*disturbance[i]
    C=lil_matrix((4*n,size));ub=np.zeros(4*n)
    for i in range(n):
     for j,col,cap in ((4*i,i,.001),(4*i+2,2*n+i,angle_amp)):
      C[j,col]=1;C[j,rho]=-cap;C[j+1,col]=-1;C[j+1,rho]=-cap
    cost=np.zeros(size);cost[rho]=1
    bounds=[(None,None)]*size;bounds[rho]=(0,None)
    fit=linprog(cost,A_ub=C.tocsr(),b_ub=ub,A_eq=A.tocsr(),b_eq=b,bounds=bounds,method='highs')
    if not fit.success:
        raise ValueError(fit.message)
    return float(fit.fun)

def main():
    H=Path(__file__).resolve().parent
    run=H.parent/'runs/still_baseline'
    r=json.loads((run/'result.json').read_text())
    trace=np.load(run/'truth.npz');T=trace['truth'];model=json.loads(str(trace['model']))
    wm=np.loadtxt(run/'wallmap.txt');mass=model['mass'];drag=np.array(model['drag_lin'])/mass
    start=np.interp(r['events']['at height']['wall'],wm[:,0],wm[:,1])+2
    end=np.interp(r['events']['descend']['wall'],wm[:,0],wm[:,1])
    t=T[:,0];vel=T[:,4:7];acc=np.column_stack([np.gradient(vel[:,i],t) for i in range(3)])
    roll,pitch,yaw=T[:,7],T[:,8],T[:,9];cr,sr=np.cos(roll),np.sin(roll);cp,sp=np.cos(pitch),np.sin(pitch);cy,sy=np.cos(yaw),np.sin(yaw)
    bx,by=model['thrust_axis_xy']
    thrust=np.column_stack([bx*cy*cp+by*(cy*sp*sr-sy*cr)-(cy*sp*cr+sy*sr),
     bx*sy*cp+by*(sy*sp*sr+cy*cr)-(sy*sp*cr-cy*sr),-bx*sp+by*cp*sr-cp*cr])
    force_acc=acc+vel*drag;force_acc[:,2]-=9.80665
    if T.shape[1] < 17:
        raise ValueError('Motor-thrust trace is required')
    scale=T[:,13:17].sum(axis=1)/mass
    d=force_acc[:,:2]-scale[:,None]*thrust[:,:2]
    out={'caveat':__doc__,'hold_s':float(end-start),'grids':{}}
    angle_amp=np.radians(.1)/2*float(np.max(np.abs(cy)+np.abs(sy)))
    for dt in (.025,.05,.1):
        u=np.arange(start,end,dt)
        down=np.array([d[(t>=tt)&(t<min(tt+dt,end))].mean(0) for tt in u])
        out['grids'][str(dt)]={
            'world_angle_half_range_rad':angle_amp,
            'minimum_common_target_scale':{axis:solve_bound(down[:,i],dt,angle_amp,drag[i]) for i,axis in enumerate('NE')},
            'disturbance_std_mps2':down.std(axis=0).tolist()}
    (H/'ideal_bound.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=="__main__":
    main()
