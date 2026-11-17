import unittest

from configurator import configure
from validation import load_parameters, validate_parameters


class ConfiguratorTests(unittest.TestCase):
    def setUp(self):
        self.p = load_parameters("parameters.json")

    def test_reachable_target_is_met_within_one_percent(self):
        for target in (0.40, 0.45, 0.50):
            cfg = configure(self.p, target, 1.24)
            self.assertLess(abs(cfg.error_percent), 1.0, target)
            validate_parameters(cfg.parameters)   # clearance and build volume still OK

    def test_unreachable_target_gives_closest_design(self):
        cfg = configure(self.p, 2.0, 1.24)
        self.assertFalse(cfg.within())
        self.assertAlmostEqual(cfg.period_s, cfg.achievable_range_s[1], delta=0.005)

    def test_longer_target_gives_longer_arm(self):
        short = configure(self.p, 0.40, 1.24).parameters["pendulum_arm_length_mm"]
        long = configure(self.p, 0.50, 1.24).parameters["pendulum_arm_length_mm"]
        self.assertGreater(long, short)


if __name__ == "__main__":
    unittest.main()
