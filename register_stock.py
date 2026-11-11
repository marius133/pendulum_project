import json
from pathlib import Path

from spoolman_client import create_filament, create_spool


def main():
    stock_path = Path(__file__).with_name("makerspace_filament.json")

    with stock_path.open(encoding="utf-8") as file:
        stock = json.load(file)

    for entry in stock:
        filament = create_filament(entry["filament"])
        spool = create_spool(filament["id"], entry["spool"]["initial_weight"])
        print(f"Registered {filament['name']} with spool ID {spool['id']}")


if __name__ == "__main__":
    main()