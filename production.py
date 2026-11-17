"""Production of one or more customer orders.

One order goes through these steps (see the activity diagram in the report):

1. plan:    copy the order into the parameters, choose arm length and weight
            for the target period (configurator.py) and estimate the mass of
            every part from the selected filaments (physics.py)
2. check:   is there enough filament on each selected spool in Spoolman?
3. export:  write the 3MF files to output/order-<n>/
4. use:     register the used filament in Spoolman (PUT /spool/{id}/use)

Orders that cannot be made are "rejected" (period out of reach, invalid
geometry) or "postponed" (not enough filament). The result is saved next to
the order as orders/order-<n>.result.json.

Run `python production.py` to (re)process all orders that are new or postponed.
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from configurator import DEFAULT_PERIOD_TOLERANCE, configure
from order import Order
from physics import PART_TO_SPOOL_FIELD, PrintSettings, kit_masses
from spoolman_client import SpoolmanClient, SpoolmanError
from validation import load_parameters, validate_parameters

PROJECT_DIR = Path(__file__).resolve().parent
ORDERS_DIR = PROJECT_DIR / "orders"
OUTPUT_DIR = PROJECT_DIR / "output"

# Only one order at a time may check the stock and register filament use,
# otherwise two orders could both "see" the same filament (Flask is threaded).
STOCK_LOCK = threading.Lock()


@dataclass
class ProductionResult:
    order_number: int
    status: str                       # "produced", "postponed" or "rejected"
    reason: str = ""
    target_period_s: float = 0.0
    period_s: float | None = None
    error_s: float | None = None
    error_percent: float | None = None
    achievable_range_s: tuple | None = None
    weight_size: str | None = None
    arm_length_mm: float | None = None
    weight_position_mm: float | None = None
    part_masses_g: dict = field(default_factory=dict)    # part -> mass of one part
    filament_use_g: dict = field(default_factory=dict)   # spool id -> grams
    output_dir: str | None = None


@dataclass
class Plan:
    """Everything that can be computed without touching the stock."""
    parameters: dict
    result: ProductionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parameters_for_order(order: Order):
    parameters = load_parameters(PROJECT_DIR / "parameters.json")

    stand_clearance = (
        parameters["axle_hole_diameter_mm"] - parameters["axle_diameter_mm"]
    )

    parameters["axle_diameter_mm"] = order.axle_diameter_mm
    parameters["axle_hole_diameter_mm"] = order.axle_diameter_mm + stand_clearance

    validate_parameters(parameters)
    return parameters


def densities_for_order(order: Order, spools_by_id: dict) -> dict:
    """Density (g/cm^3) of the filament chosen for each part."""
    return {part: spools_by_id[order.spool_ids[field_name]]["filament"]["density"]
            for part, field_name in PART_TO_SPOOL_FIELD.items()}


def remaining_weight(spool: dict) -> float | None:
    """Remaining filament on a spool in grams (None if Spoolman does not know)."""
    if spool.get("remaining_weight") is not None:
        return spool["remaining_weight"]
    initial = spool.get("initial_weight") or (spool.get("filament") or {}).get("weight")
    if initial is None:
        return None
    return initial - spool.get("used_weight", 0.0)


def find_shortages(required_g: dict, spools_by_id: dict) -> list[str]:
    """Return one message per spool that does not have enough filament."""
    shortages = []
    for spool_id, grams in required_g.items():
        spool = spools_by_id.get(spool_id)
        name = spool["filament"]["name"] if spool else "?"
        left = remaining_weight(spool) if spool else None
        if spool is None:
            shortages.append(f"spool #{spool_id} is no longer in stock")
        elif left is None:
            shortages.append(f"spool #{spool_id} ({name}) has no known remaining weight")
        elif left < grams:
            shortages.append(f"spool #{spool_id} ({name}) has {left:.1f} g left, the order needs {grams:.1f} g")
    return shortages


def export_order(order_number: int, parameters: dict, result: ProductionResult | None = None):
    """Write the 3MF files (and the parameters used) to output/order-<n>/."""
    from cad import export_kit   # imported here so planning works without CadQuery

    OUTPUT_DIR.mkdir(exist_ok=True)
    target = OUTPUT_DIR / f"order-{order_number}"
    if target.exists():
        raise FileExistsError(f"{target} already exists")

    with TemporaryDirectory(dir=OUTPUT_DIR, prefix=f".order-{order_number}-") as temp_dir:
        kit_dir = Path(temp_dir) / "kit"
        export_kit(parameters, kit_dir)
        (kit_dir / "parameters.json").write_text(json.dumps(parameters, indent=2), encoding="utf-8")
        if result is not None:
            (kit_dir / "result.json").write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
        kit_dir.rename(target)
    return target


def save_result(result: ProductionResult, orders_dir: Path | None = None):
    orders_dir = orders_dir or ORDERS_DIR
    orders_dir.mkdir(exist_ok=True)
    path = orders_dir / f"order-{result.order_number}.result.json"
    path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The production steps
# ---------------------------------------------------------------------------
def plan_order(order_number: int, order: Order, densities: dict,
               tolerance: float = DEFAULT_PERIOD_TOLERANCE) -> Plan:
    """Step 1: configure the pendulum and estimate filament use (CPU only)."""
    result = ProductionResult(order_number, "rejected", target_period_s=order.target_period_s)
    try:
        parameters = parameters_for_order(order)
    except ValueError as error:
        result.reason = f"Invalid order: {error}"
        return Plan({}, result)

    settings = PrintSettings.from_parameters(parameters)
    cfg = configure(parameters, order.target_period_s, densities["pendulum"], settings)
    p = cfg.parameters
    result.period_s = round(cfg.period_s, 4)
    result.error_s = round(cfg.error_s, 4)
    result.error_percent = round(cfg.error_percent, 2)
    result.achievable_range_s = (round(cfg.achievable_range_s[0], 3), round(cfg.achievable_range_s[1], 3))
    result.weight_size = cfg.weight_size
    result.arm_length_mm = p["pendulum_arm_length_mm"]
    result.weight_position_mm = p["pendulum_weight_position_mm"]

    if not cfg.within(tolerance):
        low, high = result.achievable_range_s
        result.reason = (f"The requested period {order.target_period_s:.3f} s cannot be reached within the size "
                         f"limits. This kit can swing with {low:.3f}-{high:.3f} s.")
        return Plan(p, result)

    masses = kit_masses(p, densities, settings)
    result.part_masses_g = {name: round(m.mass_g, 2) for name, m in masses.items()}
    use: dict[int, float] = {}
    for name, m in masses.items():
        spool_id = order.spool_ids[PART_TO_SPOOL_FIELD[name]]
        use[spool_id] = use.get(spool_id, 0.0) + m.total_mass_g
    result.filament_use_g = {sid: round(g, 2) for sid, g in use.items()}
    result.status = "planned"
    return Plan(p, result)


def produce(plan: Plan, spoolman: SpoolmanClient) -> ProductionResult:
    """Steps 2-4: check stock, export 3MF and register the filament use."""
    result = plan.result
    if result.status != "planned":
        return result
    with STOCK_LOCK:
        spools_by_id = {s["id"]: s for s in spoolman.get_spools(include_archived=False)}  # fresh numbers
        shortages = find_shortages(result.filament_use_g, spools_by_id)
        if shortages:
            result.status = "postponed"
            result.reason = "Not enough filament: " + "; ".join(shortages)
            return result

        result.status = "produced"
        result.reason = (f"Period {result.period_s:.4f} s, {result.error_s * 1000:+.1f} ms "
                         f"({result.error_percent:+.2f} %) from the requested {result.target_period_s:.3f} s")
        result.output_dir = str(OUTPUT_DIR / f"order-{result.order_number}")
        export_order(result.order_number, plan.parameters, result)
        for spool_id, grams in result.filament_use_g.items():
            spoolman.use_filament(spool_id, grams)
    return result


def process_order(order_number: int, order: Order, spoolman: SpoolmanClient,
                  tolerance: float = DEFAULT_PERIOD_TOLERANCE) -> ProductionResult:
    """Run one order through the whole flow and save the result."""
    spools_by_id = {s["id"]: s for s in spoolman.get_spools(include_archived=False)}
    missing = [f for f, sid in order.spool_ids.items() if sid not in spools_by_id]
    if missing:
        result = ProductionResult(order_number, "postponed", target_period_s=order.target_period_s,
                                  reason=f"Selected spool for {', '.join(missing)} is no longer in stock")
    else:
        plan = plan_order(order_number, order, densities_for_order(order, spools_by_id), tolerance)
        result = produce(plan, spoolman)
    save_result(result)
    return result


# ---------------------------------------------------------------------------
# Command line: process all new and postponed orders
# ---------------------------------------------------------------------------
def load_order(path: Path) -> Order:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Order(target_period_s=data["target_period_s"], axle_diameter_mm=data["axle_diameter_mm"],
                 spool_ids={k: int(v) for k, v in data["spool_ids"].items()})


def pending_orders(orders_dir: Path | None = None) -> list[tuple[int, Order]]:
    """Orders without a result, or with a postponed result, sorted by number (FIFO)."""
    orders_dir = orders_dir or ORDERS_DIR
    pending = []
    for path in orders_dir.glob("order-*.json"):
        if path.name.endswith(".result.json"):
            continue
        number = int(path.stem.split("-")[1])
        result_path = orders_dir / f"order-{number}.result.json"
        if result_path.exists():
            status = json.loads(result_path.read_text(encoding="utf-8"))["status"]
            if status != "postponed":
                continue
        pending.append((number, load_order(path)))
    return sorted(pending, key=lambda item: item[0])


def _plan_job(args):
    return plan_order(*args)


def run_production(spoolman: SpoolmanClient | None = None, workers: int | None = None):
    spoolman = spoolman or SpoolmanClient()
    orders = pending_orders()
    if not orders:
        print("No new or postponed orders.")
        return []
    spools_by_id = {s["id"]: s for s in spoolman.get_spools(include_archived=False)}

    jobs, results = [], []
    for number, order in orders:
        if all(sid in spools_by_id for sid in order.spool_ids.values()):
            jobs.append((number, order, densities_for_order(order, spools_by_id)))
        else:
            results.append(ProductionResult(number, "postponed", target_period_s=order.target_period_s,
                                            reason="A selected spool is no longer in stock"))

    # Planning is CPU heavy and independent per order -> run in parallel processes
    with ProcessPoolExecutor(max_workers=workers) as pool:
        plans = list(pool.map(_plan_job, jobs))

    # Stock check, export and filament use one at a time, in order-number order
    for plan in plans:
        results.append(produce(plan, spoolman))
    for result in sorted(results, key=lambda r: r.order_number):
        save_result(result)
        print(f"Order {result.order_number}: {result.status.upper()} - {result.reason}")
    return results


if __name__ == "__main__":
    try:
        run_production()
    except SpoolmanError as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
