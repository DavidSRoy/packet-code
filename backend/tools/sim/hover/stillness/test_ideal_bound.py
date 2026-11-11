import unittest
import numpy as np
from ideal_bound import solve_bound, adjusted_thrust
class IdealBoundTest(unittest.TestCase):
    def test_zero_and_constant_disturbance(self):
        # A constant lean can cancel a constant force without any motion.
        for value in (0,.03,-.03):
            self.assertAlmostEqual(solve_bound(np.full(200,value),.05,.0009),0,places=7)
    def test_ground_effect_applied_to_logged_thrust(self):
        import json
        from pathlib import Path
        model=json.loads((Path(__file__).resolve().parents[1]/'model.json').read_text())
        trace=np.zeros((2,21));trace[:,13:17]=7
        rest=-max(p[2] for p in model['skid_points'])
        trace[:,3]=[rest,rest-.1]
        actual=adjusted_thrust(trace,model)
        expected=7*(1+model['ge_a']*np.exp(-np.array([0,.1])/model['ge_b']))
        np.testing.assert_allclose(actual,np.repeat(expected[:,None],4,axis=1))
        model['ground_effect']=False
        np.testing.assert_allclose(adjusted_thrust(trace,model),trace[:,13:17])
    def test_linearity_and_grid_convergence(self):
        values=[]
        for dt in (.025,.05,.1):
            t=np.arange(0,20,dt);d=.03*np.sin(2*np.pi*.25*t)
            scale=solve_bound(d,dt,.0009)
            self.assertGreater(scale,1)
            self.assertAlmostEqual(solve_bound(d*.5,dt,.0009),scale*.5,places=5)
            values.append(scale)
        self.assertLess(max(values)-min(values),.03)
if __name__=='__main__':unittest.main()
