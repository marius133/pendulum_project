import argparse
import math
import time
from pathlib import Path

import mujoco
import numpy as np
import mujoco.viewer
from cadquery import exporters

from cad import make_base, make_stand, make_axle, make_pendulum
from validation import load_parameters, validate_parameters

# ---- Simulation settings -------------------------------------------------
START_ANGLE_DEG = 20.0   # how far the pendulum is pulled out before release
HINGE_DAMPING = 0.0      # friction in the hinge [N*m*s/rad]; 0 = swings forever
TIMESTEP = 0.0005        # simulation timestep [s]
MEASURE_TIME = 10.0      # seconds simulated (without viewer) to measure the period

PROJECT_DIR = Path(__file__).resolve().parent
MESH_DIR = PROJECT_DIR / "output" / "mujoco"
MM = 0.001               # CadQuery works in mm, MuJoCo in metres


def export_meshes(parameters, mesh_dir=MESH_DIR):
    """Export each part as an STL file (in mm) that MuJoCo can load."""
    mesh_dir = Path(mesh_dir)
    mesh_dir.mkdir(parents=True, exist_ok=True)
    parts = {
        "base": make_base(parameters),
        "stand": make_stand(parameters),
        "axle": make_axle(parameters),
        "pendulum": make_pendulum(parameters),
    }
    for name, part in parts.items():
        exporters.export(part, str(mesh_dir / f"{name}.stl"),
                         tolerance=0.05, angularTolerance=0.1)


def build_mjcf(parameters, mesh_dir=MESH_DIR, density=None):
    """Create the MuJoCo XML model. Positions match make_assembly() in cad.py."""
    base_thickness = parameters["base_thickness_mm"]
    stand_length = parameters["stand_length_mm"]
    slot_depth = parameters["slot_depth_mm"]
    hole_from_end = parameters["hole_center_from_end_mm"]
    stand_gap = parameters["stand_gap_mm"]
    stand_thickness = parameters["stand_thickness_mm"]
    if density is None:
        density = parameters["material_density_m3"]  # kg/m^3

    stand_z = (base_thickness / 2 - slot_depth + stand_length / 2) * MM
    axle_z = (base_thickness / 2 + stand_length - slot_depth - hole_from_end) * MM
    offset = (stand_gap + stand_thickness) / 2 * MM
    floor_z = -base_thickness / 2 * MM

    # Same rotation as cq.Location(..., (1, 0, 0), 90): 90 degrees about X
    rot_x90 = "0.7071068 0.7071068 0 0"
    s = f"{MM} {MM} {MM}"
    mesh_dir = Path(mesh_dir).as_posix()

    return f"""
<mujoco model="pendulum_kit">
  <compiler meshdir="{mesh_dir}" angle="radian"/>
  <option timestep="{TIMESTEP}" gravity="0 0 -9.81">
    <flag contact="disable"/>
  </option>

  <asset>
    <mesh name="base"     file="base.stl"     scale="{s}"/>
    <mesh name="stand"    file="stand.stl"    scale="{s}"/>
    <mesh name="axle"     file="axle.stl"     scale="{s}"/>
    <mesh name="pendulum" file="pendulum.stl" scale="{s}" inertia="exact"/>
    <texture name="grid" type="2d" builtin="checker" width="512" height="512"
             rgb1="0.85 0.85 0.85" rgb2="0.75 0.75 0.75"/>
    <material name="grid" texture="grid" texrepeat="20 20"/>
  </asset>

  <worldbody>
    <light pos="0.2 -0.3 0.5" dir="-0.3 0.5 -1" diffuse="0.8 0.8 0.8"/>
    <geom name="floor" type="plane" size="0.5 0.5 0.01" pos="0 0 {floor_z}" material="grid"/>

    <!-- Static parts of the kit -->
    <geom name="base" type="mesh" mesh="base" rgba="0.3 0.5 0.8 1"/>
    <geom name="stand_left"  type="mesh" mesh="stand" pos="0 {-offset} {stand_z}" quat="{rot_x90}" rgba="0.3 0.5 0.8 1"/>
    <geom name="stand_right" type="mesh" mesh="stand" pos="0 {offset} {stand_z}"  quat="{rot_x90}" rgba="0.3 0.5 0.8 1"/>
    <geom name="axle" type="mesh" mesh="axle" pos="0 0 {axle_z}" quat="{rot_x90}" rgba="0.6 0.6 0.6 1"/>

    <!-- The swinging pendulum. Its hinge is the axle (body Z axis = world Y). -->
    <body name="pendulum" pos="0 0 {axle_z}" quat="{rot_x90}">
      <joint name="hinge" type="hinge" axis="0 0 1" damping="{HINGE_DAMPING}"/>
      <geom name="pendulum" type="mesh" mesh="pendulum" density="{density}" rgba="0.9 0.4 0.2 1"/>
    </body>
  </worldbody>
</mujoco>
"""


