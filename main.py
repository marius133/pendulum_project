from cad import export_model_3mf,make_assembly, export_kit
from validation import validate_parameters, load_parameters
from pathlib import Path
from cadquery.vis import show

parameters = load_parameters("parameters.json")
print(parameters)
validate_parameters(parameters)

export_path = Path(__file__).resolve().parent / "output"

kit = export_kit(parameters,export_path)
assembly = make_assembly(parameters)

export_model_3mf(assembly.toCompound(),export_path / "assembly.3mf",0.1,0.1)

print(f"Saved to: {export_path}")

show(assembly)