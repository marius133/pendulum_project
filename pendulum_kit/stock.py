from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .spoolman import DEFAULT_URL, SpoolmanClient, SpoolmanError

DEFAULT_STOCK_FILE = Path(__file__).resolve().parent.parent / "data" / "filaments.json"

REQUIRED_KEYS = ("name", "vendor", "material", "density", "diameter", "spool_net_weight")


def load_stock_file(path=DEFAULT_STOCK_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        stock = json.load(f)
    for i, fil in enumerate(stock["filaments"]):
        missing = [k for k in REQUIRED_KEYS if k not in fil]
        if missing:
            raise ValueError(f"filament #{i} ({fil.get('name', '?')}) is missing {missing}")
        if fil["density"] <= 0 or fil["diameter"] <= 0 or fil["spool_net_weight"] <= 0:
            raise ValueError(f"filament {fil['name']}: density, diameter and weight must be positive")
    return stock


def register_stock(client: SpoolmanClient, stock: dict) -> list[dict]:
    report = []
    location = stock.get("location")
    for fil in stock["filaments"]:
        vendor = client.find_or_create_vendor(fil["vendor"])
        existing = [f for f in client.list_filaments(name=fil["name"])
                    if f["name"] == fil["name"] and (f.get("vendor") or {}).get("id") == vendor["id"]]
        if existing:
            filament, created = existing[0], False
        else:
            data = {
                "name": fil["name"],
                "vendor_id": vendor["id"],
                "material": fil["material"],
                "density": fil["density"],
                "diameter": fil["diameter"],
                "weight": fil["spool_net_weight"],
            }
            if "color_hex" in fil:
                data["color_hex"] = fil["color_hex"]
            if "extruder_temp" in fil:
                data["settings_extruder_temp"] = fil["extruder_temp"]
            if "bed_temp" in fil:
                data["settings_bed_temp"] = fil["bed_temp"]
            filament, created = client.create_filament(data), True

        spools = client.list_spools(filament["id"])
        if spools:
            spool, spool_created = spools[0], False
        else:
            extra = {"location": location} if location else {}
            spool = client.create_spool(filament["id"], fil["spool_net_weight"], **extra)
            spool_created = True
        report.append({"filament": filament["name"], "filament_id": filament["id"],
                       "filament_created": created, "spool_id": spool["id"],
                       "spool_created": spool_created})
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Register makerspace filaments in Spoolman")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--file", default=DEFAULT_STOCK_FILE)
    args = ap.parse_args(argv)

    client = SpoolmanClient(args.url)
    try:
        report = register_stock(client, load_stock_file(args.file))
    except (SpoolmanError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for r in report:
        print(f"{'new' if r['filament_created'] else 'had'} filament {r['filament_id']:>3} "
              f"{r['filament']:<35} spool {r['spool_id']} ({'new' if r['spool_created'] else 'had'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())