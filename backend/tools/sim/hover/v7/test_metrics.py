"""Independent synthetic trajectory check for wobble scoring units and bands."""
import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run import score
class MetricsTest(unittest.TestCase):
 def test_known_motion(self):
  t=np.arange(0,32,.0025); a=np.zeros((len(t),13)); a[:,0]=t
  a[:,3]=np.where(t<5,0,-.1)
  a[:,7]=np.radians(.2)*np.sin(2*np.pi*1.5*t)
  a[:,8]=np.radians(.1)*np.sin(2*np.pi*2*t)
  e={k:{'wall':v} for k,v in [('armed',3),('handover',5),('at height',8),('descend',30)]}
  r=score(a,e,np.array([[0.,0.],[32.,32.]]),.1)
  self.assertAlmostEqual(r['tilt_1_3_rms_deg'],np.sqrt((.2**2+.1**2)/2),places=3)
  self.assertAlmostEqual(r['roll_ptp_deg'],.4,places=3)
  self.assertAlmostEqual(r['pitch_ptp_deg'],.2,places=3)
  self.assertAlmostEqual(r['xy_rms_mm'],0)
  self.assertAlmostEqual(r['z_rms_mm'],0)
class LandingValidationTest(unittest.TestCase):
 def result(self):
  return {'final_status': {'state':'done','reason':'test run done: landed, motors off'},
          'events_rel_s': dict(zip(['armed','handover','at height','descend','disarmed'],[1,2,3,4,5]))}
 def test_success(self):
  from e2e_validation import validate_result
  validate_result(self.result(),'nominal')
  r=self.result();r['final_status']['reason']='camera-loss landing ended; FC disarmed'
  validate_result(r,'camera_loss')
 def test_failure_status_and_wrong_landing_path(self):
  from e2e_validation import validate_result
  for state in ('killed','refused'):
   r=self.result();r['final_status']['state']=state
   with self.assertRaises(ValueError):validate_result(r,'nominal')
  with self.assertRaises(ValueError):validate_result(self.result(),'camera_loss')
 def test_missing_or_early_disarm(self):
  from e2e_validation import validate_result
  for t in (None,0,3):
   r=self.result();r['events_rel_s']['disarmed']=t
   with self.assertRaises(ValueError):validate_result(r,'nominal')
if __name__=='__main__':unittest.main()

