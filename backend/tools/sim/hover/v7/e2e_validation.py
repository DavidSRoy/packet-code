"""Run the real ground-control code against isolated SITL, never a serial device."""
import concurrent.futures,json,subprocess,sys
from pathlib import Path
from experiment import config
H=Path(__file__).resolve().parent
model=json.loads((H/'model_overrides.json').read_text())
PARAM_FILE='tools/tune_v7.parm'
def run(case):
 name,inst,extra=case
 c=config('v7e2e_final_'+name,{},12,{**model,**extra})
 c['parm']=[PARAM_FILE]
 argv=[sys.executable,str(H.parent/'e2e/run_e2e.py'),'--name',c['name'],'--instance',str(inst),'--out',str(H.parent/'runs'),'--height','.10','--hold','20','--flown',c['flown']]
 for k in ('parm','p','set'):
  for v in c[k]:argv+=['--'+k,v]
 with (H/('final_'+name+'_e2e.txt')).open('w') as f:
  subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
  list(ex.map(run,[('nominal',20,{}),('camera_loss',21,{'camera.blackout':{'t':15,'dur':2}})]))
