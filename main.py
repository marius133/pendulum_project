import json

from ezdxf.entities import tolerance

from cad import make_stand, export_model_3mf, make_base
from pathlib import Path
from cadquery.vis import show

#Reading json file
def load_parameters(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        cad_parameters = json.load(file)
    return cad_parameters

#Json-parameter value validation
def validate_parameters(cad_parameters):
    for name, value in cad_parameters.items():
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero. Not {value}")
    print("All CAD parameters are positive")

parameters = load_parameters("parameters.json")
print(parameters)
validate_parameters(parameters)

stand = make_stand(parameters)
base = make_base(parameters)

export_path = Path(__file__).resolve().parent / "output" / "stand.3mf"
export_model_3mf(stand,export_path,tolerance=0.1,angular_tolerance=0.1)
export_model_3mf(base,export_path,tolerance=0.1,angular_tolerance=0.1)
print(f"Saved to: {export_path}")

show(stand)
show(base)