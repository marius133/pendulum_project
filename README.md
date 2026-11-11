# MAS417 2026 – Software-defined pendulum kit

Generates a 3D-printable pendulum kit (base, two stand sides, arm, weight, axle) for a
customer order: the arm length and weight size are chosen so the pendulum swings with
the requested period, and the material comes from a local Spoolman stock.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d                                   # Spoolman on http://localhost:7912
python -m pendulum_kit.stock                           # register makerspace filaments (once)
```

Edit `data/filaments.json` first: the entries there are examples. Use the filaments you
find in the UiA makerspace and the densities from the manufacturers' data sheets.

## Run

```bash
python -m pendulum_kit --period 0.7 --out output/order_001     # design + 3MF files
python -m pytest                                               # tests
```

## Structure

| File | What it does |
|---|---|
| `data/params_default.json` | the shared description: all dimensions, clearances, print settings, materials |
| `pendulum_kit/params.py` | `KitParameters`: load/save, JSON-Schema + geometric validation, derived dimensions |
| `pendulum_kit/geometry.py` | volume, surface areas, centre of mass and inertia of each part (NumPy, no CAD needed) |
| `pendulum_kit/physics.py` | mass from density + infill/walls, physical-pendulum period |
| `pendulum_kit/design.py` | finds arm length and weight size for a target period (scan + bisection) |
| `pendulum_kit/cad.py` | CadQuery parts, print-bed layout, 3MF export |
| `pendulum_kit/spoolman.py` | REST client for Spoolman with error handling and material reservation |
| `pendulum_kit/stock.py` | registers the makerspace filaments in Spoolman (POST) |
| `tests/` | pytest tests; `fake_spoolman.py` imitates the Spoolman API for testing |

## Use of AI

The first version of every file was generated with Claude (Anthropic) and is marked
with a comment at the top. It was checked with the tests in `tests/` (e.g. numerical
integration against exact formulas, the simple-pendulum limit, the large-amplitude
period against the exact elliptic-integral value, and the REST client against a fake
Spoolman server).
