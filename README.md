<!-- AI-assisted (Claude, Anthropic): written with Claude, then edited by us. -->
## Install
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
docker compose up -d               # 1. start Spoolman on http://localhost:7912
python register_stock.py           # 2. operator: load the makerspace filaments (makerspace_filament.json)
flask --app app run                # 3. customer: order form on http://127.0.0.1:5000
python production.py               # 4. operator: (re)process new and postponed orders
python compare_periods.py          # 5. calculated vs. MuJoCo-simulated period for produced orders
python mujoco_sim.py --params output/order-1/parameters.json   # 3D viewer for one order
python -m unittest discover -s tests -t .                       # unit tests (no Docker needed)
```

Orders are stored in `orders/order-<n>.json`, results in `orders/order-<n>.result.json`
and the 3MF files in `output/order-<n>/` (one file per part type; print the stand twice).
The result next to the order records the production status. A `needs_review` result requires
checking the filament use in Spoolman before manually retrying the order.
The configurator keeps the default stand length as a minimum and raises it when the selected
arm and weight need more clearance, within the printer build volume.

## Files
| File | Purpose |
|---|---|
| `parameters.json` | Shared description of the kit (CAD, physics, simulation, print settings) |
| `validation.py` | Validation of parameters (incl. clearance and build volume) and orders |
| `cad.py` | Parametric CAD (CadQuery) and 3MF export |
| `physics.py` | Mass per part (infill and walls), centre of mass, inertia, period |
| `configurator.py` | Chooses arm length and weight size for the wanted period |
| `production.py` | Order flow: plan, stock check, export, register filament use |
| `spoolman_client.py` | Spoolman REST API client with error handling |
| `app.py`, `templates/order.html` | Flask web GUI |
| `mujoco_sim.py`, `compare_periods.py` | MuJoCo simulation and period comparison |
| `register_stock.py`, `makerspace_filament.json` | Loading the stock into Spoolman |