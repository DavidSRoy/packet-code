"""Score complete local SITL runs; require evidence custom firmware actually ran."""
import argparse
import json
import sys
import re
from pathlib import Path
import numpy as np
from pymavlink import mavutil
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'stillness'))
from acceptance import meets_target
from gust_metrics import evaluate as evaluate_gust


def score(config):
    result=[]
    for c in json.loads(config.read_text()):
        root=HERE.parent/'runs'/c['name']
        r=json.loads((root/'result.json').read_text())
        item={'name':c['name'],'status':r['status'],'custom_control':c.get('custom_control',False)}
        if not r['status'].startswith('ok'):
            item['meets_target']=False;result.append(item);continue
        archive=np.load(root/'truth.npz');truth=archive['truth']
        wm=np.loadtxt(root/'wallmap.txt');events=r['events']
        start=np.interp(events['at height']['wall'],wm[:,0],wm[:,1])+2
        end=np.interp(events['descend']['wall'],wm[:,0],wm[:,1])
        hold=truth[(truth[:,0]>=start)&(truth[:,0]<=end)]
        position=np.ptp(hold[:,1:4],axis=0)*1000
        angle=np.ptp(np.degrees(np.unwrap(hold[:,7:10],axis=0)),axis=0)
        item.update(hold_s=float(end-start),position_ptp_mm=position.tolist(),angle_ptp_deg=angle.tolist(),score=r['score'])
        active=True
        if item['custom_control']:
            log=mavutil.mavlink_connection(r['dflog'])
            samples=[]
            while (m:=log.recv_match(type='PKLQ')) is not None:
                if events['at height']['fc_t']+2 <= m.TimeUS/1e6 <= events['descend']['fc_t']:
                    samples.append([m.TimeUS/1e6,m.Bank,m.R,m.P,m.Y])
            log.close()
            a=np.array(samples)
            expected_bank=int(next(p.split('=')[1] for p in c['p'] if p.startswith('CC1_PARAM1=')))
            active=(len(a)>0 and len(a)>=int((end-start)*8) and np.all(a[:,1]==expected_bank)
                    and np.max(np.diff(a[:,0]),initial=0)<.3)
            item.update(custom_samples=len(a),custom_activity_confirmed=bool(active))
            if len(a):item['custom_max_output']=np.max(np.abs(a[:,2:]),axis=0).tolist()
        item['meets_target']=bool(active and meets_target(position.tolist(),angle.tolist(),end-start))
        model=json.loads(str(archive['model'].item()))
        if model.get('gust'):
            lift=re.search(r'liftoff at t=([0-9.]+)',(root/'physics.log').read_text())
            if lift is None:raise ValueError('Missing explicit physics liftoff timestamp')
            gust_start=float(lift.group(1))+model['gust']['t']
            gust_end=gust_start+model['gust']['dur']
            item['gust']=evaluate_gust(hold[:,0],hold[:,1:4],np.degrees(hold[:,7:10]),gust_start,gust_end,start)
            # Whole-window extrema include the permitted gust lean. They are
            # reported above, but are not the settled-hover acceptance test.
            pre=hold[(hold[:,0]>=start)&(hold[:,0]<gust_start)]
            pre_ok=meets_target((np.ptp(pre[:,1:4],axis=0)*1000).tolist(),
                 np.ptp(np.degrees(np.unwrap(pre[:,7:10],axis=0)),axis=0).tolist(),gust_start-start)
            item['meets_target']=bool(active and pre_ok and item['gust']['recovery_confirmed'])
        result.append(item)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('--require-target',action='store_true');args=p.parse_args()
    rows=score(args.config)
    args.config.with_name(args.config.stem+'_metrics.json').write_text(json.dumps(rows,indent=2)+'\n')
    for r in rows:print(r['name'],r['status'],r.get('position_ptp_mm'),r.get('angle_ptp_deg'),'active',r.get('custom_activity_confirmed'),'pass',r['meets_target'])
    if args.require_target and not all(r['meets_target'] for r in rows):raise SystemExit(1)
