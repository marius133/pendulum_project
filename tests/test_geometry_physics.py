import math

import pytest

from pendulum_kit.geometry import (PartGeometry, arm_area_exact, arm_geometry, arm_inside,
                                   kit_geometry, raster_moments)
from pendulum_kit.physics import (G_MM_S2, amplitude_correction, kit_masses, part_mass,
                                  pendulum_properties, shell_volume, small_angle_period)

PRINT = {"walls": 2, "line_width": 0.45, "top_bottom_layers": 4, "layer_height": 0.2}


def test_raster_rectangle_matches_formulas():
    # rectangle |u| <= 2, -10 <= v <= 0: area 40, centroid v = -5, polar = w^3 L/12 + w L^3/3
    area, mean_v, polar = raster_moments(lambda u, v: (abs(u) <= 2) & (v <= 0) & (v >= -10),
                                         (-2, 2), (-10, 0), cell=0.01)
    assert area == pytest.approx(40, rel=1e-3)
    assert mean_v == pytest.approx(-5, rel=1e-3)
    assert polar == pytest.approx(4 ** 3 * 10 / 12 + 4 * 10 ** 3 / 3, rel=1e-3)


def test_arm_area_matches_exact_formula(params):
    for length, width in [(110, 10), (60, 16), (180, 4)]:
        p = params.with_updates({"arm": {"length": length, "width": width},
                                 "stand": {"height": length + 30}}, validate=False)
        assert arm_geometry(p).volume == pytest.approx(arm_area_exact(p) * p["arm"]["thickness"],
                                                       rel=1e-3)


def test_fast_arm_moments_match_full_raster(params):
    g = arm_geometry(params)
    a = params["arm"]
    area, mean_v, polar = raster_moments(arm_inside(params), (-8, 8), (-a["length"], 8), 0.05)
    assert g.com_distance == pytest.approx(-mean_v, rel=1e-4)
    assert g.second_moment == pytest.approx(polar * a["thickness"], rel=1e-4)


def test_all_parts_have_positive_geometry(params):
    for g in kit_geometry(params).values():
        assert g.volume > 0 and g.side_area > 0 and g.cap_area > 0


def test_mass_solid_and_hollow():
    cube = PartGeometry("cube", volume=1000.0, side_area=400.0, cap_area=200.0)   # 10 mm cube
    solid = part_mass(cube, 1.24, infill=1.0, print_settings=PRINT)
    assert solid.mass_g == pytest.approx(1.24)
    hollow = part_mass(cube, 1.24, infill=0.0, print_settings=PRINT)
    shell = 400 * 0.9 + 200 * 0.8
    assert hollow.mass_g == pytest.approx(1.24 * shell / 1000)
    assert shell_volume(PartGeometry("thin", 10.0, 400.0, 200.0), PRINT) == 10.0   # capped


def test_more_infill_more_mass(params):
    light = kit_masses(params.with_updates({"print": {"infill": 0.1}}))
    heavy = kit_masses(params.with_updates({"print": {"infill": 0.5}}))
    assert heavy["base"].mass_g > light["base"].mass_g
    assert heavy["weight"].mass_g == light["weight"].mass_g      # weight has its own 100 %


def test_simple_pendulum_limit():
    # point mass at 100 mm: I = m d^2 -> T = 2 pi sqrt(d/g)
    assert small_angle_period(5 * 100 ** 2, 5, 100) == pytest.approx(
        2 * math.pi * math.sqrt(100 / G_MM_S2))


def test_amplitude_correction():
    assert amplitude_correction(1.0, 0) == 1.0
    # exact value 2K(sin 15 deg)/pi = 1.01741 for 30 degrees amplitude
    assert amplitude_correction(1.0, math.radians(30)) == pytest.approx(1.01741, abs=1e-4)


def test_period_is_plausible(params):
    pend = pendulum_properties(params)
    # between a point mass at the weight centre and at the arm end
    lo = 2 * math.pi * math.sqrt(pend.com_distance_mm / G_MM_S2)
    assert pend.period_s > lo
    assert 0.5 < pend.period_s < 0.8
    assert pend.period_amplitude_s > pend.period_s


def test_denser_weight_moves_centre_down(params):
    light = pendulum_properties(params)
    heavy = pendulum_properties(params.with_updates({"materials": {"weight": {"density": 2.5}}}))
    assert heavy.com_distance_mm > light.com_distance_mm
