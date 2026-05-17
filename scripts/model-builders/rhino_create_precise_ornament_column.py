import math
import traceback

import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System


SCENE_NAME = "OrnamentColumnPrecise"
PREFIX = "OrnamentColumnPrecise_20260509"
LOG_PATH = r"C:\Users\Admin\AppData\Local\RhinoMCP\ornament_column_precise_error.log"

OX = 1180.0
OY = -160.0

LAYERS = {
    "Base": (194, 176, 146),
    "Shaft": (206, 190, 162),
    "Frieze": (182, 161, 126),
    "Capital": (214, 198, 168),
    "Abacus": (201, 184, 154),
    "Bracket": (193, 173, 141),
    "Pendants": (175, 153, 122),
}


def layer_name(key):
    return PREFIX + "_" + key


def wp(x, y, z):
    return rg.Point3d(OX + x, OY + y, z)


def ensure_layers():
    for key, color in LAYERS.items():
        name = layer_name(key)
        if not rs.IsLayer(name):
            rs.AddLayer(name, color)
        rs.LayerColor(name, color)
        objs = rs.ObjectsByLayer(name, True) or []
        if objs:
            rs.DeleteObjects(objs)


def as_ids(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def assign(value, key, created):
    ids = as_ids(value)
    target = layer_name(key)
    for obj_id in ids:
        rs.ObjectLayer(obj_id, target)
        rs.ObjectName(obj_id, SCENE_NAME)
        created.append(obj_id)
    return ids


def add_brep(brep, key, created):
    if brep is None:
        return None
    obj_id = sc.doc.Objects.AddBrep(brep)
    if obj_id == System.Guid.Empty:
        return None
    assign(obj_id, key, created)
    return obj_id


def box_brep(x0, x1, y0, y1, z0, z1):
    return rg.Box(
        rg.Plane.WorldXY,
        rg.Interval(OX + x0, OX + x1),
        rg.Interval(OY + y0, OY + y1),
        rg.Interval(z0, z1),
    ).ToBrep()


def cylinder_brep(radius, z0, z1, x=0.0, y=0.0):
    circle = rg.Circle(rg.Plane(wp(x, y, z0), rg.Vector3d.ZAxis), radius)
    return rg.Cylinder(circle, z1 - z0).ToBrep(True, True)


def loft_brep(specs, x=0.0, y=0.0):
    tol = sc.doc.ModelAbsoluteTolerance
    curves = []
    for z, radius in specs:
        curves.append(rg.Circle(rg.Plane(wp(x, y, z), rg.Vector3d.ZAxis), radius).ToNurbsCurve())
    lofts = rg.Brep.CreateFromLoft(curves, rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, False)
    if not lofts:
        return None
    capped = lofts[0].CapPlanarHoles(tol)
    return capped if capped else lofts[0]


def torus_brep(major_radius, minor_radius, z, x=0.0, y=0.0):
    return rg.Torus(rg.Plane(wp(x, y, z), rg.Vector3d.ZAxis), major_radius, minor_radius).ToBrep()


def add_curve_pipe(curve, radius, key, created):
    curve_id = sc.doc.Objects.AddCurve(curve)
    if curve_id == System.Guid.Empty:
        return []
    pipe = rs.AddPipe(curve_id, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve_id)
    return assign(pipe, key, created)


def add_pipe_points(points, radius, key, created):
    curve = rg.Curve.CreateInterpolatedCurve(points, 3)
    return add_curve_pipe(curve, radius, key, created)


def extrude_closed_curve(curve, distance):
    if curve is None:
        return None
    extr = rg.Extrusion.Create(curve, distance, True)
    if extr is None:
        return None
    brep = extr.ToBrep()
    move = rg.Transform.Translation(0.0, -distance * 0.5, 0.0)
    brep.Transform(move)
    return brep


def leaf_brep(radius, z0, height, width, relief):
    direction = 1.0 if height >= 0.0 else -1.0
    h = abs(height)
    pts = [
        wp(radius - relief * 0.12, 0.0, z0),
        wp(radius + relief * 0.22, 0.0, z0 + direction * h * 0.12),
        wp(radius + relief * 0.48, 0.0, z0 + direction * h * 0.32),
        wp(radius + relief * 0.58, 0.0, z0 + direction * h * 0.54),
        wp(radius + relief * 0.30, 0.0, z0 + direction * h * 0.82),
        wp(radius, 0.0, z0 + direction * h),
        wp(radius - relief * 0.30, 0.0, z0 + direction * h * 0.82),
        wp(radius - relief * 0.58, 0.0, z0 + direction * h * 0.54),
        wp(radius - relief * 0.48, 0.0, z0 + direction * h * 0.32),
        wp(radius - relief * 0.22, 0.0, z0 + direction * h * 0.12),
    ]
    curve = rg.PolylineCurve(pts + [pts[0]])
    return extrude_closed_curve(curve, width)


def duplicate_ring(seed_ids, key, created, count):
    center = wp(0.0, 0.0, 0.0)
    for i in range(1, count):
        angle = 360.0 * float(i) / float(count)
        new_ids = []
        for seed in seed_ids:
            new_id = rs.CopyObject(seed)
            if new_id:
                rs.RotateObject(new_id, center, angle)
                new_ids.append(new_id)
        if new_ids:
            assign(new_ids, key, created)


def add_leaf_ring(radius, z0, height, width, relief, count, key, created):
    leaf = leaf_brep(radius, z0, height, width, relief)
    if leaf is None:
        return
    seed = add_brep(leaf, key, created)
    if seed:
        duplicate_ring([seed], key, created, count)


def add_ring_beads(radius, z, count, bead_radius, key, created):
    for i in range(count):
        ang = (2.0 * math.pi * i) / float(count)
        x = math.cos(ang) * radius
        y = math.sin(ang) * radius
        sphere = rg.Sphere(wp(x, y, z), bead_radius).ToBrep()
        add_brep(sphere, key, created)


def add_dentil_ring(radius, z0, height, depth, width, count, key, created):
    for i in range(count):
        ang = (2.0 * math.pi * i) / float(count)
        cx = math.cos(ang) * (radius + depth * 0.5)
        cy = math.sin(ang) * (radius + depth * 0.5)
        plane = rg.Plane(
            wp(cx, cy, z0),
            rg.Vector3d(math.cos(ang), math.sin(ang), 0.0),
            rg.Vector3d(-math.sin(ang), math.cos(ang), 0.0),
        )
        box = rg.Box(
            plane,
            rg.Interval(-depth * 0.5, depth * 0.5),
            rg.Interval(-width * 0.5, width * 0.5),
            rg.Interval(0.0, height),
        )
        add_brep(box.ToBrep(), key, created)


def shaft_with_channels(radius, z0, z1, channel_depth, channel_width, count):
    tol = sc.doc.ModelAbsoluteTolerance
    shaft = cylinder_brep(radius, z0, z1)
    cutter0 = box_brep(radius - channel_depth, radius + 0.7, -channel_width * 0.5, channel_width * 0.5, z0 - 0.3, z1 + 0.3)
    cutters = []
    for i in range(count):
        cutter = cutter0.DuplicateBrep()
        cutter.Transform(rg.Transform.Rotation(math.radians(360.0 * float(i) / float(count)), rg.Vector3d.ZAxis, wp(0.0, 0.0, 0.0)))
        cutters.append(cutter)
    result = rg.Brep.CreateBooleanDifference([shaft], cutters, tol)
    if result and len(result) > 0:
        return result[0]
    return shaft


def add_scroll_ring(radius, z0, z1, count, key, created):
    z_mid = (z0 + z1) * 0.5
    seed_ids = []
    left = [
        wp(radius + 0.10, -0.85, z0 + 0.35),
        wp(radius + 0.24, -0.50, z_mid + 0.78),
        wp(radius + 0.38, -0.70, z_mid + 1.10),
        wp(radius + 0.18, -0.92, z_mid + 0.60),
        wp(radius + 0.06, -0.60, z_mid + 0.20),
        wp(radius + 0.16, -0.24, z_mid + 0.48),
    ]
    right = [
        wp(radius + 0.10, 0.85, z0 + 0.35),
        wp(radius + 0.24, 0.50, z_mid + 0.78),
        wp(radius + 0.38, 0.70, z_mid + 1.10),
        wp(radius + 0.18, 0.92, z_mid + 0.60),
        wp(radius + 0.06, 0.60, z_mid + 0.20),
        wp(radius + 0.16, 0.24, z_mid + 0.48),
    ]
    seed_ids.extend(add_pipe_points(left, 0.09, key, created))
    seed_ids.extend(add_pipe_points(right, 0.09, key, created))
    bridge = [
        wp(radius + 0.08, -0.35, z_mid - 0.10),
        wp(radius + 0.12, 0.00, z_mid + 0.18),
        wp(radius + 0.08, 0.35, z_mid - 0.10),
    ]
    seed_ids.extend(add_pipe_points(bridge, 0.07, key, created))
    bead = add_brep(rg.Sphere(wp(radius + 0.18, 0.0, z_mid + 0.74), 0.12).ToBrep(), key, created)
    if bead:
        seed_ids.append(bead)
    if seed_ids:
        duplicate_ring(seed_ids, key, created, count)


def add_small_tabs(radius, z0, z1, count, width, depth, key, created):
    for i in range(count):
        ang = (2.0 * math.pi * i) / float(count)
        plane = rg.Plane(
            wp(math.cos(ang) * (radius + depth * 0.5), math.sin(ang) * (radius + depth * 0.5), z0),
            rg.Vector3d(math.cos(ang), math.sin(ang), 0.0),
            rg.Vector3d(-math.sin(ang), math.cos(ang), 0.0),
        )
        tab = rg.Box(
            plane,
            rg.Interval(-depth * 0.5, depth * 0.5),
            rg.Interval(-width * 0.5, width * 0.5),
            rg.Interval(0.0, z1 - z0),
        )
        add_brep(tab.ToBrep(), key, created)


def add_side_arches(created):
    post_specs = [
        (2.15, 0.0),
        (-2.15, 0.0),
        (0.0, 2.15),
        (0.0, -2.15),
    ]
    for x, y in post_specs:
        add_brep(cylinder_brep(0.22, 6.2, 9.0, x, y), "Base", created)
        add_brep(loft_brep([(9.0, 0.18), (9.6, 0.34), (10.2, 0.14)], x, y), "Base", created)
    front_arch = [
        wp(-1.55, 2.15, 8.05),
        wp(-0.55, 2.15, 9.05),
        wp(0.55, 2.15, 9.05),
        wp(1.55, 2.15, 8.05),
    ]
    side_arch = [
        wp(2.15, -1.55, 8.05),
        wp(2.15, -0.55, 9.05),
        wp(2.15, 0.55, 9.05),
        wp(2.15, 1.55, 8.05),
    ]
    seed_ids = []
    seed_ids.extend(add_pipe_points(front_arch, 0.10, "Base", created))
    seed_ids.extend(add_pipe_points(side_arch, 0.10, "Base", created))
    if seed_ids:
        duplicate_ring(seed_ids, "Base", created, 4)


def add_pendant(x, y, top_z, length, scale, key, created):
    specs = [
        (top_z - length, 0.05 * scale),
        (top_z - length * 0.78, 0.16 * scale),
        (top_z - length * 0.56, 0.34 * scale),
        (top_z - length * 0.36, 0.22 * scale),
        (top_z - length * 0.16, 0.28 * scale),
        (top_z, 0.10 * scale),
    ]
    add_brep(loft_brep(specs, x, y), key, created)


def add_cup(x, y, z, scale, key, created):
    add_brep(loft_brep([
        (z, 0.08 * scale),
        (z + 0.30 * scale, 0.58 * scale),
        (z + 0.72 * scale, 1.00 * scale),
        (z + 1.02 * scale, 0.82 * scale),
        (z + 1.30 * scale, 0.34 * scale),
    ], x, y), key, created)
    add_brep(cylinder_brep(0.10 * scale, z + 1.30 * scale, z + 1.52 * scale, x, y), key, created)


def add_bracket_arm(axis, sign, created, scale=1.0):
    if axis == "x":
        points = [
            wp(sign * 3.35, 0.0, 131.8),
            wp(sign * 4.35, 0.0, 136.0),
            wp(sign * 6.20, 0.0, 135.6),
            wp(sign * 6.90, 0.0, 131.0),
        ]
        cup_x = sign * 7.85
        cup_y = 0.0
        cup_scale = 1.12 * scale
        pendant_scale = 1.00 * scale
    else:
        points = [
            wp(0.0, sign * 2.95, 131.8),
            wp(0.0, sign * 3.95, 135.2),
            wp(0.0, sign * 5.45, 134.9),
            wp(0.0, sign * 5.95, 130.9),
        ]
        cup_x = 0.0
        cup_y = sign * 6.75
        cup_scale = 0.92 * scale
        pendant_scale = 0.82 * scale
    add_pipe_points(points, 0.42 * scale, "Bracket", created)
    add_cup(cup_x, cup_y, 128.6, cup_scale, "Bracket", created)
    add_pendant(cup_x, cup_y, 128.6, 8.6 * pendant_scale, pendant_scale, "Pendants", created)


def build_base(created):
    add_brep(loft_brep([(0.0, 4.35), (1.1, 4.85), (2.6, 4.55), (4.0, 4.08)]), "Base", created)
    add_leaf_ring(3.50, 0.26, 2.60, 0.82, 0.58, 18, "Base", created)
    add_brep(cylinder_brep(3.72, 4.0, 5.2), "Base", created)
    add_brep(torus_brep(3.32, 0.30, 4.6), "Base", created)
    add_brep(box_brep(-2.95, 2.95, -2.95, 2.95, 5.2, 11.4), "Base", created)
    add_side_arches(created)
    add_brep(loft_brep([(11.4, 2.62), (12.7, 3.18), (14.5, 3.08), (16.1, 2.34)]), "Base", created)
    add_brep(torus_brep(2.58, 0.18, 15.6), "Base", created)


def build_shaft(created):
    add_brep(loft_brep([(16.1, 2.30), (17.8, 2.08)]), "Shaft", created)
    shaft = shaft_with_channels(2.00, 17.8, 54.5, 0.14, 0.34, 4)
    add_brep(shaft, "Shaft", created)
    add_brep(cylinder_brep(2.12, 54.5, 56.1), "Shaft", created)
    add_small_tabs(2.02, 47.8, 51.4, 4, 0.95, 0.24, "Shaft", created)
    add_brep(cylinder_brep(2.22, 51.4, 53.0), "Shaft", created)
    add_ring_beads(2.08, 52.2, 12, 0.14, "Shaft", created)


def build_frieze(created):
    add_brep(cylinder_brep(2.56, 56.1, 63.7), "Frieze", created)
    add_brep(torus_brep(2.42, 0.14, 56.6), "Frieze", created)
    add_brep(torus_brep(2.42, 0.14, 63.2), "Frieze", created)
    add_ring_beads(2.46, 57.3, 24, 0.11, "Frieze", created)
    add_ring_beads(2.46, 62.4, 24, 0.11, "Frieze", created)
    add_scroll_ring(2.62, 57.8, 62.1, 10, "Frieze", created)


def build_capital(created):
    add_brep(loft_brep([(63.7, 2.28), (65.0, 2.62), (66.0, 2.76)]), "Capital", created)
    add_ring_beads(2.42, 64.6, 22, 0.11, "Capital", created)
    add_brep(torus_brep(2.36, 0.12, 65.2), "Capital", created)
    add_leaf_ring(2.34, 66.0, 12.6, 0.98, 0.86, 16, "Capital", created)
    add_brep(torus_brep(2.42, 0.12, 78.0), "Capital", created)
    add_brep(loft_brep([(78.0, 2.54), (80.5, 2.98), (83.1, 3.36), (85.9, 3.26), (88.4, 2.72)]), "Capital", created)
    add_ring_beads(2.90, 82.0, 30, 0.10, "Capital", created)
    add_dentil_ring(2.48, 76.2, 1.0, 0.34, 0.42, 20, "Capital", created)
    add_brep(loft_brep([(88.4, 2.26), (90.1, 2.74), (92.0, 2.18)]), "Capital", created)


def build_abacus(created):
    add_brep(loft_brep([(92.0, 1.05), (94.1, 2.30), (96.1, 3.05), (97.3, 2.68)]), "Abacus", created)
    add_leaf_ring(3.54, 97.3, -3.8, 1.14, 0.56, 14, "Abacus", created)
    add_brep(box_brep(-5.08, 5.08, -5.08, 5.08, 97.3, 100.9), "Abacus", created)
    add_brep(cylinder_brep(1.62, 100.9, 103.4), "Abacus", created)
    add_brep(loft_brep([(103.4, 1.62), (105.2, 2.46), (107.2, 1.42)]), "Abacus", created)


def build_bracket(created):
    add_brep(box_brep(-5.35, 5.35, -4.30, 4.30, 109.4, 112.9), "Bracket", created)
    add_leaf_ring(3.86, 109.4, -2.6, 1.16, 0.46, 12, "Bracket", created)
    add_brep(box_brep(-4.10, 4.10, -3.20, 3.20, 122.4, 137.6), "Bracket", created)
    add_brep(box_brep(-4.95, 4.95, -3.95, 3.95, 137.6, 141.3), "Bracket", created)
    add_brep(box_brep(-3.64, 3.64, -2.88, 2.88, 141.3, 143.1), "Bracket", created)
    add_brep(loft_brep([(112.9, 1.04), (115.2, 1.58), (117.2, 2.08)]), "Bracket", created)
    add_cup(0.0, 0.0, 118.8, 0.96, "Bracket", created)
    add_pendant(0.0, 0.0, 118.7, 6.1, 0.82, "Pendants", created)
    for sign in (-1.0, 1.0):
        add_bracket_arm("x", sign, created, 1.0)
        add_bracket_arm("y", sign, created, 0.92)


def main():
    ensure_layers()
    created = []
    build_base(created)
    build_shaft(created)
    build_frieze(created)
    build_capital(created)
    build_abacus(created)
    build_bracket(created)
    rs.SelectObjects(created)
    sc.doc.Views.Redraw()


try:
    main()
except Exception:
    with open(LOG_PATH, "w") as handle:
        handle.write(traceback.format_exc())
    raise
