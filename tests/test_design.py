import pytest

from pendulum_kit.design import DesignError, DesignRequest, bisect, design_for_period, find_bracket


def test_bisect_finds_root():
    assert bisect(lambda x: x ** 2, 0, 3, 2.0) == pytest.approx(2 ** 0.5, abs=1e-5)
    assert bisect(lambda x: -x, 0, 3, -1.0) == pytest.approx(1.0, abs=1e-5)   # decreasing too


def test_bisect_rejects_unbracketed():
    with pytest.raises(ValueError):
        bisect(lambda x: x, 0, 1, 5)


def test_find_bracket_non_monotonic():
    # falls then rises: the target 0.5 is crossed twice; pick the longer one
    (lo, hi), fmin, _ = find_bracket(lambda x: (x - 1) ** 2, 0, 3, 0.5, samples=31)
    assert lo <= 1 + 0.5 ** 0.5 <= hi
    assert fmin == pytest.approx(0, abs=0.01)


@pytest.mark.parametrize("target", [0.45, 0.6, 0.75])
def test_design_hits_target(params, target):
    result = design_for_period(params, DesignRequest(target))
    assert abs(result.error_percent) < 0.1
    assert result.params.check() == []


def test_customer_choices_are_kept(params):
    result = design_for_period(params, DesignRequest(0.65, weight_diameter_mm=40,
                                                     axle_diameter_mm=6))
    assert result.params["weight"]["diameter"] == 40
    assert result.params["axle"]["diameter"] == 6


def test_size_and_material_limits(params):
    result = design_for_period(params, DesignRequest(0.6, max_height_mm=150))
    assert result.params.total_height <= 150
    with pytest.raises(DesignError, match="too long"):
        design_for_period(params, DesignRequest(0.8, max_height_mm=100))
    with pytest.raises(DesignError, match="material"):
        design_for_period(params, DesignRequest(0.6, max_material_g=10))


def test_impossible_periods(params):
    with pytest.raises(DesignError, match="too long"):
        design_for_period(params, DesignRequest(5.0))
    with pytest.raises(DesignError, match="too short"):
        design_for_period(params, DesignRequest(0.05))


def test_request_from_dict_ignores_unknown_keys():
    req = DesignRequest.from_dict({"target_period_s": 0.7, "customer": "Ola"})
    assert req.target_period_s == 0.7
