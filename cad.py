import cadquery as cq
from pathlib import Path

from PIL.ImageChops import offset
from cadquery import exporters

#Makes the stands (two identical) that will hold the pendulum:
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

#Makes the base in which the stands will be placed on for stability:
def make_base(parameters):

    #Getting parameters form json file:

    width = parameters["base_width_mm"]
    length = parameters["base_length_mm"]
    thickness = parameters["base_thickness_mm"]
    slot_depth = parameters["slot_depth_mm"]
    stand_width = parameters["stand_width_mm"]
    stand_thickness = parameters["stand_thickness_mm"]
    stand_gap = parameters["stand_gap_mm"]
    slot_clearance = parameters["slot_clearance_mm"] #Compensates for 3d-print shrinkage and makes the stands fit the slots

    offset = (stand_gap + stand_thickness)/2

    #Create the actual base part
    base = cq.Workplane("XY").box(width,length,thickness)

    #Create the slots for the stands so that they can stand on their own without glue or screws etc
    base = base.faces(">Z").workplane().pushPoints([(0, -offset),(0,offset)]).rect(stand_width + slot_clearance,stand_thickness + slot_clearance).cutBlind(-slot_depth)
    return base



def export_model_3mf(model, file_path, tolerance, angular_tolerance):
    output_file = Path(file_path)
    output_file.parent.mkdir(parents=True, exist_ok=True) #Creates the folder in which the model(s) are exported to
    exporters.export(model, str(output_file), tolerance=tolerance, angularTolerance= angular_tolerance)
