# AI-assisted (Claude, Anthropic): whole file. Reviewed and tested by the group.
import math
import unittest

from physics import SOLID, PrintSettings, analyze_pendulum, calculate_period, kit_masses, part_mass
from validation import load_parameters


class PhysicsTests(unittest.TestCase):
    def setUp(self):
        self.p = load_parameters("parameters.json")

    def test_axle_volume_matches_cylinder_formula(self):
        r, length = self.p["axle_diameter_mm"] / 2, self.p["stand_gap_mm"] + 2 * self.p["stand_thickness_mm"]
        expected = math.pi * r ** 2 * length
        self.assertAlmostEqual(part_mass("axle", self.p, 1.24, SOLID, 0.1).volume_mm3, expected, delta=0.02 * expected)

    def test_base_volume_matches_box_minus_slots(self):
        p = self.p
        slots = 2 * (p["stand_width_mm"] + p["slot_clearance_mm"]) * (p["stand_thickness_mm"] + p["slot_clearance_mm"]) * p["slot_depth_mm"]
        expected = p["base_width_mm"] * p["base_length_mm"] * p["base_thickness_mm"] - slots
        self.assertAlmostEqual(part_mass("base", p, 1.24, SOLID).volume_mm3, expected, delta=0.01 * expected)

    def test_infill_makes_parts_lighter_but_not_lighter_than_infill_fraction(self):
        printed = part_mass("base", self.p, 1.24, PrintSettings(infill=0.15))
        solid = part_mass("base", self.p, 1.24, SOLID)
        self.assertLess(printed.mass_g, solid.mass_g)
        self.assertGreater(printed.mass_g, 0.15 * solid.mass_g)

    def test_simple_pendulum_formula(self):
        # point mass: I = m d^2 -> T = 2 pi sqrt(d/g)
        self.assertAlmostEqual(calculate_period(0.1 * 0.25 ** 2, 0.1, 0.25), 2 * math.pi * math.sqrt(0.25 / 9.81))

    def test_period_does_not_depend_on_density_for_solid_part(self):
        a = analyze_pendulum(self.p, 1.24, SOLID).period_s
        b = analyze_pendulum(self.p, 1.04, SOLID).period_s
        self.assertAlmostEqual(a, b, places=9)

    def test_default_pendulum_matches_independent_calculation(self):
        # 0.4364 s was calculated with a separate 0.1 mm voxel script for the report
        self.assertAlmostEqual(analyze_pendulum(self.p, 1.24, SOLID).period_s, 0.4364, delta=0.002)

    def test_kit_masses_cover_all_parts(self):
        masses = kit_masses(self.p, {n: 1.24 for n in ("base", "stand", "axle", "pendulum")}, PrintSettings())
        self.assertEqual(masses["stand"].count, 2)
        self.assertTrue(all(m.mass_g > 0 for m in masses.values()))


if __name__ == "__main__":
    unittest.main()
