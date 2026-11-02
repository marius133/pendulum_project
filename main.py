from cad import make_stand, export_model_3mf, make_base, make_axle
from validation import validate_parameters, load_parameters
from pathlib import Path
from cadquery.vis import show

parameters = load_parameters("parameters.json")
print(parameters)
validate_parameters(parameters)

stand = make_stand(parameters)
base = make_base(parameters)
axle = make_axle(parameters)

export_path = Path(__file__).resolve().parent / "output" / "stand.3mf"
export_model_3mf(stand,export_path,tolerance=0.1,angular_tolerance=0.1)
export_model_3mf(base,export_path,tolerance=0.1,angular_tolerance=0.1)
export_model_3mf(axle,export_path,tolerance=0.1,angular_tolerance=0.1)
print(f"Saved to: {export_path}")

show(stand,base, axle)