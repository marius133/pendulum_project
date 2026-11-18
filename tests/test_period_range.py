import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import app
from configurator import configure
from production import parameters_for_axle
from tests.fake_spoolman import FakeSpoolman


class PeriodRangeTests(unittest.TestCase):
    def test_form_shows_range_next_to_period_even_if_stock_is_unavailable(self):
        with patch("app.spoolman", FakeSpoolman(available=False)):
            response = app.test_client().get("/")

        self.assertEqual(response.status_code, 503)
        html = response.get_data(as_text=True)
        self.assertIn('aria-describedby="period-range"', html)
        self.assertIn('data-url="/period-range"', html)
        self.assertIn('min="4" value="5"', html)
        minimum, maximum = configure(parameters_for_axle(), 0.45, 1.24).achievable_range_s
        self.assertIn(f"Min {minimum:.3f} s · Max {maximum:.3f} s", html)

    def test_range_uses_requested_axle_diameter(self):
        client = app.test_client()
        default = client.get("/period-range").get_json()
        response = client.get("/period-range", query_string={"axle_diameter_mm": 10})

        self.assertEqual(response.status_code, 200)
        minimum, maximum = configure(parameters_for_axle(10), 0.45, 1.24).achievable_range_s
        result = response.get_json()
        self.assertAlmostEqual(result["minimum_s"], minimum)
        self.assertAlmostEqual(result["maximum_s"], maximum)
        self.assertNotAlmostEqual(result["minimum_s"], default["minimum_s"], places=3)

    def test_minimum_axle_diameter_is_accepted(self):
        response = app.test_client().get("/period-range", query_string={"axle_diameter_mm": 4})
        self.assertEqual(response.status_code, 200)

    def test_configured_minimum_updates_form_and_period_range(self):
        parameters = parameters_for_axle()
        parameters["min_axle_diameter_mm"] = 4.5
        client = app.test_client()
        with TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "parameters.json").write_text(json.dumps(parameters), encoding="utf-8")
            with patch("production.PROJECT_DIR", project_dir), patch("app.spoolman", FakeSpoolman()):
                form = client.get("/")
                too_small = client.get("/period-range", query_string={"axle_diameter_mm": 4})
                minimum = client.get("/period-range", query_string={"axle_diameter_mm": 4.5})

        self.assertIn('min="4.5"', form.get_data(as_text=True))
        self.assertEqual(too_small.status_code, 400)
        self.assertEqual(too_small.get_json()["error"], "Axle diameter must be at least 4.5 mm")
        self.assertEqual(minimum.status_code, 200)

    def test_invalid_axle_diameter_does_not_return_a_range(self):
        client = app.test_client()
        for diameter in ("", "0", "1", "3.99", "20"):
            with self.subTest(diameter=diameter):
                response = client.get("/period-range", query_string={"axle_diameter_mm": diameter})
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

    def test_order_with_thin_axle_is_rejected_before_saving(self):
        form = {
            "target_period_s": "0.45",
            "axle_diameter_mm": "1",
            "base_spool_id": "1",
            "side_spool_id": "1",
            "pendulum_spool_id": "1",
            "axle_spool_id": "1",
        }
        with patch("app.spoolman", FakeSpoolman()), patch("app.save_order") as save_order:
            response = app.test_client().post("/orders", data=form)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Axle diameter must be at least 4 mm", response.get_data(as_text=True))
        save_order.assert_not_called()
