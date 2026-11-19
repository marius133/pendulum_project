# AI-assisted (Claude, Anthropic): part_bounding_boxes() and the build-volume check in validate_parameters(). The rest is our own. Reviewed and tested by the group.
import math
import json
from order import Order

# Reading json file
def load_parameters(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        cad_parameters = json.load(file)
    return cad_parameters

def validate_float(form_data, field_name, label):
    raw_value = form_data.get(field_name,"")
    try:
        value = float(raw_value)
    except ValueError:
        raise ValueError(f"{label} must be a number")

    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be greater than zero and finite")

    return value

def validate_order(form_data, available_spool_ids):

    period_s = validate_float(form_data, "target_period_s", "Swing period")
    axle_diameter_mm = validate_float(form_data,"axle_diameter_mm", "Axle diameter")
    spool_ids = {}

    for part in ("base", "side", "pendulum", "axle"):
        field_name = f"{part}_spool_id"
        raw_value = form_data.get(field_name, "")

        try:
            spool_id = int(raw_value)
        except ValueError:
            raise ValueError(f"Select a valid spool for the {part}.")

        if spool_id not in available_spool_ids:
            raise ValueError(f"The selected spool for the {part} is no longer available.")

        spool_ids[part] = spool_id

    return Order(target_period_s=period_s,axle_diameter_mm=axle_diameter_mm,spool_ids=spool_ids,)


def validate_parameters(cad_parameters, *, check_design=True):
    required_parameters = (
      "stand_length_mm",
      "stand_width_mm",
      "stand_thickness_mm",
      "stand_gap_mm",
      "axle_hole_diameter_mm",
      "hole_center_from_end_mm",
      "base_length_mm",
      "base_width_mm",
      "base_thickness_mm",
      "slot_depth_mm",
      "slot_clearance_mm",
      "axle_diameter_mm",
      "pendulum_cylinder_diameter_mm",
      "pendulum_cylinder_clearance_mm",
      "pendulum_cylinder_length_mm",
      "pendulum_arm_length_mm",
      "pendulum_arm_width_mm",
      "pendulum_arm_thickness_mm",
      "pendulum_weight_width_mm",
      "pendulum_weight_length_mm",
      "pendulum_weight_thickness_mm",
      "pendulum_weight_position_mm",
      "minimum_pendulum_clearance_mm"
    )

    # Exported geometry from older orders may predate this setting.
    if "min_axle_diameter_mm" in cad_parameters:
        required_parameters += ("min_axle_diameter_mm",)

    # Check required parameters, types and numeric values.
    for name in required_parameters:
        if name not in cad_parameters:
            raise ValueError(f"Missing parameter: {name}")

        value = cad_parameters[name]

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number. Got {value!r}")

        if not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")

        if name == "slot_clearance_mm":
            if value < 0:
                raise ValueError(f"{name} must be zero or greater")
        elif value <= 0:
            raise ValueError(f"{name} must be greater than zero")

    # Get dimensions from json file
    axle_diameter = cad_parameters["axle_diameter_mm"]
    hole_diameter = cad_parameters["axle_hole_diameter_mm"]
    stand_width = cad_parameters["stand_width_mm"]
    stand_thickness = cad_parameters["stand_thickness_mm"]
    stand_gap = cad_parameters["stand_gap_mm"]
    hole_from_end = cad_parameters["hole_center_from_end_mm"]

    base_width = cad_parameters["base_width_mm"]
    base_length = cad_parameters["base_length_mm"]
    base_thickness = cad_parameters["base_thickness_mm"]

    slot_depth = cad_parameters["slot_depth_mm"]
    slot_clearance = cad_parameters["slot_clearance_mm"]
    hole_radius = hole_diameter/2
    stand_length = cad_parameters["stand_length_mm"]
    axle_height_above_base = stand_length - slot_depth - hole_from_end

    if (axle_height_above_base - hole_radius) <= 0:
        raise ValueError("Axle hole must be above the base")

    if stand_length <= 0:
        raise ValueError("Stand length after subtracting slot depth must be positive")

    # Axle and hole dimensions
    min_axle_diameter = cad_parameters.get("min_axle_diameter_mm", 0)
    if axle_diameter < min_axle_diameter:
        raise ValueError(f"Axle diameter must be at least {min_axle_diameter:g} mm")

    if axle_diameter >= hole_diameter:
        raise ValueError("Axle diameter must be smaller than the axle hole diameter")

    if hole_diameter >= stand_width:
        raise ValueError("Axle hole diameter must be smaller than the stand width")

    # Leave material beneath the slots
    if not 0 < slot_depth < base_thickness:
        raise ValueError("Slot depth must be greater than zero and smaller than base thickness")

    # Keep the hole inside the stand, with material around it
    hole_radius = hole_diameter / 2

    if hole_from_end <= hole_radius or hole_from_end + hole_radius >= stand_length:
        raise ValueError("Axle hole must lie entirely inside the stand, with material around it")

    # Keep the entire axle hole above the base after insertion
    if stand_length - hole_from_end - hole_radius <= slot_depth:
        raise ValueError("Axle hole must be entirely above the base when the stand is inserted")

    # Check slot dimensions and placement
    slot_length = stand_width + slot_clearance
    slot_width = stand_thickness + slot_clearance
    offset = (stand_gap + stand_thickness) / 2

    if slot_length >= base_width:
        raise ValueError("Slots must fit inside the base width, with material on both sides")

    if offset + slot_width / 2 >= base_length / 2:
        raise ValueError("Slots must fit inside the base length,with material at both ends")

    if stand_gap <= slot_clearance:
        raise ValueError("There must be material between the two slots")

    # Validation of pendulum arm:
    arm_thickness = cad_parameters["pendulum_arm_thickness_mm"]
    cylinder_diameter = cad_parameters["pendulum_cylinder_diameter_mm"]
    cylinder_length = cad_parameters["pendulum_cylinder_length_mm"]
    arm_width = cad_parameters["pendulum_arm_width_mm"]

    hub_hole_diameter = axle_diameter + cad_parameters["pendulum_cylinder_clearance_mm"]

    if hub_hole_diameter >= cylinder_diameter:
        raise ValueError("Hub hole must be smaller than the hub outer diameter")

    if arm_thickness >= stand_gap:
        raise ValueError("Arm thickness must be smaller than the gap between the stands")

    if cylinder_length >= stand_gap:
        raise ValueError("Pendulum hub length must be smaller than the gap between the stands")

    if arm_width > cylinder_diameter:
        raise ValueError("Arm width must be smaller than the cylinder diameter")

    if check_design:
        validate_pendulum_design(cad_parameters)

    build_volume = sorted(printer_build_volume_mm(cad_parameters))
    for name, size in part_bounding_boxes(cad_parameters).items():
        if name == "pendulum" and not check_design:
            continue
        if any(s > b for s, b in zip(sorted(size), build_volume)):
            raise ValueError(f"The {name} ({size[0]:.0f} x {size[1]:.0f} x {size[2]:.0f} mm) "
                             f"does not fit in the printer build volume")


def minimum_stand_length_mm(p):
    arm_reach = math.hypot(p["pendulum_arm_length_mm"], p["pendulum_arm_width_mm"] / 2)
    weight_end = p["pendulum_weight_position_mm"] + p["pendulum_weight_length_mm"] / 2
    weight_reach = math.hypot(weight_end, p["pendulum_weight_width_mm"] / 2)
    hub_radius = p["pendulum_cylinder_diameter_mm"] / 2
    return (max(arm_reach, weight_reach, hub_radius)
            + p["slot_depth_mm"] + p["hole_center_from_end_mm"]
            + p["minimum_pendulum_clearance_mm"])


def validate_pendulum_design(p):
    minimum_length = minimum_stand_length_mm(p)
    minimum_clearance = p["minimum_pendulum_clearance_mm"]
    clearance = minimum_clearance + p["stand_length_mm"] - minimum_length
    if p["stand_length_mm"] < minimum_length:
        raise ValueError(f"Pendulum clearance to the base must be at least {minimum_clearance:.1f} mm. "
                         f"Got {clearance:.1f} mm.")

    hub_radius = p["pendulum_cylinder_diameter_mm"] / 2
    weight_position = p["pendulum_weight_position_mm"]
    half_weight_length = p["pendulum_weight_length_mm"] / 2

    if p["pendulum_weight_thickness_mm"] >= p["stand_gap_mm"]:
        raise ValueError("Weight thickness must be smaller than the stand gap")
    if weight_position - half_weight_length < hub_radius:
        raise ValueError("The weight must lie outside the hub")
    if weight_position + half_weight_length - p["pendulum_arm_length_mm"] > 1e-9:
        raise ValueError("The weight must not extend beyond the end of the arm")


def printer_build_volume_mm(parameters):
    volume = parameters.get("build_volume_mm", [250, 210, 220])
    if not isinstance(volume, (list, tuple)) or len(volume) != 3:
        raise ValueError("Build volume must have three dimensions")
    if any(isinstance(dimension, bool) or not isinstance(dimension, (float, int))
           or not math.isfinite(dimension) or dimension <= 0 for dimension in volume):
        raise ValueError("Build volume dimensions must be finite positive numbers")
    return volume


def part_bounding_boxes(p):
    """Size (x, y, z) in mm of each printed part, as modelled in cad.py."""
    hub_r = p["pendulum_cylinder_diameter_mm"] / 2
    pendulum_reach = max(p["pendulum_arm_length_mm"],
                         p["pendulum_weight_position_mm"] + p["pendulum_weight_length_mm"] / 2)
    return {
        "base": (p["base_width_mm"], p["base_length_mm"], p["base_thickness_mm"]),
        "stand": (p["stand_width_mm"], p["stand_length_mm"], p["stand_thickness_mm"]),
        "axle": (p["axle_diameter_mm"], p["axle_diameter_mm"],
                 p["stand_gap_mm"] + 2 * p["stand_thickness_mm"]),
        "pendulum": (max(2 * hub_r, p["pendulum_arm_width_mm"], p["pendulum_weight_width_mm"]),
                     pendulum_reach + hub_r,
                     max(p["pendulum_cylinder_length_mm"], p["pendulum_arm_thickness_mm"],
                         p["pendulum_weight_thickness_mm"])),
    }
