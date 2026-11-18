"""In-memory stand-in for SpoolmanClient, used by the tests (no Docker needed)."""
from spoolman_client import SpoolmanUnavailableError


class FakeSpoolman:
    def __init__(self, spools=None, available=True):
        self.available = available
        self.used = []                     # (spool_id, grams) for every PUT /use
        self.spools = spools if spools is not None else [
            self.make_spool(1, "PLA+HS (White)", 1000),
            self.make_spool(2, "PLA+HS (Black)", 1000),
            self.make_spool(3, "PLA+HS (Light Khaki)", 1000),
        ]

    @staticmethod
    def make_spool(spool_id, name, remaining, density=1.24):
        return {"id": spool_id, "remaining_weight": remaining, "initial_weight": 1000, "used_weight": 1000 - remaining,
                "filament": {"id": spool_id, "name": name, "material": "PLA+HS", "density": density, "diameter": 1.75}}

    def _check(self):
        if not self.available:
            raise SpoolmanUnavailableError("The material stock (Spoolman) is not answering.")

    def get_spools(self, include_archived=True):
        self._check()
        return [dict(s) for s in self.spools]

    def use_filament(self, spool_id, weight_g):
        self._check()
        for s in self.spools:
            if s["id"] == spool_id:
                s["remaining_weight"] -= weight_g
                s["used_weight"] += weight_g
        self.used.append((spool_id, weight_g))
