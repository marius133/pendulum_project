"""Mass, centre of mass, moment of inertia and swing period of the kit.

The parts are described with the same parameters as in cad.py, but instead of
asking CadQuery for the volume we fill each part with small cubes (voxels) using
NumPy. This gives us an independent check of the CAD/MuJoCo model, and it makes
it easy to model 3D printing: voxels close to the surface are printed solid
(perimeters and top/bottom layers), voxels inside are printed with infill.

Units: the geometry is in millimetres, masses are returned in grams and kg,
inertia in kg*m^2 and periods in seconds.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

G = 9.81  # gravity [m/s^2]

# How many of each part one kit contains
PART_COUNT = {"base": 1, "stand": 2, "axle": 1, "pendulum": 1}

# Which spool (order field) each part is printed from
PART_TO_SPOOL_FIELD = {"base": "base", "stand": "side", "axle": "axle", "pendulum": "pendulum"}


# ---------------------------------------------------------------------------
# Print settings
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PrintSettings:
    infill: float = 0.15             # infill fraction (0.15 = 15 %)
    perimeters: int = 2              # number of walls
    extrusion_width_mm: float = 0.45 # width of one wall line
    layer_height_mm: float = 0.20
    solid_layers: int = 4            # solid layers at top and bottom

    @property
    def wall_mm(self) -> float:
        return self.perimeters * self.extrusion_width_mm

    @property
    def skin_mm(self) -> float:
        return self.solid_layers * self.layer_height_mm

    @classmethod
    def from_parameters(cls, parameters: dict) -> "PrintSettings":
        return cls(
            infill=parameters.get("print_infill_fraction", cls.infill),
            perimeters=parameters.get("print_perimeters", cls.perimeters),
            extrusion_width_mm=parameters.get("print_extrusion_width_mm", cls.extrusion_width_mm),
            layer_height_mm=parameters.get("print_layer_height_mm", cls.layer_height_mm),
            solid_layers=parameters.get("print_solid_layers", cls.solid_layers),
        )


SOLID = PrintSettings(infill=1.0)  # 100 % infill = the same as a solid part


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@dataclass
class PartMass:
    name: str
    count: int
    volume_mm3: float      # volume of ONE part
    shell_mm3: float       # of which printed solid (walls + top/bottom)
    density_g_cm3: float
    mass_g: float          # mass of ONE part as printed

    @property
    def total_mass_g(self) -> float:
        return self.count * self.mass_g


@dataclass
class PendulumProperties:
    mass_kg: float
    com_distance_m: float   # axle -> centre of mass
    inertia_kg_m2: float    # about the axle
    period_s: float         # small-angle period

    @property
    def equivalent_length_m(self) -> float:
        """Length of the simple pendulum that has the same period."""
        return self.inertia_kg_m2 / (self.mass_kg * self.com_distance_m)


# ---------------------------------------------------------------------------
# Voxel geometry (mirrors cad.py; z is the printing direction)
# ---------------------------------------------------------------------------
class VoxelGrid:
    """A regular grid of voxel centres covering a box [min, max] in mm."""

    def __init__(self, lower, upper, voxel_mm: float):
        self.h = voxel_mm
        axes = [np.arange(lo, hi, voxel_mm) + voxel_mm / 2 for lo, hi in zip(lower, upper)]
        self.x, self.y, self.z = np.meshgrid(*axes, indexing="ij", sparse=True)

    @property
    def voxel_volume(self) -> float:
        return self.h ** 3


def _box(g: VoxelGrid, cx, cy, cz, sx, sy, sz):
    return (np.abs(g.x - cx) <= sx / 2) & (np.abs(g.y - cy) <= sy / 2) & (np.abs(g.z - cz) <= sz / 2)


def _cylinder_z(g: VoxelGrid, cx, cy, radius, z_low=-np.inf, z_high=np.inf):
    return ((g.x - cx) ** 2 + (g.y - cy) ** 2 <= radius ** 2) & (g.z >= z_low) & (g.z <= z_high)


def base_voxels(p, h):
    w, l, t = p["base_width_mm"], p["base_length_mm"], p["base_thickness_mm"]
    g = VoxelGrid((-w / 2, -l / 2, -t / 2), (w / 2, l / 2, t / 2), h)
    solid = _box(g, 0, 0, 0, w, l, t)
    offset = (p["stand_gap_mm"] + p["stand_thickness_mm"]) / 2
    slot_x = p["stand_width_mm"] + p["slot_clearance_mm"]
    slot_y = p["stand_thickness_mm"] + p["slot_clearance_mm"]
    depth = p["slot_depth_mm"]
    for y in (-offset, offset):
        solid &= ~_box(g, 0, y, t / 2 - depth / 2, slot_x, slot_y, depth)
    return g, solid


def stand_voxels(p, h):
    w, l, t = p["stand_width_mm"], p["stand_length_mm"], p["stand_thickness_mm"]
    g = VoxelGrid((-w / 2, -l / 2, -t / 2), (w / 2, l / 2, t / 2), h)
    hole_y = l / 2 - p["hole_center_from_end_mm"]
    solid = _box(g, 0, 0, 0, w, l, t) & ~_cylinder_z(g, 0, hole_y, p["axle_hole_diameter_mm"] / 2)
    return g, solid


def axle_voxels(p, h):
    r = p["axle_diameter_mm"] / 2
    length = p["stand_gap_mm"] + 2 * p["stand_thickness_mm"]
    g = VoxelGrid((-r, -r, -length / 2), (r, r, length / 2), h)
    return g, _cylinder_z(g, 0, 0, r, -length / 2, length / 2)


def pendulum_voxels(p, h):
    """Hub + arm with axle hole, and the weight. The axle is the z axis."""
    hub_r = p["pendulum_cylinder_diameter_mm"] / 2
    hub_l = p["pendulum_cylinder_length_mm"]
    hole_r = (p["axle_diameter_mm"] + p["pendulum_cylinder_clearance_mm"]) / 2
    arm_l, arm_w, arm_t = p["pendulum_arm_length_mm"], p["pendulum_arm_width_mm"], p["pendulum_arm_thickness_mm"]
    w_w, w_l, w_t = p["pendulum_weight_width_mm"], p["pendulum_weight_length_mm"], p["pendulum_weight_thickness_mm"]
    w_pos = p["pendulum_weight_position_mm"]

    half_x = max(hub_r, arm_w / 2, w_w / 2)
    y_low = -max(arm_l, w_pos + w_l / 2)
    half_z = max(hub_l, arm_t, w_t) / 2
    g = VoxelGrid((-half_x, y_low, -half_z), (half_x, hub_r, half_z), h)

    hub = _cylinder_z(g, 0, 0, hub_r, -hub_l / 2, hub_l / 2)
    arm = _box(g, 0, -arm_l / 2, 0, arm_w, arm_l, arm_t)
    hole = _cylinder_z(g, 0, 0, hole_r)
    weight = _box(g, 0, -w_pos, 0, w_w, w_l, w_t)
    return g, ((hub | arm) & ~hole) | weight   # same order of operations as cad.py


PART_VOXELS = {"base": base_voxels, "stand": stand_voxels, "axle": axle_voxels, "pendulum": pendulum_voxels}


# ---------------------------------------------------------------------------
# Printing model: shell (solid) and core (infill)
# ---------------------------------------------------------------------------
def _erode_axis(mask: np.ndarray, radius: int, axis: int) -> np.ndarray:
    """Keep a voxel only if every voxel within `radius` along `axis` is inside.

    Uses a running sum (cumulative sum), so the cost is O(n) per axis.
    Voxels outside the grid count as outside the part.
    """
    if radius <= 0:
        return mask
    window = 2 * radius + 1
    pad = [(0, 0)] * mask.ndim
    pad[axis] = (radius + 1, radius)
    counts = np.cumsum(np.pad(mask, pad).astype(np.int32), axis=axis)
    upper = np.take(counts, range(window, counts.shape[axis]), axis=axis)
    lower = np.take(counts, range(0, counts.shape[axis] - window), axis=axis)
    return (upper - lower) == window


def core_mask(solid: np.ndarray, settings: PrintSettings, h: float) -> np.ndarray:
    """Voxels that are printed with infill (i.e. not walls or solid skin)."""
    rxy = math.ceil(settings.wall_mm / h)
    rz = math.ceil(settings.skin_mm / h)
    core = _erode_axis(solid, rxy, 0)
    core = _erode_axis(core, rxy, 1)
    core = _erode_axis(core, rz, 2)
    return core & solid


def _density_field(solid, settings, h):
    """Relative material density per voxel: 1 in the shell, `infill` in the core."""
    field = solid.astype(np.float64)
    if settings.infill < 1.0:
        field[core_mask(solid, settings, h)] = settings.infill
    return field


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------
def calculate_mass(volume_m3, density_kg_m3):
    """m = rho * V (kept from the first version, used by the tests)."""
    return density_kg_m3 * volume_m3


def part_mass(name: str, parameters: dict, density_g_cm3: float,
              settings: PrintSettings, voxel_mm: float = 0.25) -> PartMass:
    g, solid = PART_VOXELS[name](parameters, voxel_mm)
    field = solid.astype(np.float64) if settings.infill >= 1.0 else _density_field(solid, settings, voxel_mm)
    dv = g.voxel_volume
    volume = solid.sum() * dv
    core = (solid & (field < 1.0)).sum() * dv
    material_mm3 = field.sum() * dv               # volume of plastic actually printed
    return PartMass(name=name, count=PART_COUNT[name], volume_mm3=volume, shell_mm3=volume - core,
                    density_g_cm3=density_g_cm3, mass_g=material_mm3 * density_g_cm3 / 1000.0)


def kit_masses(parameters: dict, densities_g_cm3: dict, settings: PrintSettings,
               voxel_mm: float = 0.25) -> dict:
    """Mass of each part type. `densities_g_cm3` maps part name -> density."""
    return {name: part_mass(name, parameters, densities_g_cm3[name], settings, voxel_mm)
            for name in PART_VOXELS}


def calculate_period(inertia_kg_m2: float, mass_kg: float, com_distance_m: float, g: float = G) -> float:
    """Small-angle period of a physical pendulum, T = 2*pi*sqrt(I / (m g d))."""
    return 2 * math.pi * math.sqrt(inertia_kg_m2 / (mass_kg * g * com_distance_m))


def amplitude_correction(start_angle_deg: float) -> float:
    """Factor T(theta0)/T0 for a finite release angle (series to 4th order)."""
    t = math.radians(start_angle_deg)
    return 1 + t ** 2 / 16 + 11 * t ** 4 / 3072


def analyze_pendulum(parameters: dict, density_g_cm3: float,
                     settings: PrintSettings = SOLID, voxel_mm: float = 0.25) -> PendulumProperties:
    """Mass, centre of mass, inertia about the axle and period of the swinging part."""
    g, solid = pendulum_voxels(parameters, voxel_mm)
    field = solid.astype(np.float64) if settings.infill >= 1.0 else _density_field(solid, settings, voxel_mm)

    rho = density_g_cm3 * 1000.0                   # kg/m^3
    dm = field * (rho * (voxel_mm * 1e-3) ** 3)    # kg per voxel
    mass = dm.sum()
    x = g.x * 1e-3                                 # m
    y = g.y * 1e-3
    x_c = (dm * x).sum() / mass
    y_c = (dm * y).sum() / mass
    inertia = (dm * (x ** 2 + y ** 2)).sum()       # about the z (axle) axis
    d = math.hypot(x_c, y_c)
    return PendulumProperties(mass_kg=mass, com_distance_m=d, inertia_kg_m2=inertia,
                              period_s=calculate_period(inertia, mass, d))


if __name__ == "__main__":
    from validation import load_parameters
    params = load_parameters("parameters.json")
    settings = PrintSettings.from_parameters(params)
    density = params["material_density_m3"] / 1000
    for label, s in (("solid", SOLID), ("as printed", settings)):
        r = analyze_pendulum(params, density, s)
        print(f"{label:10s}: m={r.mass_kg*1000:.2f} g  d={r.com_distance_m*1000:.2f} mm  "
              f"I={r.inertia_kg_m2:.3e} kg m^2  T={r.period_s:.4f} s")
    masses = kit_masses(params, {n: density for n in PART_VOXELS}, settings)
    for m in masses.values():
        print(f"{m.name:9s} x{m.count}: {m.mass_g:6.2f} g each (volume {m.volume_mm3:8.0f} mm^3, shell {m.shell_mm3:8.0f})")
    print(f"kit total: {sum(m.total_mass_g for m in masses.values()):.2f} g")
