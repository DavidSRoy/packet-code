import unittest
import numpy as np
from collections import deque
from predictor import Predictor
class PredictorTest(unittest.TestCase):
    def test_zero_motion(self):
        c=Predictor(.0025)
        for _ in range(1000):self.assertEqual(c.update(0,0),0)
    def test_constant_torque_rejection_and_timing(self):
        dt=.0025;c=Predictor(dt);queue=deque([0.]*12,maxlen=12)
        theta=omega=motor=0.;angles=[];errors=[]
        for i in range(12000):
            # Model motor state must match the plant at measurement time.
            errors.append(abs(motor-c.motor))
            u=c.update(theta,omega)
            applied=queue[0];queue.append(u)
            motor+=(1-np.exp(-dt/.015))*(applied-motor)
            a=73.5*motor+.2
            theta+=omega*dt+.5*a*dt*dt;omega+=a*dt
            if i>10000:angles.append(theta)
        self.assertLess(max(errors),1e-12)
        self.assertLess(max(abs(np.array(angles))),1e-5)
    def test_saturation_is_finite(self):
        c=Predictor(.0025)
        for _ in range(100):self.assertLessEqual(abs(c.update(1,10)),.35)
if __name__=='__main__':unittest.main()
