"""Runs orders through production with a fake Spoolman and a fake 3MF export."""
import json
from dataclasses import asdict
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import production
from order import Order
from spoolman_client import SpoolmanUnavailableError
from tests.fake_spoolman import FakeSpoolman

SPOOLS = {"base": 1, "side": 2, "pendulum": 3, "axle": 1}


def fake_export(order_number, parameters, result=None):
    target = production.OUTPUT_DIR / f"order-{order_number}"
    target.mkdir(parents=True)
    (target / "parameters.json").write_text(json.dumps(parameters))
    return target


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.patches = [mock.patch.object(production, "OUTPUT_DIR", tmp / "output"),
                        mock.patch.object(production, "ORDERS_DIR", tmp / "orders"),
                        mock.patch.object(production, "export_order", side_effect=fake_export)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_order_is_produced_and_filament_is_registered(self):
        stock = FakeSpoolman()
        result = production.process_order(1, Order(0.45, 5.0, dict(SPOOLS)), stock)
        self.assertEqual(result.status, "produced")
        self.assertLess(abs(result.error_percent), 2)
        self.assertEqual({sid for sid, _ in stock.used}, {1, 2, 3})
        self.assertTrue((production.OUTPUT_DIR / "order-1" / "parameters.json").exists())

    def test_not_enough_filament_postpones_without_export(self):
        stock = FakeSpoolman([FakeSpoolman.make_spool(1, "White", 10), FakeSpoolman.make_spool(2, "Black", 1000),
                              FakeSpoolman.make_spool(3, "Khaki", 1000)])
        result = production.process_order(2, Order(0.45, 5.0, dict(SPOOLS)), stock)
        self.assertEqual(result.status, "postponed")
        self.assertIn("spool #1", result.reason)
        self.assertEqual(stock.used, [])
        self.assertFalse((production.OUTPUT_DIR / "order-2").exists())

    def test_unreachable_period_is_rejected(self):
        stock = FakeSpoolman()
        result = production.process_order(3, Order(1.5, 5.0, dict(SPOOLS)), stock)
        self.assertEqual(result.status, "rejected")
        self.assertIn("cannot be reached", result.reason)
        self.assertEqual(stock.used, [])

    def test_confirmed_debit_with_timed_out_response_is_not_retried(self):
        stock = FakeSpoolman()
        order = Order(0.45, 5.0, dict(SPOOLS))
        production.ORDERS_DIR.mkdir()
        (production.ORDERS_DIR / "order-1.json").write_text(json.dumps(asdict(order)))
        apply_debit = stock.use_filament

        def lose_second_response(spool_id, weight):
            self.assertEqual(production.load_result(1).status, "needs_review")
            apply_debit(spool_id, weight)
            if len(stock.used) == 2:
                raise SpoolmanUnavailableError("The response timed out")

        with mock.patch.object(stock, "use_filament", side_effect=lose_second_response):
            result = production.process_order(1, order, stock)
            self.assertEqual(result.status, "needs_review")
            self.assertEqual(production.load_result(1).status, "needs_review")
            self.assertEqual(production.pending_orders(), [])
            self.assertEqual(production.process_order(1, order, stock).status, "needs_review")

        self.assertEqual(len(stock.used), 2)

    def test_legacy_output_does_not_stop_later_orders(self):
        order = Order(0.45, 5.0, dict(SPOOLS))
        production.ORDERS_DIR.mkdir()
        for number in (1, 2):
            (production.ORDERS_DIR / f"order-{number}.json").write_text(json.dumps(asdict(order)))
        legacy_output = production.OUTPUT_DIR / "order-1"
        legacy_output.mkdir(parents=True)
        (legacy_output / "stand.3mf").touch()

        stock = FakeSpoolman()
        results = production.run_production(stock, workers=1)
        self.assertEqual([(result.order_number, result.status) for result in results], [(2, "produced")])
        self.assertEqual(len(stock.used), 3)
        self.assertTrue((legacy_output / "stand.3mf").is_file())

    def test_unknown_filament_density_postpones_order(self):
        stock = FakeSpoolman()
        stock.spools[2]["filament"]["density"] = None
        result = production.process_order(1, Order(0.45, 5.0, dict(SPOOLS)), stock)
        self.assertEqual(result.status, "postponed")
        self.assertIn("density", result.reason)
        self.assertEqual(stock.used, [])

    def test_spoolman_down_raises_clear_error(self):
        with self.assertRaises(SpoolmanUnavailableError):
            production.process_order(4, Order(0.45, 5.0, dict(SPOOLS)), FakeSpoolman(available=False))


if __name__ == "__main__":
    unittest.main()
