"""Thin client for the Spoolman REST API (material stock).

Spoolman API documentation: http://localhost:7912/api/v1/docs
"""
import requests


class SpoolmanError(Exception):
    """Spoolman answered, but with an error (for example 404 or 422)."""


class SpoolmanUnavailableError(SpoolmanError):
    """Spoolman did not answer (not started, wrong port, or timeout)."""


class SpoolmanClient:
    def __init__(self, base_url: str = "http://127.0.0.1:7912/api/v1", timeout: float = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs):
        """Send one request and turn network/HTTP problems into our own exceptions."""
        try:
            response = requests.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as error:
            raise SpoolmanUnavailableError(
                f"The material stock (Spoolman at {self.base_url}) is not answering. "
                f"Start it with 'docker compose up -d' and try again."
            ) from error
        if not response.ok:
            raise SpoolmanError(f"Spoolman returned {response.status_code} for {method} {path}: {response.text[:200]}")
        return response.json()

    def get_spools(self, include_archived: bool = True):
        return self._request("GET", "/spool",
                             params={"allow_archived": "true" if include_archived else "false"})

    def get_spool(self, spool_id: int):
        return self._request("GET", f"/spool/{spool_id}")

    def get_filaments(self):
        return self._request("GET", "/filament")

    def create_filament(self, filament_data: dict):
        return self._request("POST", "/filament", json=filament_data)

    def create_spool(self, filament_id: int, initial_weight: float, stock_id: str):
        spool_data = {
            "filament_id": filament_id,
            "initial_weight": initial_weight,
            "comment": stock_id,
        }
        return self._request("POST", "/spool", json=spool_data)

    def use_filament(self, spool_id: int, weight_g: float):
        """Register that `weight_g` grams were used from a spool (PUT /spool/{id}/use)."""
        return self._request("PUT", f"/spool/{spool_id}/use", json={"use_weight": round(weight_g, 2)})
