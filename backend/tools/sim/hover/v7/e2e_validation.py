"""Run the real ground-control code against isolated SITL, never a serial device."""
import concurrent.futures,json,subprocess,sys
from pathlib import Path
from experiment import config
H=Path(__file__).resolve().parent
model=json.loads((H/'model_overrides.json').read_text())
PARAM_FILE='tools/tune_v7.parm'


def validate_result(result, case):
    expected = {
        'nominal': 'test run done: landed, motors off',
        'camera_loss': 'camera-loss landing ended; FC disarmed',
    }[case]
    status = result.get('final_status', {})
    if status.get('state') != 'done' or status.get('reason') != expected:
        raise ValueError(f'{case}: unsuccessful landing: {status}')
    events = result.get('events_rel_s', {})
    times = [events.get(k) for k in ('armed', 'handover', 'at height', 'descend', 'disarmed')]
    if any(not isinstance(t, (int, float)) for t in times):
        raise ValueError(f'{case}: missing flight/landing events: {events}')
    if not all(0 <= a < b for a, b in zip(times, times[1:])):
        raise ValueError(f'{case}: flight/landing events out of order: {events}')

def run(case):
 name,inst,extra=case
 c=config('v7e2e_final_'+name,{},12,{**model,**extra})
 c['parm']=[PARAM_FILE]
 argv=[sys.executable,str(H.parent/'e2e/run_e2e.py'),'--name',c['name'],'--instance',str(inst),'--out',str(H.parent/'runs'),'--height','.10','--hold','20','--flown',c['flown']]
 for k in ('parm','p','set'):
  for v in c[k]:argv+=['--'+k,v]
 with (H/('final_'+name+'_e2e.txt')).open('w') as f:
  subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
 validate_result(json.loads((H.parent/'runs'/c['name']/'result.json').read_text()),name)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
  list(ex.map(run,[('nominal',20,{}),('camera_loss',21,{'camera.blackout':{'t':15,'dur':2}})]))
