from cad import make_stand, export_model_3mf, make_base, make_axle, make_assembly,make_pendulum
from validation import validate_parameters, load_parameters
from pathlib import Path
from cadquery.vis import show

parameters = load_parameters("parameters.json")
print(parameters)
validate_parameters(parameters)

stand = make_stand(parameters)
base = make_base(parameters)
axle = make_axle(parameters)
pendulum = make_pendulum(parameters)
assembly = make_assembly(parameters)

export_path = Path(__file__).resolve().parent / "output"

export_model_3mf(stand,export_path / "stand.3mf",0.1,0.1)
export_model_3mf(base,export_path / "base.3mf",0.1, 0.1)
export_model_3mf(axle,export_path / "axle.3mf",0.1, 0.1)
export_model_3mf(pendulum,export_path / "pendulum.3mf",0.1, 0.1)


export_model_3mf(assembly.toCompound(),export_path / "assembly.3mf",0.1,0.1)

print(f"Saved to: {export_path}")

show(assembly)
