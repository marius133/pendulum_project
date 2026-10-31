import json
from cad import make_arm, export_model_3mf
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

arm = make_arm(parameters)

export_path = Path(__file__).resolve().parent / "output" / "arm.3mf"
export_model_3mf(arm,export_path,tolerance=0.1,angular_tolerance=0.1)
print(f"Saved to: {export_path}")

show(arm)