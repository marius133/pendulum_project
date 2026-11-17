from __future__ import annotations

import copy
from dataclasses import dataclass, field

from physics import PrintSettings, analyze_pendulum
from validation import validate_parameters

# (length along arm, width, thickness) of the weight in mm: small -> large
WEIGHT_SIZES = {
    "S": (10.0, 16.0, 8.0),
    "M": (12.0, 20.0, 10.0),
    "L": (16.0, 26.0, 14.0),
    "XL": (20.0, 32.0, 18.0),
}

SEARCH_VOXEL_MM = 0.5     # coarse model while searching (fast)
FINAL_VOXEL_MM = 0.25     # fine model for the reported result
ARM_TOLERANCE_MM = 0.25   # stop bisection when the interval is this small
DEFAULT_PERIOD_TOLERANCE = 0.02  # accept the order if |error| <= 2 % of target


@dataclass
class Candidate:
    weight_size: str
    arm_length_mm: float
    period_s: float
    mass_g: float


@dataclass
class Configuration:
    parameters: dict
    weight_size: str
    target_period_s: float
    period_s: float
    pendulum_mass_g: float
    achievable_range_s: tuple[float, float]
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def error_s(self) -> float:
        return self.period_s - self.target_period_s

    @property
    def error_percent(self) -> float:
        return 100.0 * self.error_s / self.target_period_s

    def within(self, tolerance: float = DEFAULT_PERIOD_TOLERANCE) -> bool:
        return abs(self.error_s) <= tolerance * self.target_period_s


def with_design(parameters: dict, arm_length_mm: float, weight_size: str) -> dict:
    """Copy of the parameters with a given arm length and weight at the arm end."""
    length, width, thickness = WEIGHT_SIZES[weight_size]
    p = copy.deepcopy(parameters)
    p["pendulum_arm_length_mm"] = round(arm_length_mm, 2)
    p["pendulum_weight_length_mm"] = length
    p["pendulum_weight_width_mm"] = width
    p["pendulum_weight_thickness_mm"] = thickness
    p["pendulum_weight_position_mm"] = round(arm_length_mm - length / 2, 2)
    return p


def is_valid(p: dict) -> bool:
    try:
        validate_parameters(p)
        return True
    except ValueError:
        return False


def arm_length_range(parameters: dict, weight_size: str) -> tuple[float, float] | None:
    """Shortest and longest arm that pass validation for this weight size."""
    hub_r = parameters["pendulum_cylinder_diameter_mm"] / 2
    length = WEIGHT_SIZES[weight_size][0]
    low = hub_r + length + 0.5                     # weight must lie outside the hub
    high = parameters["stand_length_mm"]           # can never be longer than the stand
    if not is_valid(with_design(parameters, low, weight_size)):
        return None
    # Bisection on validity: valid at `low`, invalid at `high`
    while high - low > ARM_TOLERANCE_MM:
        mid = (low + high) / 2
        if is_valid(with_design(parameters, mid, weight_size)):
            low = mid
        else:
            high = mid
    return hub_r + length + 0.5, low


def _period(p, density, settings, voxel_mm):
    r = analyze_pendulum(p, density, settings, voxel_mm)
    return r.period_s, r.mass_kg * 1000


def configure(parameters: dict, target_period_s: float, density_g_cm3: float,
              settings: PrintSettings | None = None) -> Configuration:
    """Find the design whose period is closest to `target_period_s`."""
    if settings is None:
        settings = PrintSettings.from_parameters(parameters)
    candidates: list[Candidate] = []
    shortest, longest = float("inf"), 0.0

    for size in WEIGHT_SIZES:
        limits = arm_length_range(parameters, size)
        if limits is None:
            continue
        low, high = limits
        t_low, _ = _period(with_design(parameters, low, size), density_g_cm3, settings, SEARCH_VOXEL_MM)
        t_high, _ = _period(with_design(parameters, high, size), density_g_cm3, settings, SEARCH_VOXEL_MM)
        shortest, longest = min(shortest, t_low), max(longest, t_high)

        if target_period_s <= t_low:
            arm = low
        elif target_period_s >= t_high:
            arm = high
        else:
            # Bisection: T(arm) is increasing, find arm with T(arm) = target
            while high - low > ARM_TOLERANCE_MM:
                mid = (low + high) / 2
                t_mid, _ = _period(with_design(parameters, mid, size), density_g_cm3, settings, SEARCH_VOXEL_MM)
                if t_mid < target_period_s:
                    low = mid
                else:
                    high = mid
            arm = (low + high) / 2

        p = with_design(parameters, arm, size)
        t, m = _period(p, density_g_cm3, settings, FINAL_VOXEL_MM)
        candidates.append(Candidate(size, round(arm, 2), t, m))

    if not candidates:
        raise ValueError("No pendulum design fits inside the size limits")

    best = min(candidates, key=lambda c: (round(abs(c.period_s - target_period_s), 3), c.mass_g))
    return Configuration(
        parameters=with_design(parameters, best.arm_length_mm, best.weight_size),
        weight_size=best.weight_size,
        target_period_s=target_period_s,
        period_s=best.period_s,
        pendulum_mass_g=best.mass_g,
        achievable_range_s=(shortest, longest),
        candidates=candidates,
    )


if __name__ == "__main__":
    import sys
    from validation import load_parameters
    target = float(sys.argv[1]) if len(sys.argv) > 1 else 0.45
    params = load_parameters("parameters.json")
    cfg = configure(params, target, params["material_density_m3"] / 1000)
    for c in cfg.candidates:
        print(f"  weight {c.weight_size:2s}: arm {c.arm_length_mm:6.2f} mm -> T = {c.period_s:.4f} s, m = {c.mass_g:.2f} g")
    print(f"Chosen: weight {cfg.weight_size}, arm {cfg.parameters['pendulum_arm_length_mm']} mm, "
          f"T = {cfg.period_s:.4f} s (target {target} s, error {cfg.error_s*1000:+.1f} ms = {cfg.error_percent:+.2f} %)")
    print(f"Achievable range: {cfg.achievable_range_s[0]:.3f} - {cfg.achievable_range_s[1]:.3f} s")