def reset(model, data):
    mujoco.mj_resetData(model, data)
    data.qpos[0] = math.radians(START_ANGLE_DEG)
    mujoco.mj_forward(model, data)


# measure_physics(), simulate() and the --params/--no-viewer options are AI-assisted
# (Claude, Anthropic), refactored from our report_physics(); reviewed by the group.
def measure_physics(model, data):
    """Mass, inertia and period (theory vs. simulation) of the pendulum body."""
    body = model.body("pendulum").id
    mass = model.body_mass[body]

    # Inertia about the hinge axis (for a single hinge this is the mass matrix)
    mujoco.mj_resetData(model, data)
    mujoco.mj_forward(model, data)
    R = np.zeros(9)
    mujoco.mju_quat2Mat(R, model.body_iquat[body])
    R = R.reshape(3, 3)
    I_body = R @ np.diag(model.body_inertia[body]) @ R.T
    x, y, _ = model.body_ipos[body]
    inertia_axis = I_body[2, 2] + mass * (x**2 + y**2)
    # Distance from axle to centre of mass when hanging straight down
    d = math.dist(data.xipos[body], data.xpos[body])
    g = 9.81

    period_theory = 2 * math.pi * math.sqrt(inertia_axis / (mass * g * d))

    # Measure the period from the simulation: time between upward zero crossings
    reset(model, data)
    crossings = []
    prev = data.qpos[0]
    while data.time < MEASURE_TIME:
        mujoco.mj_step(model, data)
        cur = data.qpos[0]
        if prev < 0 <= cur:
            crossings.append(data.time)
        prev = cur
    if len(crossings) >= 2:
        period_sim = (crossings[-1] - crossings[0]) / (len(crossings) - 1)
    else:
        period_sim = float("nan")

    return {"mass_kg": mass, "com_distance_m": d, "inertia_kg_m2": inertia_axis,
            "period_theory_s": period_theory, "period_sim_s": period_sim,
            "start_angle_deg": START_ANGLE_DEG}


def report_physics(model, data):
    """Print mass, inertia and period (theory vs. simulation)."""
    r = measure_physics(model, data)
    print("\n--- Pendulum (from MuJoCo) ---")
    print(f"Mass:                      {r['mass_kg'] * 1000:.2f} g")
    print(f"Axle -> centre of mass:    {r['com_distance_m'] * 1000:.2f} mm")
    print(f"Inertia about axle:        {r['inertia_kg_m2']:.3e} kg*m^2")
    print(f"Period, small-angle theory:{r['period_theory_s']:8.4f} s")
    print(f"Period, simulated ({START_ANGLE_DEG:.0f} deg): {r['period_sim_s']:.4f} s\n")
    return r


def simulate(parameters, mesh_dir=MESH_DIR, density=None):
    """Build the MuJoCo model for a parameter set and measure the period (no viewer)."""
    export_meshes(parameters, mesh_dir)
    model = mujoco.MjModel.from_xml_string(build_mjcf(parameters, mesh_dir, density))
    data = mujoco.MjData(model)
    return measure_physics(model, data)


def main():
    # --params lets us simulate the parameters of a produced order, e.g.
    #   python mujoco_sim.py --params output/order-1/parameters.json
    parser = argparse.ArgumentParser(description="Simulate the pendulum in MuJoCo")
    parser.add_argument("--params", default=PROJECT_DIR / "parameters.json")
    parser.add_argument("--no-viewer", action="store_true", help="only print the period")
    args = parser.parse_args()

    parameters = load_parameters(args.params)
    validate_parameters(parameters)

    export_meshes(parameters)
    model = mujoco.MjModel.from_xml_string(build_mjcf(parameters))
    data = mujoco.MjData(model)

    report_physics(model, data)
    if args.no_viewer:
        return

    # Run the viewer in real time until the window is closed
    reset(model, data)
    with mujoco.viewer.launch_passive(model, data) as viewer:
        viewer.cam.lookat[:] = [0, 0, 0.05]
        viewer.cam.distance = 0.35
        viewer.cam.azimuth = 0
        viewer.cam.elevation = -15
        start = time.perf_counter()
        while viewer.is_running():
            # Step the simulation until it has caught up with the real clock
            while data.time < time.perf_counter() - start:
                mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(1 / 60)  # ~60 frames per second


if __name__ == "__main__":
    main()