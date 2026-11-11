"""
Command line demo: design a kit for a period, print masses and period, export files.

    python -m pendulum_kit                         # default parameters as they are
    python -m pendulum_kit --period 0.7            # solve arm length + weight for 0.7 s
    python -m pendulum_kit --period 0.7 --weight 30 --max-height 200 --out output/order_001

AI-assisted: first version generated with Claude (Anthropic).
"""
from __future__ import annotations

import argparse
import sys

from .design import DesignError, DesignRequest, design_for_period
from .params import DEFAULT_PARAMS_FILE, KitParameters, ParameterError
from .physics import kit_masses, pendulum_properties, total_material_g


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pendulum_kit")
    ap.add_argument("--params", default=DEFAULT_PARAMS_FILE, help="parameter JSON file")
    ap.add_argument("--period", type=float, help="target period in seconds")
    ap.add_argument("--weight", type=float, help="weight diameter in mm (default: program picks)")
    ap.add_argument("--axle", type=float, help="axle diameter in mm")
    ap.add_argument("--max-height", type=float)
    ap.add_argument("--max-material", type=float, help="grams")
    ap.add_argument("--out", help="folder for 3MF files (needs CadQuery)")
    args = ap.parse_args(argv)

    try:
        params = KitParameters.load(args.params)
        if args.period:
            result = design_for_period(params, DesignRequest(
                target_period_s=args.period, weight_diameter_mm=args.weight,
                axle_diameter_mm=args.axle, max_height_mm=args.max_height,
                max_material_g=args.max_material))
            params = result.params
            print("Design:", result.summary())
    except (ParameterError, DesignError) as exc:
        print(f"Cannot make this kit: {exc}", file=sys.stderr)
        return 1

    masses = kit_masses(params)
    print(f"\n{'part':<8}{'count':>6}{'volume cm3':>12}{'infill':>8}{'mass g':>9}")
    for m in masses.values():
        print(f"{m.name:<8}{m.count:>6}{m.volume_mm3 / 1000:>12.2f}"
              f"{params.infill(m.name):>8.0%}{m.mass_g:>9.2f}")
    print(f"{'total material':<34}{total_material_g(masses):>9.1f} g")

    pend = pendulum_properties(params, masses)
    amp = params.data.get("simulation", {}).get("amplitude_deg", 0)
    print(f"\nSwinging mass {pend.mass_g:.2f} g, centre of mass {pend.com_distance_mm:.1f} mm "
          f"below the axle, I = {pend.inertia_g_mm2:.0f} g*mm^2 about the axle")
    print(f"Period: {pend.period_s:.4f} s (small angle), {pend.period_amplitude_s:.4f} s at {amp} deg")

    if args.out:
        try:
            from .cad import export_kit
        except ImportError:
            print("\nCadQuery is not installed, so no 3MF files were written (pip install cadquery).")
            return 0
        files = export_kit(params, args.out)
        print(f"\nWrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
