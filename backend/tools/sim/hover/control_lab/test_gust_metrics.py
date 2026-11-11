import unittest
import numpy as np
from gust_metrics import evaluate

class GustMetricsTest(unittest.TestCase):
    def trace(self):
        t=np.arange(0,55.001,.01);p=np.zeros((len(t),3));a=p.copy()
        event=(t>=25)&(t<28)
        p[event,0]=.03*np.sin((t[event]-25)*np.pi/3)**2
        a[event,1]=2*np.sin((t[event]-25)*np.pi/3)
        return t,p,a
    def test_smooth_excursion_then_still_is_allowed(self):
        t,p,a=self.trace();r=evaluate(t,p,a,25,26,2)
        self.assertTrue(r['recovery_confirmed'])
        self.assertGreaterEqual(r['recovery_start_after_gust_s'],1.75)
        self.assertAlmostEqual(r['peak_displacement_from_pre_gust_mean_mm'],30)
    def test_persistent_rocking_fails(self):
        t,p,a=self.trace();a[t>=28,0]=.2*np.sin(t[t>=28]*8)
        self.assertFalse(evaluate(t,p,a,25,26,2)['recovery_confirmed'])
    def test_smooth_drift_to_wrong_location_fails(self):
        t,p,a=self.trace();p[t>=28,0]=.01
        self.assertFalse(evaluate(t,p,a,25,26,2)['recovery_confirmed'])
    def test_short_post_gust_trace_cannot_pass(self):
        t,p,a=self.trace();k=t<40
        self.assertFalse(evaluate(t[k],p[k],a[k],25,26,2)['recovery_confirmed'])
    def test_nonfinite_data_fails_closed(self):
        t,p,a=self.trace();p[-1,0]=np.nan
        with self.assertRaises(ValueError):evaluate(t,p,a,25,26,2)
    def test_late_rocking_invalidates_earlier_quiet_window(self):
        t,p,a=self.trace();a[t>=50,0]=10*np.sin(t[t>=50]*8)
        self.assertFalse(evaluate(t,p,a,25,26,2)['recovery_confirmed'])
if __name__=='__main__':unittest.main()
