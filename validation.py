import math
import json

#Reading json file
def load_parameters(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        cad_parameters = json.load(file)
    return cad_parameters


def validate_parameters(cad_parameters):
    required_parameters = (
        "axle_diameter_mm",
        "axle_hole_diameter_mm",
        "stand_length_mm",
        "stand_width_mm",
        "stand_thickness_mm",
        "stand_gap_mm",
        "hole_center_from_end_mm",
        "base_width_mm",
        "base_length_mm",
        "base_thickness_mm",
        "slot_depth_mm",
        "slot_clearance_mm",
    )

    #Check required parameters, types and numeric values.
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

    #Get dimensions from json file
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

    #Matches the current make_stand() geometry
    stand_length = cad_parameters["stand_length_mm"] - slot_depth

    if stand_length <= 0:
        raise ValueError("Stand length after subtracting slot depth must be positive")

    #Axle and hole dimensions
    if axle_diameter >= hole_diameter:
        raise ValueError("Axle diameter must be smaller than the axle hole diameter")

    if hole_diameter >= stand_width:
        raise ValueError("Axle hole diameter must be smaller than the stand width")

    #Leave material beneath the slots
    if not 0 < slot_depth < base_thickness:
        raise ValueError("Slot depth must be greater than zero and smaller than base thickness")

    #Keep the hole inside the stand, with material around it
    hole_radius = hole_diameter / 2

    if (hole_from_end <= hole_radius or hole_from_end + hole_radius >= stand_length):
        raise ValueError("Axle hole must lie entirely inside the stand, with material around it")

    #Keep the entire axle hole above the base after insertion
    if stand_length - hole_from_end - hole_radius <= slot_depth:
        raise ValueError("Axle hole must be entirely above the base when the stand is inserted")

    #Check slot dimensions and placement
    slot_length = stand_width + slot_clearance
    slot_width = stand_thickness + slot_clearance
    offset = (stand_gap + stand_thickness) / 2

    if slot_length >= base_width:
        raise ValueError("Slots must fit inside the base width, with material on both sides")

    if offset + slot_width / 2 >= base_length / 2:
        raise ValueError("Slots must fit inside the base length,with material at both ends")

    if stand_gap <= slot_clearance:
        raise ValueError("There must be material between the two slots")