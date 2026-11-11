import requests
import json

with open("./spoolman_client/filaments.json") as file:
    stock = json.load(file)

api_url = "http://127.0.0.1:7912/api/v1"

def get_filaments():
    response = requests.get(f"{api_url}/filament", timeout=5)
    response.raise_for_status()
    filaments = response.json()
    print(filaments)

    return filaments