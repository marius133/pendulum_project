import json
import sys
from pathlib import Path

import mujoco_sim
from physics import SOLID, PrintSettings, amplitude_correction, analyze_pendulum

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def compare(order_number: int) -> dict:
    kit_dir = OUTPUT_DIR / f"order-{order_number}"
    parameters = json.loads((kit_dir / "parameters.json").read_text(encoding="utf-8"))
    result = json.loads((kit_dir / "result.json").read_text(encoding="utf-8"))
    density = parameters["material_density_m3"] / 1000

    solid = analyze_pendulum(parameters, density, SOLID)
    printed = analyze_pendulum(parameters, density, PrintSettings.from_parameters(parameters))
    sim = mujoco_sim.simulate(parameters, kit_dir / "mujoco")
    corrected = solid.period_s * amplitude_correction(sim["start_angle_deg"])
    return {
        "order": order_number,
        "target": result["target_period_s"],
        "arm": parameters["pendulum_arm_length_mm"],
        "weight": result["weight_size"],
        "T_printed": printed.period_s,
        "T_solid": solid.period_s,
        "T_solid_amp": corrected,
        "T_mj_theory": sim["period_theory_s"],
        "T_mj_sim": sim["period_sim_s"],
        "m_calc_g": solid.mass_kg * 1000,
        "m_mj_g": sim["mass_kg"] * 1000,
        "diff_percent": 100 * (sim["period_sim_s"] - corrected) / corrected,
    }


def main():
    if len(sys.argv) > 1:
        numbers = [int(a) for a in sys.argv[1:]]
    else:
        numbers = sorted(int(p.name.split("-")[1]) for p in OUTPUT_DIR.glob("order-*") if p.is_dir())
    rows = [compare(n) for n in numbers]

    header = ("| Order | Target [s] | Arm [mm] | Weight | T as printed [s] | T solid, calc [s] | "
              "T solid, calc, 20° [s] | T MuJoCo theory [s] | T MuJoCo simulated [s] | "
              "Mass calc / MuJoCo [g] | Sim vs calc [%] |")
    lines = [header, "|" + "---|" * 11]
    for r in rows:
        lines.append(f"| {r['order']} | {r['target']:.3f} | {r['arm']:.2f} | {r['weight']} | {r['T_printed']:.4f} | "
                     f"{r['T_solid']:.4f} | {r['T_solid_amp']:.4f} | {r['T_mj_theory']:.4f} | {r['T_mj_sim']:.4f} | "
                     f"{r['m_calc_g']:.2f} / {r['m_mj_g']:.2f} | {r['diff_percent']:+.2f} |")
    table = "\n".join(lines)
    print(table)
    (OUTPUT_DIR / "period_comparison.md").write_text(table + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
