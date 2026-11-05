"""Hover analysis of an ArduCopter dataflash log (.BIN).

Usage: python tools/hover_analysis.py logs/bin/00000014.BIN

Finds stable hover (armed, height > 2 m, climb < 0.3 m/s, GPS speed < 0.7 m/s,
roll and pitch < 6 deg) and prints hover power, motor balance, control effort,
vibration and position-hold error. Needs pymavlink and numpy.
"""
from pymavlink import mavutil
import numpy as np, sys
m=mavutil.mavlink_connection(sys.argv[1])
D={k:[] for k in ["CTUN","BAT","RCOU","ATT","GPS","VIBE","RATE","MOTB","PIDR","PIDP","PIDY","PSCD","PSCN","PSCE"]}
armed=[]
while True:
    x=m.recv_match(type=list(D)+["EV"])
    if x is None: break
    t=x.get_type()
    if t=="EV":
        if x.Id==10: armed.append([x.TimeUS,None])
        if x.Id==11 and armed: armed[-1][1]=x.TimeUS
        continue
    if t=="VIBE" and x.IMU!=0: continue
    D[t].append(x)
def arr(t,f): return np.array([getattr(x,f) for x in D[t]],float)
def ts(t): return arr(t,"TimeUS")
def at(t,f,tq):
    T=ts(t); V=arr(t,f); i=np.clip(np.searchsorted(T,tq),0,len(T)-1); return V[i]
T=ts("CTUN")
alt=arr("CTUN","Alt"); crt=arr("CTUN","CRt"); tho=arr("CTUN","ThO"); thh=arr("CTUN","ThH")
spd=at("GPS","Spd",T); roll=at("ATT","Roll",T); pitch=at("ATT","Pitch",T)
inarm=np.zeros(len(T),bool)
for a,b in armed: inarm|=(T>=a)&(T<=(b or 1e18))
hov=inarm&(alt>2)&(abs(crt)<0.3)&(spd<0.7)&(abs(roll)<6)&(abs(pitch)<6)
print("armed periods s",[(round(a/1e6),round((b or 0)/1e6)) for a,b in armed])
print("stable hover",hov.sum()/10,"s; alt p5/50/95",np.round(np.percentile(alt[hov],[5,50,95]),1))
V=at("BAT","Volt",T); I=at("BAT","Curr",T)
print("hover V med",np.median(V[hov]).round(2),"I med",np.median(I[hov]).round(1),"I p10/p90",np.percentile(I[hov],[10,90]).round(1),"P med W",np.median((V*I)[hov]).round(0))
print("ThO hover med",np.median(tho[hov]).round(3),"ThH med",np.median(thh[hov]).round(3))
Vb=arr("BAT","Volt");Ib=arr("BAT","Curr")
print("rest V med",np.median(Vb[Ib<1.5]).round(2),"min V",Vb.min().round(2),"BAT Res",D["BAT"][-1].Res,"mAh total",round(D["BAT"][-1].CurrTot),"RemPct end",D["BAT"][-1].RemPct)
# sag regression V = V0 - R*I in armed
Tb=ts("BAT"); ab=np.zeros(len(Tb),bool)
for a,b in armed: ab|=(Tb>=a)&(Tb<=(b or 1e18))
if ab.sum()>20:
    A=np.vstack([np.ones(ab.sum()),Ib[ab]]).T; c=np.linalg.lstsq(A,Vb[ab],rcond=None)[0]; print("fit V0",c[0].round(2),"R ohm",(-c[1]).round(4))
c=[at("RCOU",f"C{i}",T)[hov] for i in range(1,5)]
md=[np.median(x) for x in c]
print("motor PWM med M1..M4",[int(x) for x in md],"(M1 FR CCW, M2 RL CCW, M3 FL CW, M4 RR CW)")
print("CW-CCW",round((md[2]+md[3]-md[0]-md[1])/2,1),"front-rear",round((md[0]+md[2]-md[1]-md[3])/2,1),"left-right",round((md[1]+md[2]-md[0]-md[3])/2,1),"max-min",round(max(md)-min(md),1))
for k in ["ROut","POut","YOut"]: print(k,"mean",at("RATE",k,T)[hov].mean().round(3),"std",at("RATE",k,T)[hov].std().round(3))
print("att mean roll/pitch",roll[hov].mean().round(2),pitch[hov].mean().round(2))
for ax in ["PIDR","PIDP","PIDY"]:
    print(ax,"I",np.round(at(ax,"I",T)[hov].mean(),3),"Pstd",np.round(at(ax,"P",T)[hov].std(),3),"Dstd",np.round(at(ax,"D",T)[hov].std(),3),"errstd",np.round(at(ax,"Err",T)[hov].std(),2))
for k in ["VibeX","VibeY","VibeZ"]:
    v=at("VIBE",k,T)[hov]; print(k,"med",np.median(v).round(1),"p95",np.percentile(v,95).round(1))
print("clip",D["VIBE"][-1].Clip)
print("LiftMax med",np.median(at("MOTB","LiftMax",T)[hov]).round(3),"ThLimit samples",(at("MOTB","ThLimit",T)[inarm]>0).sum())
pn=at("PSCN","PN",T)-at("PSCN","TPN",T); pe=at("PSCE","PE",T)-at("PSCE","TPE",T); pd=at("PSCD","PD",T)-at("PSCD","TPD",T)
print("pos err horiz p50/p95",np.percentile(np.hypot(pn,pe)[hov],[50,95]).round(2),"vert p95",np.percentile(abs(pd[hov]),95).round(2))
print("rate std R/P/Y",[np.std(at("RATE",k,T)[hov]).round(2) for k in "RPY"])
