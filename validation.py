import math
import json

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

def validate_order(form_data):

    period_s = validate_float(form_data, "target_period_s", "Swing period")
    axle_diameter_mm = validate_float(form_data,"axle_diameter_mm", "Axle diameter")

    return {"target_period_s": period_s, "axle_diameter_mm": axle_diameter_mm}


def validate_parameters(cad_parameters):
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

    axle_height_above_base = cad_parameters["stand_length_mm"] - slot_depth - hole_from_end
    arm_length = cad_parameters["pendulum_arm_length_mm"]
    hub_radius = cad_parameters["pendulum_cylinder_diameter_mm"] / 2

    weight_position = cad_parameters["pendulum_weight_position_mm"]
    weight_length = cad_parameters["pendulum_weight_length_mm"]
    weight_width = cad_parameters["pendulum_weight_width_mm"]

    hub_hole_diameter = axle_diameter + cad_parameters["pendulum_cylinder_clearance_mm"]

    if hub_hole_diameter >= cylinder_diameter:
        raise ValueError("Hub hole must be smaller than the hub outer diameter")

    if arm_thickness >= stand_gap:
        raise ValueError("Arm thickness must be smaller than the stand thickness")

    if cylinder_length >= stand_gap:
        raise ValueError("Pendulum hub length must be smaller than the gap between the stands")

    if arm_width > cylinder_diameter:

        raise ValueError("Arm width must be smaller than the cylinder diameter")

    # Validation of distance between the pendulum arm with weight to the base with clearance:
    arm_reach = math.hypot(arm_length, arm_width / 2)
    weight_reach = math.hypot(weight_position + weight_length / 2, weight_width / 2,)
    pendulum_reach = max(arm_reach, weight_reach, hub_radius)
    minimum_clearance = cad_parameters["minimum_pendulum_clearance_mm"]
    clearance = axle_height_above_base - pendulum_reach

    if clearance < minimum_clearance:
        raise ValueError(f"Pendulum clearance to the base must be at least {minimum_clearance:.1f} mm. Got {clearance:.1f} mm.")

    # Weight position validation:
    # Weight edges, measured from the axle along the arm.
    weight_start = weight_position - weight_length / 2
    weight_end = weight_position + weight_length / 2
    hub_radius = cad_parameters["pendulum_cylinder_diameter_mm"] / 2
    weight_thickness = cad_parameters["pendulum_weight_thickness_mm"]

    if weight_thickness >= stand_gap:
        raise ValueError("Weight thickness must be smaller than the stand gap")

    if weight_start < hub_radius:
        raise ValueError("The weight must lie outside the hub")

    if weight_end > arm_length:
        raise ValueError("The weight must not extend beyond the end of the arm")