#!/usr/bin/env python3
"""Reproducible closed-loop, integrated rate-response fit. Not causal identification.
Fit log49 150-180s; validate unchanged coefficients on 180-205s.
The identified delay includes sensing/filter delay; do not add it twice.
"""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.signal import lfilter
from pymavlink import mavutil
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
m = mavutil.mavlink_connection(str(ROOT/'logs/pi/bin/00000049.BIN'))
rows=[]
while (x:=m.recv_match(type='RATE')) is not None:
    if 149 < x.TimeUS/1e6 < 206:
        rows.append([x.TimeUS/1e6,x.R,x.ROut,x.P,x.POut])
a=np.array(rows); dt=.0025; t=np.arange(a[0,0],a[-1,0],dt)
result={'source':'00000049.BIN','source_sha256':hashlib.sha256((ROOT/'logs/pi/bin/00000049.BIN').read_bytes()).hexdigest(),'train_s':[150,180],'validation_s':[180,205], 'caveat':'Closed-loop regression can be biased by correlated disturbances. Lag/delay split is uncertain.'}
for axis,ri,ui in [('roll',1,2),('pitch',3,4)]:
    w=np.radians(np.interp(t,a[:,0],a[:,ri])); u=np.interp(t,a[:,0],a[:,ui])
    n=8; ix=np.arange(60,len(t)); y=w[ix]-w[ix-n]; train=(t[ix]>=150)&(t[ix]<180); val=(t[ix]>=180)&(t[ix]<205)
    candidates=[]
    for tau in np.arange(.002,.042,.002):
        alpha=np.exp(-dt/tau); uf=lfilter([1-alpha],[1,-alpha],u)
        cs=np.r_[0,np.cumsum(uf)]*dt
        for delay in np.arange(0,.062,.002):
            ud=np.interp(t-delay,t,cs[1:]); integ=ud[ix]-ud[ix-n]
            X=np.c_[integ,np.full(len(ix),dt*n)]
            beta=np.linalg.lstsq(X[train],y[train],rcond=None)[0]
            mse=np.mean((y[train]-X[train]@beta)**2)
            candidates.append((mse,float(tau),float(delay),beta,X))
    mse,tau,delay,beta,X=min(candidates,key=lambda z:z[0])
    def r2(mask,pred): return float(1-np.sum((y[mask]-pred[mask])**2)/np.sum((y[mask]-y[mask].mean())**2))
    near=[c for c in candidates if c[0]<=mse*1.05]
    result[axis]={'K':float(beta[0]),'tau_s':tau,'delay_s':delay,'train_r2':r2(train,X@beta),'validation_r2':r2(val,X@beta),'K_within_5pct_loss':[float(min(c[3][0] for c in near)),float(max(c[3][0] for c in near))],'total_delay_within_5pct_loss_s':[min(c[1]+c[2] for c in near),max(c[1]+c[2] for c in near)]}
cv=[json.loads(l) for l in (ROOT/'logs/pi/rec/20261106-205327/cv.jsonl').read_text().splitlines()]
lat=np.array([r['t_done']-r['t_cap'] for r in cv]); gaps=np.diff([r['t_cap'] for r in cv])
result['camera']={'processing_median_s':float(np.median(lat)),'processing_p95_s':float(np.percentile(lat,95)),'period_median_s':float(np.median(gaps)),'gap_p99_s':float(np.percentile(gaps,99)),'frames':len(cv)}
(OUT/'fit.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
