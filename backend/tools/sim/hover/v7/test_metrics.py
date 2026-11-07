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
if __name__=='__main__':unittest.main()
