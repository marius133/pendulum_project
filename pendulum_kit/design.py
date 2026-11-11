from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .params import KitParameters, ParameterError
from .physics import PartMass, PendulumProperties, kit_masses, pendulum_properties, total_material_g


class DesignError(ValueError):
    """The order cannot be produced. The message explains why."""
@dataclass
class DesignRequest:
    target_period_s: float
    axle_diameter_mm: float | None = None
    weight_diameter_mm: float | None = None      
    max_height_mm: float | None = None
    max_width_mm: float | None = None            
    max_depth_mm: float | None = None           
    max_material_g: float | None = None
    materials: dict = field(default_factory=dict)   

    @classmethod
    def from_dict(cls, d: dict) -> "DesignRequest":
        known = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class DesignResult:
    params: KitParameters
    target_period_s: float
    period_s: float
    pendulum: PendulumProperties
    masses: dict[str, PartMass]
    total_material_g: float

    @property
    def error_s(self) -> float:
        return self.period_s - self.target_period_s

    @property
    def error_percent(self) -> float:
        return 100 * self.error_s / self.target_period_s

    def summary(self) -> str:
        p = self.params
        return (f"arm {p['arm']['length']:.1f} mm, weight {p['weight']['diameter']:.0f} mm, "
                f"stand {p['stand']['height']:.1f} mm | period {self.period_s:.4f} s "
                f"(target {self.target_period_s:.4f} s, error {self.error_s * 1000:+.2f} ms "
                f"= {self.error_percent:+.3f} %) | material {self.total_material_g:.1f} g")


def _kit_for(base: KitParameters, arm_length: float, weight_diameter: float,
             validate: bool = False) -> KitParameters:
    c, s = base["clearance"], base["stand"]
    stand_height = math.ceil((arm_length + c["ground"] + s["axle_offset"]) * 2) / 2  
    return base.with_updates({"arm": {"length": arm_length},
                              "weight": {"diameter": weight_diameter},
                              "stand": {"height": stand_height}}, validate=validate)


def _period(base, arm_length, weight_diameter) -> float:
    return pendulum_properties(_kit_for(base, arm_length, weight_diameter)).period_s


def _arm_length_limits(base: KitParameters, req: DesignRequest) -> tuple[float, float]:
    a, c, s, b, pr = base["arm"], base["clearance"], base["stand"], base["base"], base["printer"]
    shortest = a["hub_diameter"] / 2 + base["weight"]["height"]        
    longest_bed = max(pr["bed_x"], pr["bed_y"])
    longest = min(
        longest_bed - b["thickness"] - c["ground"] - s["axle_offset"] - 0.5,   
        longest_bed - a["hub_diameter"] / 2,                                   
    )
    if req.max_height_mm is not None:
        longest = min(longest, req.max_height_mm - b["thickness"] - c["ground"] - s["axle_offset"] - 0.5)
    return shortest, longest


def _limit_errors(kit: KitParameters, req: DesignRequest, material: float) -> list[str]:
    errors = []
    if req.max_height_mm is not None and kit.total_height > req.max_height_mm:
        errors.append(f"height {kit.total_height:.1f} mm > max {req.max_height_mm} mm")
    if req.max_width_mm is not None and kit.base_length > req.max_width_mm:
        errors.append(f"width {kit.base_length:.1f} mm > max {req.max_width_mm} mm")
    if req.max_depth_mm is not None and kit["base"]["width"] > req.max_depth_mm:
        errors.append(f"depth {kit['base']['width']} mm > max {req.max_depth_mm} mm")
    if req.max_material_g is not None and material > req.max_material_g:
        errors.append(f"needs {material:.1f} g material > max {req.max_material_g} g")
    return errors


def bisect(f, lo: float, hi: float, target: float, tol: float = 1e-6, max_iter: int = 100) -> float:
    f_lo = f(lo) - target
    if f_lo * (f(hi) - target) > 0:
        raise ValueError("bisect: the target is not bracketed by [lo, hi]")
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = f(mid) - target
        if f_mid == 0:
            return mid
        if (f_mid < 0) == (f_lo < 0):      
            lo, f_lo = mid, f_mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2


def find_bracket(f, lo: float, hi: float, target: float, samples: int = 25):
    xs = np.linspace(lo, hi, samples)
    ys = np.array([f(x) for x in xs])
    diff = ys - target
    for i in range(samples - 2, -1, -1):
        if diff[i] == 0 or diff[i] * diff[i + 1] < 0 or diff[i + 1] == 0:
            return (xs[i], xs[i + 1]), ys.min(), ys.max()
    return None, ys.min(), ys.max()


def design_for_period(base: KitParameters, req: DesignRequest,
                      weight_diameters=None) -> DesignResult:
    if req.target_period_s <= 0:
        raise DesignError("the period must be positive")

    updates = {}
    if req.axle_diameter_mm is not None:
        updates["axle"] = {"diameter": req.axle_diameter_mm}
    if req.materials:
        updates["materials"] = req.materials
    base = base.with_updates(updates, validate=False)

    if req.weight_diameter_mm is not None:
        diameters = [req.weight_diameter_mm]
    else:
        diameters = weight_diameters or range(16, 82, 2)

    shortest, longest = _arm_length_limits(base, req)
    if longest <= shortest:
        raise DesignError(f"the size limits leave no room for an arm "
                          f"(shortest {shortest:.1f} mm, longest {longest:.1f} mm)")

    candidates, problems = [], []
    achievable = [math.inf, 0.0]
    for diameter in diameters:
        period_of = lambda L, D=diameter: _period(base, L, D)      
        try:
            bracket, t_min, t_max = find_bracket(period_of, shortest, longest, req.target_period_s)
        except (ValueError, ZeroDivisionError) as exc:
            problems.append(f"weight {diameter} mm: geometry impossible ({exc})")
            continue
        achievable[0] = min(achievable[0], t_min)
        achievable[1] = max(achievable[1], t_max)
        if bracket is None:
            continue

        length = bisect(period_of, *bracket, req.target_period_s)
        length = round(length, 1)
        kit = _kit_for(base, length, diameter)
        errors = kit.check()
        masses = kit_masses(kit)
        material = total_material_g(masses)
        errors += _limit_errors(kit, req, material)
        if errors:
            problems.append(f"weight {diameter} mm: " + "; ".join(errors))
            continue
        pend = pendulum_properties(kit, masses)
        candidates.append(DesignResult(kit, req.target_period_s, pend.period_s, pend, masses, material))

    if candidates:
        return min(candidates, key=lambda r: (round(abs(r.error_s), 4), r.total_material_g))

    if achievable[1] and req.target_period_s > achievable[1]:
        reason = (f"period {req.target_period_s} s is too long: the longest possible within the "
                  f"limits is {achievable[1]:.3f} s")
    elif achievable[0] < math.inf and req.target_period_s < achievable[0]:
        reason = (f"period {req.target_period_s} s is too short: the shortest possible is "
                  f"{achievable[0]:.3f} s")
    else:
        reason = "no weight size gives a valid kit"
    if problems:
        reason += " (" + " | ".join(problems[:3]) + (" ..." if len(problems) > 3 else "") + ")"
    raise DesignError(reason)


__all__ = ["DesignRequest", "DesignResult", "DesignError", "design_for_period", "bisect",
           "ParameterError"]

