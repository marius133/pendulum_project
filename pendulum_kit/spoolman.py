from __future__ import annotations

from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_URL = "http://localhost:7912"


class SpoolmanError(Exception):
    """Base class for all Spoolman problems."""


class SpoolmanUnavailable(SpoolmanError):
    """Spoolman does not answer (not started, wrong URL, timeout or server error)."""


class SpoolmanNotFound(SpoolmanError):
    """The filament or spool does not exist."""


class InsufficientMaterial(SpoolmanError):
    """Not enough filament in stock. `shortages` maps filament id -> text."""

    def __init__(self, shortages: dict):
        self.shortages = shortages
        super().__init__("Not enough material: " + "; ".join(shortages.values()))


@dataclass(frozen=True)
class SpoolUse:
    spool_id: int
    filament_id: int
    grams: float


class SpoolmanClient:
    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 5.0, retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.api = self.base_url + "/api/v1"
        self.timeout = timeout
        self.session = requests.Session()

        retry = Retry(total=retries, backoff_factor=0.3, status_forcelist=(502, 503, 504),
                      allowed_methods=frozenset({"GET"}))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _request(self, method: str, path: str, **kwargs):
        url = self.api + path
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.exceptions.RetryError as exc:
            raise SpoolmanUnavailable(f"Spoolman at {self.base_url} keeps failing ({exc})") from exc
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            raise SpoolmanUnavailable(
                f"Spoolman does not answer at {self.base_url}. Is it running? "
                f"(docker compose up -d)") from exc

        if resp.status_code == 404:
            raise SpoolmanNotFound(f"{method} {path}: not found")
        if resp.status_code >= 500:
            raise SpoolmanUnavailable(f"{method} {path}: Spoolman server error {resp.status_code}")
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            raise SpoolmanError(f"{method} {path}: rejected ({resp.status_code}): {detail}")
        return resp.json() if resp.content else None

    def _get(self, path, **params):
        return self._request("GET", path, params=params or None)

    def _post(self, path, data):
        return self._request("POST", path, json=data)

    def _put(self, path, data):
        return self._request("PUT", path, json=data)

    def is_available(self) -> bool:
        try:
            self._get("/health")
            return True
        except SpoolmanError:
            return False

    def find_or_create_vendor(self, name: str) -> dict:
        for vendor in self._get("/vendor", name=name):
            if vendor["name"] == name:
                return vendor
        return self._post("/vendor", {"name": name})

    def list_filaments(self, **filters) -> list[dict]:
        return self._get("/filament", **filters)

    def get_filament(self, filament_id: int) -> dict:
        return self._get(f"/filament/{filament_id}")

    def create_filament(self, data: dict) -> dict:
        return self._post("/filament", data)

    def list_spools(self, filament_id: int | None = None) -> list[dict]:
        if filament_id is None:
            return self._get("/spool")
        return self._get("/spool", **{"filament.id": filament_id})

    def get_spool(self, spool_id: int) -> dict:
        return self._get(f"/spool/{spool_id}")

    def create_spool(self, filament_id: int, initial_weight: float, **extra) -> dict:
        return self._post("/spool", {"filament_id": filament_id, "initial_weight": initial_weight,
                                     **extra})

    def use_filament(self, spool_id: int, grams: float) -> dict:
        if grams <= 0:
            raise ValueError("grams must be positive")
        return self._put(f"/spool/{spool_id}/use", {"use_weight": grams})

    def remaining_g(self, filament_id: int) -> float:
        return sum(s.get("remaining_weight") or 0 for s in self.list_spools(filament_id))

    def reserve(self, needed: dict[int, float]) -> list[SpoolUse]:
       
        allocation, shortages = [], {}
        for filament_id, grams in needed.items():
            try:
                spools = self.list_spools(filament_id)
            except SpoolmanNotFound:
                spools = []
            if not spools:
                shortages[filament_id] = f"filament {filament_id}: no spools in stock"
                continue
            big_enough = [s for s in spools if (s.get("remaining_weight") or 0) >= grams]
            if not big_enough:
                best = max((s.get("remaining_weight") or 0) for s in spools)
                shortages[filament_id] = (f"filament {filament_id}: needs {grams:.1f} g, "
                                          f"largest spool has {best:.1f} g")
                continue
            spool = min(big_enough, key=lambda s: s["remaining_weight"])
            allocation.append(SpoolUse(spool["id"], filament_id, grams))
        if shortages:
            raise InsufficientMaterial(shortages)
        return allocation

    def register_use(self, allocation: list[SpoolUse]) -> list[dict]:
        return [self.use_filament(use.spool_id, use.grams) for use in allocation]
