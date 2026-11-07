import unittest
import numpy as np
from ideal_bound import solve_bound
class IdealBoundTest(unittest.TestCase):
    def test_zero_and_constant_disturbance(self):
        # A constant lean can cancel a constant force without any motion.
        for value in (0,.03,-.03):
            self.assertAlmostEqual(solve_bound(np.full(200,value),.05,.0009),0,places=7)
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
