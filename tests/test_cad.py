"""CAD tests. Skipped when CadQuery is not installed."""
import pytest

cq = pytest.importorskip("cadquery")

from pendulum_kit.cad import cad_volumes, export_kit  # noqa: E402
from pendulum_kit.geometry import kit_geometry  # noqa: E402


def test_cad_volumes_match_geometry(params):
    cad = cad_volumes(params)
    calc = kit_geometry(params)
    for part, volume in cad.items():
        assert volume == pytest.approx(calc[part].volume, rel=0.01), part


def test_export_writes_3mf(params, tmp_path):
    files = export_kit(params, tmp_path)
    for name in ("base", "stand_side_1", "stand_side_2", "arm", "weight", "axle", "plate_1"):
        assert files[name].suffix == ".3mf"
        assert files[name].stat().st_size > 0
    assert (tmp_path / "params.json").exists()
