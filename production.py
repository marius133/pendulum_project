from pathlib import Path
from tempfile import TemporaryDirectory

from cad import export_kit
from order import Order
from validation import load_parameters, validate_parameters

PROJECT_DIR = Path(__file__).resolve().parent


def parameters_for_order(order: Order):
    parameters = load_parameters(PROJECT_DIR / "parameters.json")

    stand_clearance = (
        parameters["axle_hole_diameter_mm"] - parameters["axle_diameter_mm"]
    )

    parameters["axle_diameter_mm"] = order.axle_diameter_mm
    parameters["axle_hole_diameter_mm"] = order.axle_diameter_mm + stand_clearance

    validate_parameters(parameters)
    return parameters

def export_order(order_number: int, parameters):
    output_root = PROJECT_DIR / "output"
    output_root.mkdir(exist_ok=True)

    with TemporaryDirectory(dir=output_root, prefix=f".order-{order_number}-") as temp_dir:
        kit_dir = Path(temp_dir) / "kit"
        export_kit(parameters, kit_dir)
        kit_dir.rename(output_root / f"order-{order_number}")