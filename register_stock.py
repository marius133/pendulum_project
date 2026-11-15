import json
from pathlib import Path
from spoolman_client import SpoolmanClient

def main():
    spoolman = SpoolmanClient()
    stock_path = Path(__file__).with_name("makerspace_filament.json")

    # Indexing existing filaments by name so the import can reuse them
    filaments_by_name = {filament["name"]: filament for filament in spoolman.get_filaments()}

    # The import stores each spools stock id in its spoolman comment
    registered_stock_ids = {spool.get("comment") for spool in spoolman.get_spools()}

    with stock_path.open(encoding="utf-8") as file:
        stock = json.load(file)

    for entry in stock:
        spool_data = entry["spool"]
        stock_id = spool_data["stock_id"]

        if stock_id in registered_stock_ids:
            print(f"Already registered: {stock_id}")
            continue

        filament_data = entry["filament"]
        name = filament_data["name"]
        filament = filaments_by_name.get(name)

        if filament is None:
            filament = spoolman.create_filament(filament_data)
            filaments_by_name[name] = filament

        spool = spoolman.create_spool(filament["id"], spool_data["initial_weight"], stock_id)

        registered_stock_ids.add(stock_id)
        print(f"Registered {name} with spool ID {spool['id']}")


if __name__ == "__main__":
    main()