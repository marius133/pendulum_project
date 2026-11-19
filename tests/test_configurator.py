# AI-assisted (Claude, Anthropic): setUp and the tests reachable_target, unreachable_target and longer_target. The two stand tests are our own. Reviewed by the group.
import unittest

from configurator import configure
from validation import load_parameters, minimum_stand_length_mm, validate_parameters


class ConfiguratorTests(unittest.TestCase):
    def setUp(self):
        self.p = load_parameters("parameters.json")

    def test_reachable_target_is_met_within_one_percent(self):
        for target in (0.40, 0.45, 0.50):
            cfg = configure(self.p, target, 1.24)
            self.assertLess(abs(cfg.error_percent), 1.0, target)
            validate_parameters(cfg.parameters)   # clearance and build volume still OK

    def test_stand_raises_to_clear_the_configured_pendulum(self):
        short = configure(self.p, 0.45, 1.24)
        tall = configure(self.p, 0.70, 1.24)
        self.assertEqual(short.parameters["stand_length_mm"], self.p["stand_length_mm"])
        self.assertTrue(tall.within())
        self.assertGreater(tall.parameters["stand_length_mm"], self.p["stand_length_mm"])
        self.assertAlmostEqual(tall.parameters["stand_length_mm"], minimum_stand_length_mm(tall.parameters))
        validate_parameters(tall.parameters)

    def test_stand_does_not_exceed_a_smaller_build_volume(self):
        self.p["build_volume_mm"] = [120, 110, 125]
        self.p["base_width_mm"] = 80.0
        self.p["base_length_mm"] = 100.0
        cfg = configure(self.p, 0.70, 1.24)
        self.assertFalse(cfg.within())
        self.assertLessEqual(cfg.parameters["stand_length_mm"], 125)
        validate_parameters(cfg.parameters)

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
