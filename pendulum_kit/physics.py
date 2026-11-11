from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .geometry import PartGeometry, kit_geometry
from .params import PART_COUNT, PARTS, SWINGING_PARTS, KitParameters

G_MM_S2 = 9810.0     #mm/s^2

@dataclass(frozen=True)
class PartMass:
    name: str
    count: int                  
    volume_mm3: float
    shell_volume_mm3: float
    mass_g: float             
    effective_density: float    # g/mm^3

    @property
    def total_mass_g(self) -> float:
        return self.mass_g * self.count


@dataclass(frozen=True)
class PendulumProperties:
    mass_g: float        
    com_distance_mm: float  
    inertia_g_mm2: float   
    period_s: float       
    period_amplitude_s: float 
    equivalent_length_mm: float  


def shell_volume(geom: PartGeometry, print_settings: dict) -> float:
    wall = print_settings["walls"] * print_settings["line_width"]
    cap = print_settings["top_bottom_layers"] * print_settings["layer_height"]
    return min(geom.volume, geom.side_area * wall + geom.cap_area * cap)


def part_mass(geom: PartGeometry, density_g_cm3: float, infill: float,
              print_settings: dict, count: int = 1) -> PartMass:
    shell = shell_volume(geom, print_settings)
    printed_volume = shell + infill * (geom.volume - shell)       
    mass = density_g_cm3 * printed_volume / 1000.0              
    return PartMass(geom.name, count, geom.volume, shell, mass, mass / geom.volume)


def kit_masses(p: KitParameters, geometry: dict[str, PartGeometry] | None = None) -> dict[str, PartMass]:
    geometry = geometry or kit_geometry(p)
    return {
        part: part_mass(geometry[part], p.density(part), p.infill(part), p["print"], PART_COUNT[part])
        for part in PARTS
    }


def total_material_g(masses: dict[str, PartMass]) -> float:
    return sum(m.total_mass_g for m in masses.values())


def material_per_filament(p: KitParameters, masses: dict[str, PartMass]) -> dict:
    needed = defaultdict(float)
    for part, m in masses.items():
        mat = p["materials"][part]
        key = mat.get("filament_id") if mat.get("filament_id") is not None else mat.get("name", part)
        needed[key] += m.total_mass_g
    return dict(needed)


def small_angle_period(inertia_g_mm2: float, mass_g: float, com_distance_mm: float) -> float:
    return 2 * math.pi * math.sqrt(inertia_g_mm2 / (mass_g * G_MM_S2 * com_distance_mm))


def amplitude_correction(period0_s: float, amplitude_rad: float) -> float:
    th2 = amplitude_rad ** 2
    return period0_s * (1 + th2 / 16 + 11 * th2 ** 2 / 3072)


def pendulum_properties(p: KitParameters, masses: dict[str, PartMass] | None = None,
                        geometry: dict[str, PartGeometry] | None = None) -> PendulumProperties:
    geometry = geometry or kit_geometry(p)
    masses = masses or kit_masses(p, geometry)

    m_total = sum(masses[part].mass_g for part in SWINGING_PARTS)
    d = sum(masses[part].mass_g * geometry[part].com_distance for part in SWINGING_PARTS) / m_total
    inertia = sum(masses[part].effective_density * geometry[part].second_moment
                  for part in SWINGING_PARTS)

    t0 = small_angle_period(inertia, m_total, d)
    amp = math.radians(p.data.get("simulation", {}).get("amplitude_deg", 0.0))
    return PendulumProperties(
        mass_g=m_total,
        com_distance_mm=d,
        inertia_g_mm2=inertia,
        period_s=t0,
        period_amplitude_s=amplitude_correction(t0, amp),
        equivalent_length_mm=inertia / (m_total * d),
    )

