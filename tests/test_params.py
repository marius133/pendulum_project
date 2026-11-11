import json

import pytest

from pendulum_kit.params import KitParameters, ParameterError


def test_default_parameters_are_valid(params):
    assert params.check() == []


def test_save_and_load_roundtrip(params, tmp_path):
    params.save(tmp_path / "p.json")
    assert KitParameters.load(tmp_path / "p.json").to_dict() == params.to_dict()


def test_with_updates_does_not_change_original(params):
    longer = params.with_updates({"arm": {"length": 120}, "stand": {"height": 150}})
    assert longer["arm"]["length"] == 120
    assert params["arm"]["length"] == 110
    assert longer["arm"]["width"] == params["arm"]["width"]


@pytest.mark.parametrize("update, text", [
    ({"arm": {"length": -5}}, "arm/length"),
    ({"weight": {"diameter": 0}}, "weight/diameter"),
    ({"print": {"infill": 1.5}}, "print/infill"),
    ({"print": {"walls": 1.5}}, "print/walls"),
    ({"materials": {"arm": {"density": -1}}}, "materials/arm/density"),
])
def test_schema_rules(params, update, text):
    with pytest.raises(ParameterError) as err:
        params.with_updates(update)
    assert any(text in e for e in err.value.errors)


def test_missing_section_is_reported(params):
    data = params.to_dict()
    del data["axle"]
    with pytest.raises(ParameterError, match="axle"):
        KitParameters(data)


@pytest.mark.parametrize("update, text", [
    ({"arm": {"length": 135}}, "clearance to the base"),          # arm hits the base
    ({"weight": {"height": 105}}, "weight (height"),               # weight runs into the hub
    ({"weight": {"diameter": 12}}, "weight diameter"),             # arm hole bigger than weight
    ({"arm": {"hub_diameter": 8}}, "hub"),
    ({"stand": {"height": 300}, "arm": {"length": 200}}, "build volume"),
    ({"stand": {"tab_length": 40}}, "tab"),
    ({"stand": {"axle_offset": 2}}, "too close to the top"),
])
def test_geometric_rules(params, update, text):
    errors = params.with_updates(update, validate=False).check()
    assert any(text in e for e in errors), errors


def test_all_errors_reported_together(params):
    errors = params.with_updates({"arm": {"length": 135}, "weight": {"diameter": 12}},
                                 validate=False).check()
    assert len(errors) >= 2


def test_derived_dimensions(params):
    assert params.inner_gap == 30 + 2 * 2
    assert params.pivot_height == 140 - 12
    assert params.ground_clearance == 128 - 110
    assert params.weight_centre_distance == 110 - 10
    assert params.total_height == 146


def test_default_file_is_plain_json():
    from pendulum_kit.params import DEFAULT_PARAMS_FILE
    json.loads(DEFAULT_PARAMS_FILE.read_text())
