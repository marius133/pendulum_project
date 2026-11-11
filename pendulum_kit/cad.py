from __future__ import annotations

from pathlib import Path

import cadquery as cq

from .params import KitParameters

EXPORT_TOLERANCE = dict(tolerance=0.05, angularTolerance=0.1)

def make_base(p: KitParameters) -> cq.Workplane:
    b, s, c = p["base"], p["stand"], p["clearance"]
    base = cq.Workplane("XY").box(p.base_length, b["width"], b["thickness"],
                                  centered=(True, True, False))
    for x in p.stand_x_positions:
        slot = (cq.Workplane("XY").center(x, 0)
                .rect(s["thickness"] + c["fit"], s["tab_length"] + c["fit"])
                .extrude(b["thickness"]))
        base = base.cut(slot)
    return base


def make_stand_side(p: KitParameters) -> cq.Workplane:
    s, b = p["stand"], p["base"]
    t = s["thickness"]
    plate = cq.Workplane("XY").center(0, s["height"] / 2).rect(s["width"], s["height"]).extrude(t)
    tab = (cq.Workplane("XY").center(0, -b["thickness"] / 2)
           .rect(s["tab_length"], b["thickness"]).extrude(t))
    hole = (cq.Workplane("XY").center(0, p.pivot_height)
            .circle(p.axle_hole_stand / 2).extrude(t))         
    return plate.union(tab).cut(hole)


def make_arm(p: KitParameters) -> cq.Workplane:
    a = p["arm"]
    t = a["thickness"]
    bar = cq.Workplane("XY").center(0, -a["length"] / 2).rect(a["width"], a["length"]).extrude(t)
    hub = cq.Workplane("XY").circle(a["hub_diameter"] / 2).extrude(t)
    hole = cq.Workplane("XY").circle(p.axle_hole_arm / 2).extrude(t)   
    return bar.union(hub).cut(hole)


def make_weight(p: KitParameters) -> cq.Workplane:
    w = p["weight"]
    hole_y, hole_x = p.weight_hole
    body = cq.Workplane("XY").circle(w["diameter"] / 2).extrude(w["height"])
    hole = cq.Workplane("XY").rect(hole_y, hole_x).extrude(w["height"])
    return body.cut(hole)


def make_axle(p: KitParameters) -> cq.Workplane:
    return cq.Workplane("XY").circle(p["axle"]["diameter"] / 2).extrude(p.axle_length)


def make_kit(p: KitParameters) -> dict[str, cq.Workplane]:
    stand = make_stand_side(p)
    return {
        "base": make_base(p),
        "stand_side_1": stand,
        "stand_side_2": stand,
        "arm": make_arm(p),
        "weight": make_weight(p),
        "axle": make_axle(p),
    }


def cad_volumes(p: KitParameters) -> dict[str, float]:
    kit = make_kit(p)
    names = {"base": "base", "stand": "stand_side_1", "arm": "arm", "weight": "weight", "axle": "axle"}
    return {part: kit[name].val().Volume() for part, name in names.items()}


def make_assembly(p: KitParameters, parts: dict[str, cq.Workplane]) -> cq.Assembly:
    b_t = p["base"]["thickness"]
    pivot_z = b_t + p.pivot_height
    s_t = p["stand"]["thickness"]
    arm_end_z = pivot_z - p["arm"]["length"]

    stand_up = (cq.Vector(1, 1, 1), 120)

    assy = cq.Assembly(name="pendulum_kit")
    assy.add(parts["base"], name="base", color=cq.Color("gray"))
    x1, x2 = p.stand_x_positions
    assy.add(parts["stand_side_1"], name="stand_side_1", color=cq.Color("blue"),
             loc=cq.Location(cq.Vector(x1 - s_t / 2, 0, b_t), *stand_up))
    assy.add(parts["stand_side_2"], name="stand_side_2", color=cq.Color("blue"),
             loc=cq.Location(cq.Vector(x2 - s_t / 2, 0, b_t), *stand_up))
    assy.add(parts["arm"], name="arm", color=cq.Color("orange"),
             loc=cq.Location(cq.Vector(-p["arm"]["thickness"] / 2, 0, pivot_z), *stand_up))
  
    assy.add(parts["weight"], name="weight", color=cq.Color("red"),
             loc=cq.Location(cq.Vector(0, 0, arm_end_z + p["weight"]["height"]),
                             cq.Vector(1, 1, 0), 180))

    assy.add(parts["axle"], name="axle", color=cq.Color("black"),
             loc=cq.Location(cq.Vector(-p.axle_length / 2, 0, pivot_z), cq.Vector(0, 1, 0), 90))
    return assy



def fits_build_volume(part: cq.Workplane, p: KitParameters) -> bool:
    bb = part.val().BoundingBox()
    pr = p["printer"]
    footprint, bed = sorted((bb.xlen, bb.ylen)), sorted((pr["bed_x"], pr["bed_y"]))
    return footprint[0] <= bed[0] and footprint[1] <= bed[1] and bb.zlen <= pr["max_z"]


def lay_out(parts: dict[str, cq.Workplane], p: KitParameters) -> list[list[cq.Workplane]]:
    pr = p["printer"]
    bed_x, bed_y, gap = pr["bed_x"], pr["bed_y"], pr["part_gap"]

    def footprint(part):
        bb = part.val().BoundingBox()
        fits = bb.xlen <= bed_x and bb.ylen <= bed_y
        fits_turned = bb.ylen <= bed_x and bb.xlen <= bed_y
        if not fits and fits_turned:                      
            part = part.rotate((0, 0, 0), (0, 0, 1), 90)
        return part

    ordered = sorted((footprint(pt) for pt in parts.values()),
                     key=lambda pt: pt.val().BoundingBox().ylen, reverse=True)
    plates, plate = [], []
    x = y = row_height = 0.0
    for part in ordered:
        bb = part.val().BoundingBox()
        if x > 0 and x + bb.xlen > bed_x:                 
            x, y, row_height = 0.0, y + row_height + gap, 0.0
        if y > 0 and y + bb.ylen > bed_y:                 
            plates.append(plate)
            plate, x, y, row_height = [], 0.0, 0.0, 0.0
        plate.append(part.translate((x - bb.xmin, y - bb.ymin, -bb.zmin)))
        x += bb.xlen + gap
        row_height = max(row_height, bb.ylen)
    if plate:
        plates.append(plate)
    return plates


def export_kit(p: KitParameters, out_dir) -> dict[str, Path]:
    p.validate()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = make_kit(p)
    files = {}

    for name, part in parts.items():
        if not fits_build_volume(part, p):
            raise ValueError(f"{name} does not fit in the printer's build volume")
        path = out_dir / f"{name}.3mf"
        cq.exporters.export(part, str(path), **EXPORT_TOLERANCE)
        files[name] = path

    for i, plate in enumerate(lay_out(parts, p), start=1):
        kit = cq.Workplane("XY")
        for placed in plate:
            kit = kit.add(placed)
        path = out_dir / f"kit_plate_{i}.3mf"
        cq.exporters.export(kit, str(path), **EXPORT_TOLERANCE)
        files[f"plate_{i}"] = path

    path = out_dir / "kit_assembled.step"
    make_assembly(p, parts).export(str(path))
    files["assembly"] = path

    p.save(out_dir / "params.json")
    files["params"] = out_dir / "params.json"
    return files