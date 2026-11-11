from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import jsonschema


PARTS = ("base", "stand", "arm", "weight", "axle")
PART_COUNT = {"base": 1, "stand": 2, "arm": 1, "weight": 1, "axle": 1}
SWINGING_PARTS = ("arm", "weight")  

DEFAULT_PARAMS_FILE = Path(__file__).resolve().parent.parent / "data" / "params_default.json"


def _section(positive=(), non_negative=(), extra=None):
    props = {n: {"type": "number", "exclusiveMinimum": 0} for n in positive}
    props.update({n: {"type": "number", "minimum": 0} for n in non_negative})
    props.update(extra or {})
    return {"type": "object", "properties": props,
            "required": list(positive) + list(non_negative)}


_MATERIAL = {
    "type": "object",
    "properties": {
        "filament_id": {"type": ["integer", "null"]},
        "name": {"type": "string"},
        "density": {"type": "number", "exclusiveMinimum": 0},
    },
    "required": ["density"],
}

_FRACTION = {"type": "number", "minimum": 0, "maximum": 1}

SCHEMA = {
    "type": "object",
    "properties": {
        "arm": _section(["length", "width", "thickness", "hub_diameter"]),
        "weight": _section(["diameter", "height"]),
        "axle": _section(["diameter"], ["overhang"]),
        "stand": _section(["width", "height", "thickness", "axle_offset", "tab_length"]),
        "base": _section(["width", "thickness"], ["margin"]),
        "clearance": _section(["min_wall"], ["fit", "press_fit", "rotation", "side_gap", "ground"]),
        "printer": _section(["bed_x", "bed_y", "max_z"], ["part_gap"]),
        "print": _section(
            ["layer_height", "line_width"],
            extra={
                "walls": {"type": "integer", "minimum": 1},
                "top_bottom_layers": {"type": "integer", "minimum": 1},
                "infill": _FRACTION,
                "infill_per_part": {
                    "type": "object",
                    "propertyNames": {"enum": list(PARTS)},
                    "additionalProperties": _FRACTION,
                },
            },
        ),
        "materials": {
            "type": "object",
            "properties": {part: _MATERIAL for part in PARTS},
            "required": list(PARTS),
        },
        "simulation": {
            "type": "object",
            "properties": {"amplitude_deg": {"type": "number", "exclusiveMinimum": 0, "maximum": 90}},
        },
    },
    "required": ["arm", "weight", "axle", "stand", "base", "clearance", "printer", "print", "materials"],
}
SCHEMA["properties"]["print"]["required"] += ["walls", "top_bottom_layers", "infill"]


class ParameterError(ValueError):

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("Invalid kit parameters:\n  - " + "\n  - ".join(self.errors))


