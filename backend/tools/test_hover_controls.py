"""Control contract tests without a connected flight controller."""
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ground_control'))
from hop import Hop, HEIGHT_MIN, HEIGHT_MAX

class HoverControls(unittest.TestCase):
    def setUp(self):
        self.h = Hop.__new__(Hop)
        self.h.lock = threading.Lock()
        self.h.active = self.h.interactive = True
        self.h.land_requested = False
        self.h.status = {'state': 'locked'}
        self.h.offset = [0., 0.]
        self.h.height = .02
        self.h.link = Mock(sysid=1, compid=1)

    def test_centimetre_and_target_frame(self):
        self.h.move('x', 1); self.h.move('y', -1); self.h.move('z', 1)
        self.h._hold_target([1, 2, 3], .5)
        args = self.h.link.send.call_args.args
        self.assertEqual(args[6:9], (1.01, 1.99, 2.97))

    def test_bounds(self):
        for _ in range(100):
            self.h.move('x', 1); self.h.move('y', -1); self.h.move('z', 1)
        self.assertEqual(self.h.offset, [.05, -.05])
        self.assertEqual(self.h.height, HEIGHT_MAX)
        for _ in range(100): self.h.move('z', -1)
        self.assertEqual(self.h.height, HEIGHT_MIN)

    def test_land_blocks_further_moves(self):
        self.h.land()
        self.assertTrue(self.h.land_requested)
        self.h.move('x', 1)
        self.assertEqual(self.h.offset, [0., 0.])
        self.h.link.command.assert_not_called()

    def test_inactive_takeoff_and_bad_commands(self):
        for state in ['arming', 'climbing', 'landing', 'done']:
            self.h.status['state'] = state
            self.h.move('x', 1); self.h.land()
            self.assertFalse(self.h.land_requested)
        self.h.status['state'] = 'locked'
        for axis, direction in [('x', 100), ('z', float('nan')), ('q', 1), ('x', True)]:
            self.h.move(axis, direction)
        self.h.active = False
        self.h.move('x', 1)
        self.assertEqual(self.h.offset, [0., 0.])
        self.assertEqual(self.h.height, .02)

    def test_emergency_stop_force_disarms(self):
        self.h.release('Emergency stop')
        self.assertFalse(self.h.active)
        calls = self.h.link.command.call_args_list
        self.assertEqual(sum(c.args[1:] == (0, 21196) for c in calls), 3)
        self.assertEqual(self.h.status['state'], 'killed')

class HoverOrigin(unittest.TestCase):
    def setUp(self):
        self.h = Hop.__new__(Hop)
        self.h.link = Mock(sysid=1, compid=1)
        self.h.link.state = {"lat_fc": 0, "lon_fc": 0, "alt_msl": 0}
        self.h.kill = Mock()

    def keep(self, cond, send, timeout):
        for _ in range(3):
            if cond(): break
            send()
        return True

    def test_cold_boot_restores_and_confirms(self):
        import time
        def receive(fn, sysid, lat, lon, alt, stamp):
            self.h.link.state.update(origin=(lat, lon, alt), origin_t=time.time())
        self.h.link.send.side_effect = receive
        self.assertTrue(self.h.ensure_origin(self.keep))
        self.assertEqual(self.h.link.state['origin'], (476625072, -1222951904, 18790))
        self.h.kill.assert_not_called()

    def test_missing_ack_blocks_progress(self):
        self.assertFalse(self.h.ensure_origin(self.keep))
        self.h.kill.assert_called_once()

    def test_wrong_origin_blocks_progress(self):
        import time
        def wrong(*args):
            self.h.link.state.update(origin=(1, 2, 3), origin_t=time.time())
        self.h.link.send.side_effect = wrong
        self.assertFalse(self.h.ensure_origin(self.keep))

    def test_existing_fresh_origin_is_not_overwritten(self):
        import time
        self.h.link.command.side_effect = lambda *args: self.h.link.state.update(origin_t=time.time())
        self.assertTrue(self.h.ensure_origin(self.keep))
        self.h.link.send.assert_not_called()

    def test_stale_origin_is_requested_again(self):
        self.h.link.state.update(origin_t=1, origin=(1, 2, 3))
        self.assertFalse(self.h.ensure_origin(self.keep))
        self.assertEqual(self.h.link.send.call_count, 3)

    def test_coordinate_validation_and_pairing(self):
        self.assertTrue(Hop.valid_origin(0, 10, 0))
        self.assertTrue(Hop.valid_origin(10, 0, 0))
        self.assertFalse(Hop.valid_origin(float('nan'), 10, 0))
        self.assertFalse(Hop.valid_origin(0, 0, 0))
        self.assertFalse(Hop.valid_origin(91, 10, 0))
        self.h.link.state.update(lat_fc=47, lon_fc=None, lat=None, lon=-122)
        self.assertEqual(self.h.origin_reference(), (47.6625072, -122.2951904, 18.79))

if __name__ == '__main__': unittest.main()
