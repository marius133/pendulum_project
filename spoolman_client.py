import requests

class SpoolmanClient:
    def __init__(self,base_url: str = "http://127.0.0.1:7912/api/v1",timeout: float = 5,):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_spools(self, include_archived: bool = True):
        response = requests.get(
            f"{self.base_url}/spool",
            params={"allow_archived": "true" if include_archived else "false"},
            timeout=self.timeout,)
        response.raise_for_status()
        return response.json()

    def get_filaments(self):
        response = requests.get(f"{self.base_url}/filament", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def create_filament(self, filament_data: dict):
        response = requests.post(f"{self.base_url}/filament",json=filament_data,timeout=self.timeout,)
        response.raise_for_status()
        return response.json()

    def create_spool(self, filament_id: int, initial_weight: float, stock_id: str):
        spool_data = {
            "filament_id": filament_id,
            "initial_weight": initial_weight,
            "comment": stock_id,
        }
        response = requests.post(f"{self.base_url}/spool",json=spool_data,timeout=self.timeout,)
        response.raise_for_status()
        return response.json()