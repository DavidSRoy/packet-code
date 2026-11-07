import unittest
import numpy as np
from score_full_sitl import activity_confirmed, truth_covered
class ActivityTest(unittest.TestCase):
    def samples(self):
        a=np.zeros((280,5));a[:,0]=np.arange(280)*.1+10.05;a[:,1]=2
        return a
    def test_complete_hold(self):
        self.assertTrue(activity_confirmed(self.samples(),10,38,2))
    def test_missing_start(self):
        self.assertFalse(activity_confirmed(self.samples()[40:],10,38,2))
    def test_missing_end(self):
        self.assertFalse(activity_confirmed(self.samples()[:-40],10,38,2))
    def test_missing_interior(self):
        self.assertFalse(activity_confirmed(np.delete(self.samples(),100,axis=0),10,38,2))
    def test_wrong_bank(self):
        self.assertFalse(activity_confirmed(self.samples(),10,38,1))
    def test_truth_requires_complete_hold(self):
        a=np.zeros((2801,21));a[:,0]=np.arange(2801)*.01+10
        self.assertTrue(truth_covered(a,10,38))
        self.assertFalse(truth_covered(a[-801:],10,38))
        self.assertFalse(truth_covered(a[:801],10,38))
    def test_truth_rejects_gap_and_clock_reversal(self):
        a=np.zeros((2801,21));a[:,0]=np.arange(2801)*.01+10
        self.assertFalse(truth_covered(np.delete(a,[100,101,102],axis=0),10,38))
        a[100,0]=a[99,0]
        self.assertFalse(truth_covered(a,10,38))
if __name__=='__main__':unittest.main()
