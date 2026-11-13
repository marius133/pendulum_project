from operator import truediv

import requests

api_url = "http://127.0.0.1:7912/api/v1"

def create_filament(filament_data):
    response = requests.post(f"{api_url}/filament", json=filament_data,timeout=5)
    response.raise_for_status()
    return response.json()

def create_spool(filament_id, initial_weight, stock_id):
    spool_data = {
        "filament_id": filament_id,
        "initial_weight": initial_weight,
        "comment": stock_id
    }
    response = requests.post(f"{api_url}/spool", json=spool_data, timeout=5)
    response.raise_for_status()
    return response.json()

def get_filaments():
    response = requests.get(f"{api_url}/filament", timeout=5)
    response.raise_for_status()
    filaments = response.json()
    return filaments

def get_spools(include_archived=True):

    if include_archived:
        allow_archived = "true"
    else:
        allow_archived = "false"

    response = requests.get(
        f"{api_url}/spool",params={f"allow_archived": allow_archived},timeout=5,)
    response.raise_for_status()
    return response.json()