def deep_merge(base: dict, updates: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class KitParameters:

    def __init__(self, data: dict, validate: bool = True):
        self.data = copy.deepcopy(data)
        if validate:
            self.validate()

    @classmethod
    def load(cls, path=DEFAULT_PARAMS_FILE, validate: bool = True) -> "KitParameters":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f), validate=validate)

    def save(self, path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def to_dict(self) -> dict:
        return copy.deepcopy(self.data)

    def with_updates(self, updates: dict, validate: bool = True) -> "KitParameters":
        return KitParameters(deep_merge(self.data, updates), validate=validate)

    def __getitem__(self, key):
        return self.data[key]

    @property
    def inner_gap(self) -> float:
        return self["weight"]["diameter"] + 2 * self["clearance"]["side_gap"]

    @property
    def stand_x_positions(self) -> tuple[float, float]:
        x = self.inner_gap / 2 + self["stand"]["thickness"] / 2
        return (-x, x)

    @property
    def base_length(self) -> float:
        return self.inner_gap + 2 * self["stand"]["thickness"] + 2 * self["base"]["margin"]

    @property
    def pivot_height(self) -> float:
        return self["stand"]["height"] - self["stand"]["axle_offset"]

    @property
    def axle_length(self) -> float:
        return self.inner_gap + 2 * self["stand"]["thickness"] + 2 * self["axle"]["overhang"]

    @property
    def weight_centre_distance(self) -> float:
        return self["arm"]["length"] - self["weight"]["height"] / 2

    @property
    def ground_clearance(self) -> float:
        return self.pivot_height - self["arm"]["length"]

    @property
    def total_height(self) -> float:
        return self["base"]["thickness"] + self["stand"]["height"]

    @property
    def axle_hole_stand(self) -> float:
        return self["axle"]["diameter"] + self["clearance"]["press_fit"]   

    @property
    def axle_hole_arm(self) -> float:
        return self["axle"]["diameter"] + self["clearance"]["rotation"]    

    @property
    def weight_hole(self) -> tuple[float, float]:
        fit = self["clearance"]["fit"]
        return (self["arm"]["width"] + fit, self["arm"]["thickness"] + fit)

    def infill(self, part: str) -> float:
        pr = self["print"]
        return pr.get("infill_per_part", {}).get(part, pr["infill"])

    def density(self, part: str) -> float:
        return self["materials"][part]["density"]

    def print_bounding_boxes(self) -> dict[str, tuple[float, float, float]]:
        a, w, s, b, ax = self["arm"], self["weight"], self["stand"], self["base"], self["axle"]
        return {
            "base": (self.base_length, b["width"], b["thickness"]),
            "stand": (s["width"], s["height"] + b["thickness"], s["thickness"]),  
            "arm": (max(a["width"], a["hub_diameter"]), a["length"] + a["hub_diameter"] / 2,
                    a["thickness"]),
            "weight": (w["diameter"], w["diameter"], w["height"]),                 
            "axle": (ax["diameter"], ax["diameter"], self.axle_length),            
        }

    def validate(self) -> None:
        errors = self.check()
        if errors:
            raise ParameterError(errors)

    def check(self) -> list[str]:
        validator = jsonschema.Draft7Validator(SCHEMA)
        schema_errors = [
            f"{'/'.join(str(x) for x in e.absolute_path) or '(root)'}: {e.message}"
            for e in sorted(validator.iter_errors(self.data), key=lambda e: list(e.absolute_path))
        ]
        if schema_errors:
            return schema_errors     
        return self._geometric_errors()

    def _geometric_errors(self) -> list[str]:
        a, w, s, b, c = self["arm"], self["weight"], self["stand"], self["base"], self["clearance"]
        wall = c["min_wall"]
        errors = []

        def rule(ok, message):
            if not ok:
                errors.append(message)

        rule(a["hub_diameter"] >= a["width"],
             f"arm hub diameter ({a['hub_diameter']}) must be at least the arm width ({a['width']})")
        rule(a["hub_diameter"] >= self.axle_hole_arm + 2 * wall,
             f"arm hub ({a['hub_diameter']}) too small for the axle hole "
             f"({self.axle_hole_arm:.2f}) plus {wall} mm walls")

        rule(w["height"] <= a["length"] - a["hub_diameter"] / 2,
             f"weight (height {w['height']}) does not fit on the arm below the hub "
             f"(arm length {a['length']}, hub radius {a['hub_diameter'] / 2})")
        hole_y, hole_x = self.weight_hole
        hole_half_diag = math.hypot(hole_y, hole_x) / 2
        rule(w["diameter"] / 2 >= hole_half_diag + wall,
             f"weight diameter ({w['diameter']}) too small for the arm hole "
             f"({hole_y:.1f} x {hole_x:.1f}) plus {wall} mm walls")

        rule(self.ground_clearance >= c["ground"],
             f"clearance to the base is {self.ground_clearance:.1f} mm, needs at least {c['ground']} mm "
             f"(make the stand taller or the arm shorter)")

        rule(s["axle_offset"] >= self.axle_hole_stand / 2 + wall,
             f"axle hole too close to the top of the stand (axle_offset {s['axle_offset']})")
        rule(s["width"] >= self.axle_hole_stand + 2 * wall,
             f"stand width ({s['width']}) too small for the axle hole")
        rule(s["tab_length"] <= s["width"],
             f"stand tab ({s['tab_length']}) is wider than the stand ({s['width']})")
        rule(s["tab_length"] + c["fit"] <= b["width"],
             f"stand tab ({s['tab_length']}) does not fit in the base width ({b['width']})")
        rule(b["width"] >= s["width"],
             f"base width ({b['width']}) should be at least the stand width ({s['width']}) for stability")

        pr = self["printer"]
        bed = sorted((pr["bed_x"], pr["bed_y"]))
        for part, (x, y, z) in self.print_bounding_boxes().items():
            footprint = sorted((x, y))
            rule(footprint[0] <= bed[0] and footprint[1] <= bed[1] and z <= pr["max_z"],
                 f"{part} ({x:.1f} x {y:.1f} x {z:.1f}) does not fit in the build volume "
                 f"({pr['bed_x']} x {pr['bed_y']} x {pr['max_z']})")
        return errors
