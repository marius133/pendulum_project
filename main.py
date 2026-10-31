import json

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


