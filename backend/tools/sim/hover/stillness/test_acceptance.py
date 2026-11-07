import unittest
from acceptance import meets_target
class AcceptanceTest(unittest.TestCase):
    def test_still(self):
        self.assertTrue(meets_target([1,1,1],[.05,.05,.05],28))
    def test_movement_and_boundary(self):
        self.assertFalse(meets_target([2,0,0],[0,0,0],28))
        self.assertFalse(meets_target([0,0,0],[0,0,.1],28))
        self.assertFalse(meets_target([0,0,4.7],[.06,.06,.06],28))
    def test_invalid_or_short(self):
        for t in (10,float('nan'),float('inf')):
            self.assertFalse(meets_target([0,0,0],[0,0,0],t))
        self.assertFalse(meets_target([0,0],[0,0,0],28))
        self.assertFalse(meets_target([-1,0,0],[0,0,0],28))
if __name__=='__main__':unittest.main()
