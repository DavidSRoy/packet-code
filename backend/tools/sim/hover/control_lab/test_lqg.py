"""Check model timing against an independently stepped delayed actuator."""
import math
import unittest
from collections import deque

import numpy as np

from lqg import LQG


class LQGTest(unittest.TestCase):
    def test_zero_measurements_stay_zero(self):
        controller = LQG(.0025)
        for _ in range(1000):
            self.assertEqual(controller.update(0., 0.), 0.)
            np.testing.assert_array_equal(controller.state, 0.)

    def test_model_matches_independent_actuator_and_sensor(self):
        dt = .0025
        controller = LQG(dt)
        queue = deque([0.] * 12, maxlen=12)
        angle, rate, motor, gyro = .01, -.02, .03, -.01
        slow, fast = .2, -.1
        state = np.array([angle, rate, motor, slow, fast, gyro, *queue])
        for i in range(500):
            command = .05 * math.sin(i * .17)
            applied = queue[0]
            queue.append(command)
            motor += (1 - math.exp(-dt / .015)) * (applied - motor)
            slow *= math.exp(-dt / .25)
            fast *= math.exp(-dt / .025)
            acceleration = 73.5 * motor + slow + fast
            angle += rate * dt + .5 * acceleration * dt * dt
            rate += acceleration * dt
            gyro += (1 - math.exp(-2 * math.pi * 40 * dt)) * (rate - gyro)
            state = controller.A @ state + controller.B[:, 0] * command
            np.testing.assert_allclose(
                state, [angle, rate, motor, slow, fast, gyro, *queue],
                atol=1e-12, rtol=1e-12,
            )

    def test_clipped_command_is_recorded_in_delay_queue(self):
        controller = LQG(.0025)
        output = controller.update(10., 10.)
        self.assertEqual(abs(output), .35)
        self.assertEqual(controller.state[-1], output)
        self.assertTrue(np.isfinite(controller.state).all())

    def test_constant_target_is_an_equilibrium(self):
        controller = LQG(.0025)
        controller.state[0] = .1
        for _ in range(1000):
            self.assertAlmostEqual(controller.update(.1, 0., target=.1), 0., places=10)

    def test_gyro_measurement_history_has_exact_delay(self):
        controller = LQG(.0025, gyro_delay=.0075)
        state = np.zeros(21)
        state[5] = 1.
        for _ in range(3):
            self.assertEqual((controller.C @ state)[1], 0.)
            state = controller.A @ state
        self.assertEqual((controller.C @ state)[1], 1.)
        self.assertEqual(np.flatnonzero(controller.B[:, 0]).tolist(), [17])

    def test_rate_feedforward_tracks_constant_ramp(self):
        c = LQG(.0025,gyro_delay=.0075)
        c.state[0]=.01
        c.state[1]=c.state[5]=.02
        c.state[18:]=.02
        for i in range(1000):
            target=.01+i*.0025*.02
            self.assertAlmostEqual(c.update(target,.02,target=target,target_rate=.02),0.,places=9)


if __name__ == '__main__':
    unittest.main()
