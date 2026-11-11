from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .params import KitParameters


@dataclass(frozen=True)
class PartGeometry:
    name: str
    volume: float                  # mm^3
    side_area: float               # mm^2
    cap_area: float                # mm^2
    com_distance: float | None = None    # mm
    second_moment: float | None = None   


def raster_moments(inside, u_range, v_range, cell=0.05):
    u = np.arange(u_range[0] + cell / 2, u_range[1], cell)
    v = np.arange(v_range[0] + cell / 2, v_range[1], cell)
    uu, vv = np.meshgrid(u, v)
    mask = inside(uu, vv)
    dA = cell * cell
    area = mask.sum() * dA
    if area == 0:
        return 0.0, 0.0, 0.0
    mean_v = vv[mask].sum() * dA / area
    polar = ((uu[mask] ** 2 + vv[mask] ** 2).sum()) * dA
    return float(area), float(mean_v), float(polar)


def arm_inside(p: KitParameters):
    a = p["arm"]
    half_w, length = a["width"] / 2, a["length"]
    r_hub, r_hole = a["hub_diameter"] / 2, p.axle_hole_arm / 2

    def inside(u, v):
        r2 = u ** 2 + v ** 2
        bar = (np.abs(u) <= half_w) & (v <= 0) & (v >= -length)
        hub = r2 <= r_hub ** 2
        return (bar | hub) & (r2 >= r_hole ** 2)

    return inside


def arm_area_exact(p: KitParameters) -> float:
    a = p["arm"]
    w, length, R = a["width"], a["length"], a["hub_diameter"] / 2
    r_hole = p.axle_hole_arm / 2
    overlap = (w / 2) * math.sqrt(R ** 2 - (w / 2) ** 2) + R ** 2 * math.asin(w / (2 * R))
    return w * length + math.pi * R ** 2 - overlap - math.pi * r_hole ** 2


def arm_perimeter_exact(p: KitParameters) -> float:
    a = p["arm"]
    w, length, R = a["width"], a["length"], a["hub_diameter"] / 2
    join = math.sqrt(R ** 2 - (w / 2) ** 2)          
    hub_arc = R * (2 * math.pi - 2 * math.asin(w / (2 * R)))
    return 2 * (length - join) + w + hub_arc + math.pi * p.axle_hole_arm


@lru_cache(maxsize=256)
def _hub_zone_moments(width: float, r_hub: float, r_hole: float, cell: float):
    half_w = width / 2

    def inside(u, v):
        r2 = u ** 2 + v ** 2
        bar = (np.abs(u) <= half_w) & (v <= 0)
        return (bar | (r2 <= r_hub ** 2)) & (r2 >= r_hole ** 2)

    half = max(half_w, r_hub)
    return raster_moments(inside, (-half, half), (-r_hub, r_hub), cell)


def arm_profile_moments(p: KitParameters, cell: float = 0.05):
    a = p["arm"]
    w, length, R = a["width"], a["length"], a["hub_diameter"] / 2
    area_h, mean_h, polar_h = _hub_zone_moments(w, R, p.axle_hole_arm / 2, cell)
    bar_len = length - R                              
    area_b = w * bar_len
    mean_b = -(length + R) / 2
    polar_b = bar_len * w ** 3 / 12 + w * (length ** 3 - R ** 3) / 3
    area = area_h + area_b
    return area, (area_h * mean_h + area_b * mean_b) / area, polar_h + polar_b


def arm_geometry(p: KitParameters, cell: float = 0.05) -> PartGeometry:
    a = p["arm"]
    t = a["thickness"]
    area, mean_v, polar = arm_profile_moments(p, cell)
    return PartGeometry(
        name="arm",
        volume=area * t,
        side_area=arm_perimeter_exact(p) * t,
        cap_area=2 * area,
        com_distance=-mean_v,
        second_moment=polar * t,       
    )


def weight_geometry(p: KitParameters) -> PartGeometry:
    w = p["weight"]
    R, h = w["diameter"] / 2, w["height"]
    hole_y, hole_x = p.weight_hole
    v_cyl = math.pi * R ** 2 * h
    v_hole = hole_y * hole_x * h
    volume = v_cyl - v_hole
  
    own = v_cyl * (R ** 2 / 4 + h ** 2 / 12) - v_hole * (hole_y ** 2 + h ** 2) / 12
    d = p.weight_centre_distance
    return PartGeometry(
        name="weight",
        volume=volume,
        side_area=(2 * math.pi * R + 2 * (hole_y + hole_x)) * h,
        cap_area=2 * (math.pi * R ** 2 - hole_y * hole_x),
        com_distance=d,
        second_moment=own + volume * d ** 2,     
    )


def base_geometry(p: KitParameters) -> PartGeometry:
    b, s, c = p["base"], p["stand"], p["clearance"]
    slot_x, slot_y = s["thickness"] + c["fit"], s["tab_length"] + c["fit"]
    area = p.base_length * b["width"] - 2 * slot_x * slot_y
    perimeter = 2 * (p.base_length + b["width"]) + 2 * 2 * (slot_x + slot_y)
    return PartGeometry("base", area * b["thickness"], perimeter * b["thickness"], 2 * area)


def stand_geometry(p: KitParameters) -> PartGeometry:
    s, tab_h = p["stand"], p["base"]["thickness"]
    r = p.axle_hole_stand / 2
    area = s["width"] * s["height"] + s["tab_length"] * tab_h - math.pi * r ** 2
    perimeter = 2 * (s["width"] + s["height"]) + 2 * tab_h + 2 * math.pi * r
    return PartGeometry("stand", area * s["thickness"], perimeter * s["thickness"], 2 * area)


def axle_geometry(p: KitParameters) -> PartGeometry:
    r, length = p["axle"]["diameter"] / 2, p.axle_length
    return PartGeometry("axle", math.pi * r ** 2 * length, 2 * math.pi * r * length,
                        2 * math.pi * r ** 2)


def kit_geometry(p: KitParameters) -> dict[str, PartGeometry]:
    return {
        "base": base_geometry(p),
        "stand": stand_geometry(p),
        "arm": arm_geometry(p),
        "weight": weight_geometry(p),
        "axle": axle_geometry(p),
    }