import cadquery as cq
from pathlib import Path
from cadquery import exporters

def make_stand(parameters):

    #Getting parameters from json file:

    length = parameters["stand_length_mm"]
    width = parameters["stand_width_mm"]
    thickness = parameters["stand_thickness_mm"]
    hole_diameter = parameters["axle_hole_diameter_mm"]
    distance_from_end = parameters["hole_center_from_end_mm"]
    hole_y = length / 2 - distance_from_end

    #Create the actual geometry:

    stand = cq.Workplane("XY").box(width,length,thickness) #Creates the arm that will hold the pendulum in the xy-plane
    stand = stand.faces(">Z").workplane().center(0,hole_y).hole(hole_diameter) #Creates the hole in the arm

    return stand

def export_model_3mf(model, file_path, tolerance, angular_tolerance):
    output_file = Path(file_path)
    output_file.parent.mkdir(parents=True, exist_ok=True) #Creates the folder in which the model(s) are exported to
    exporters.export(model, str(output_file), tolerance=tolerance, angularTolerance= angular_tolerance)
