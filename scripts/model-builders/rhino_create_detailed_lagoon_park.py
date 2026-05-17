import math

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

from Rhino.Geometry import Box
from Rhino.Geometry import Interval
from Rhino.Geometry import Plane
from Rhino.Geometry import Point3d
from Rhino.Geometry import Vector3d


SCENE_NAME = "DetailedLagoonPark"
PREFIX = "DetailedLagoonPark_20260509"

OX = 180.0
OY = 0.0

LAYERS = {
    "Terrain": (119, 156, 84),
    "UpperTerrace": (132, 116, 86),
    "Water": (74, 151, 175),
    "Paths": (202, 191, 169),
    "Decks": (144, 96, 58),
    "Pavilions": (119, 82, 49),
    "Palms": (58, 113, 61),
    "Trees": (71, 122, 66),
    "Shrubs": (88, 140, 62),
    "Rocks": (147, 140, 128),
    "Boats": (222, 228, 231),
    "Furniture": (90, 90, 90),
}


def layer_name(key):
    return PREFIX + "_" + key


def sp(x, y, z):
    return (OX + x, OY + y, z)


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
    return [value]


def assign(value, key, created):
    ids = as_ids(value)
    name = layer_name(key)
    for obj_id in ids:
        rs.ObjectLayer(obj_id, name)
        rs.ObjectName(obj_id, SCENE_NAME)
        created.append(obj_id)
    return ids


def add_box_area(x0, x1, y0, y1, z0, z1, key, created):
    box = rs.AddBox([
        sp(x0, y0, z0),
        sp(x1, y0, z0),
        sp(x1, y1, z0),
        sp(x0, y1, z0),
        sp(x0, y0, z1),
        sp(x1, y0, z1),
        sp(x1, y1, z1),
        sp(x0, y1, z1),
    ])
    assign(box, key, created)
    return box


def add_closed_planar(points, z, key, created):
    pts = [sp(x, y, z) for x, y in points]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    curve = rs.AddPolyline(pts)
    srfs = rs.AddPlanarSrf(curve)
    rs.DeleteObject(curve)
    assign(srfs, key, created)
    return srfs


def add_segment_box(p0, p1, width, height, z0, key, created):
    x0, y0 = p0
    x1, y1 = p1
    vx = x1 - x0
    vy = y1 - y0
    length = math.sqrt(vx * vx + vy * vy)
    if length < 0.01:
        return None
    ux = vx / length
    uy = vy / length
    xaxis = Vector3d(ux, uy, 0.0)
    yaxis = Vector3d(-uy, ux, 0.0)
    mid = Point3d(OX + (x0 + x1) * 0.5, OY + (y0 + y1) * 0.5, z0)
    plane = Plane(mid, xaxis, yaxis)
    box = Box(
        plane,
        Interval(-length * 0.5, length * 0.5),
        Interval(-width * 0.5, width * 0.5),
        Interval(0.0, height),
    )
    obj_id = sc.doc.Objects.AddBrep(box.ToBrep())
    assign(obj_id, key, created)
    return obj_id


def add_path(points, width, height, z0, key, created):
    for i in range(len(points) - 1):
        add_segment_box(points[i], points[i + 1], width, height, z0, key, created)


def add_pipe_line(start, end, radius, key, created):
    curve = rs.AddLine(start, end)
    pipe = rs.AddPipe(curve, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve)
    assign(pipe, key, created)
    return pipe


def add_pipe_arc(start, mid, end, radius, key, created):
    curve = rs.AddArc3Pt(start, mid, end)
    pipe = rs.AddPipe(curve, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve)
    assign(pipe, key, created)
    return pipe


def add_circle_pipe(center, radius, pipe_radius, key, created):
    curve = rs.AddCircle(center, radius)
    pipe = rs.AddPipe(curve, [0.0, 1.0], [pipe_radius, pipe_radius], cap=2)
    rs.DeleteObject(curve)
    assign(pipe, key, created)
    return pipe


def add_pavilion(cx, cy, base_z, width, depth, roof_z, roof_thickness, created):
    add_box_area(cx - width * 0.5, cx + width * 0.5, cy - depth * 0.5, cy + depth * 0.5, roof_z, roof_z + roof_thickness, "Pavilions", created)
    col_offsets = [
        (-width * 0.42, -depth * 0.42),
        (width * 0.42, -depth * 0.42),
        (-width * 0.42, depth * 0.42),
        (width * 0.42, depth * 0.42),
    ]
    for ox, oy in col_offsets:
        col = rs.AddCylinder(sp(cx + ox, cy + oy, base_z), roof_z - base_z, 0.24, True)
        assign(col, "Pavilions", created)


def add_palm(x, y, base_z, trunk_h, crown_r, created):
    trunk1 = rs.AddCylinder(sp(x, y, base_z), trunk_h * 0.45, 0.28, True)
    trunk2 = rs.AddCylinder(sp(x, y, base_z + trunk_h * 0.45), trunk_h * 0.35, 0.22, True)
    trunk3 = rs.AddCylinder(sp(x, y, base_z + trunk_h * 0.80), trunk_h * 0.20, 0.16, True)
    assign([trunk1, trunk2, trunk3], "Palms", created)

    top = sp(x, y, base_z + trunk_h)
    for i in range(6):
        angle = (2.0 * math.pi * i) / 6.0
        end = sp(x + math.cos(angle) * crown_r, y + math.sin(angle) * crown_r, base_z + trunk_h - 1.6)
        mid = sp(x + math.cos(angle) * crown_r * 0.55, y + math.sin(angle) * crown_r * 0.55, base_z + trunk_h + 1.2)
        add_pipe_arc(top, mid, end, 0.05, "Palms", created)

    crown = rs.AddSphere(sp(x, y, base_z + trunk_h - 0.4), 0.42)
    assign(crown, "Palms", created)


def add_tree(x, y, base_z, trunk_h, crown_r, created):
    trunk = rs.AddCylinder(sp(x, y, base_z), trunk_h, max(0.14, crown_r * 0.10), True)
    assign(trunk, "Trees", created)

    spheres = [
        rs.AddSphere(sp(x, y, base_z + trunk_h + crown_r * 0.40), crown_r),
        rs.AddSphere(sp(x - crown_r * 0.55, y + crown_r * 0.18, base_z + trunk_h + crown_r * 0.10), crown_r * 0.72),
        rs.AddSphere(sp(x + crown_r * 0.60, y - crown_r * 0.10, base_z + trunk_h + crown_r * 0.05), crown_r * 0.68),
    ]
    for obj_id, scale in zip(spheres, [(1.35, 1.0, 0.72), (1.0, 1.15, 0.82), (1.1, 0.95, 0.78)]):
        rs.ScaleObject(obj_id, rs.SurfaceAreaCentroid(obj_id)[0], scale, False)
        assign(obj_id, "Trees", created)


def add_shrub(x, y, z, radius, created):
    shrub = rs.AddSphere(sp(x, y, z + radius * 0.8), radius)
    if shrub:
        rs.ScaleObject(shrub, rs.SurfaceAreaCentroid(shrub)[0], (1.4, 1.0, 0.55), False)
        assign(shrub, "Shrubs", created)


def add_bench(x, y, z, angle_deg, created):
    seat = rs.AddBox([
        sp(x - 0.8, y - 0.22, z + 0.42),
        sp(x + 0.8, y - 0.22, z + 0.42),
        sp(x + 0.8, y + 0.22, z + 0.42),
        sp(x - 0.8, y + 0.22, z + 0.42),
        sp(x - 0.8, y - 0.22, z + 0.52),
        sp(x + 0.8, y - 0.22, z + 0.52),
        sp(x + 0.8, y + 0.22, z + 0.52),
        sp(x - 0.8, y + 0.22, z + 0.52),
    ])
    back = rs.AddBox([
        sp(x - 0.8, y + 0.14, z + 0.52),
        sp(x + 0.8, y + 0.14, z + 0.52),
        sp(x + 0.8, y + 0.24, z + 0.52),
        sp(x - 0.8, y + 0.24, z + 0.52),
        sp(x - 0.8, y + 0.14, z + 1.10),
        sp(x + 0.8, y + 0.14, z + 1.10),
        sp(x + 0.8, y + 0.24, z + 1.10),
        sp(x - 0.8, y + 0.24, z + 1.10),
    ])
    legs = [
        rs.AddCylinder(sp(x - 0.65, y - 0.10, z), 0.42, 0.05, True),
        rs.AddCylinder(sp(x + 0.65, y - 0.10, z), 0.42, 0.05, True),
        rs.AddCylinder(sp(x - 0.65, y + 0.10, z), 0.42, 0.05, True),
        rs.AddCylinder(sp(x + 0.65, y + 0.10, z), 0.42, 0.05, True),
    ]
    ids = [seat, back] + legs
    pivot = sp(x, y, z)
    rs.RotateObjects(ids, pivot, angle_deg, None, False)
    assign(ids, "Furniture", created)


def add_light_pole(x, y, z, height, created):
    pole = rs.AddCylinder(sp(x, y, z), height, 0.06, True)
    lamp = rs.AddSphere(sp(x, y, z + height + 0.18), 0.14)
    assign([pole, lamp], "Furniture", created)


def add_rock_cluster(x, y, z, created):
    cone1 = rs.AddCone(sp(x, y, z), 5.0, 1.8, True)
    cone2 = rs.AddCone(sp(x + 1.4, y - 0.6, z), 3.8, 1.2, True)
    cone3 = rs.AddCone(sp(x - 1.0, y + 0.8, z), 3.2, 1.0, True)
    assign([cone1, cone2, cone3], "Rocks", created)


def add_boat(x, y, z, length, width, created):
    hull = rs.AddBox([
        sp(x - length * 0.5, y - width * 0.5, z),
        sp(x + length * 0.5, y - width * 0.5, z),
        sp(x + length * 0.5, y + width * 0.5, z),
        sp(x - length * 0.5, y + width * 0.5, z),
        sp(x - length * 0.5, y - width * 0.5, z + 0.55),
        sp(x + length * 0.5, y - width * 0.5, z + 0.55),
        sp(x + length * 0.5, y + width * 0.5, z + 0.55),
        sp(x - length * 0.5, y + width * 0.5, z + 0.55),
    ])
    deck = rs.AddBox([
        sp(x - length * 0.22, y - width * 0.28, z + 0.55),
        sp(x + length * 0.22, y - width * 0.28, z + 0.55),
        sp(x + length * 0.22, y + width * 0.28, z + 0.55),
        sp(x - length * 0.22, y + width * 0.28, z + 0.55),
        sp(x - length * 0.22, y - width * 0.28, z + 1.00),
        sp(x + length * 0.22, y - width * 0.28, z + 1.00),
        sp(x + length * 0.22, y + width * 0.28, z + 1.00),
        sp(x - length * 0.22, y + width * 0.28, z + 1.00),
    ])
    assign([hull, deck], "Boats", created)


def build_scene():
    created = []
    ensure_layers()

    add_box_area(-78, 78, -50, 36, -1.2, 0.0, "Terrain", created)
    add_box_area(-78, 78, 24, 32, 0.0, 13.2, "Terrain", created)
    add_box_area(-78, 78, 32, 44, 13.2, 14.3, "UpperTerrace", created)

    lake_pts = [
        (-48, 6), (-40, 18), (-20, 25), (4, 26), (25, 20), (40, 11),
        (50, 0), (42, -13), (23, -22), (2, -26), (-22, -24), (-38, -15), (-49, -3),
    ]
    add_closed_planar(lake_pts, 0.10, "Water", created)

    canal_pts = [(-76, -44), (-60, -42), (-44, -35), (-30, -28), (-19, -22), (-12, -17), (-7, -10)]
    add_path(canal_pts, 5.4, 0.12, 0.08, "Water", created)

    inlet_pts = [(-8, -7), (4, -6), (16, -1), (24, 6)]
    add_path(inlet_pts, 3.8, 0.12, 0.08, "Water", created)

    main_path = [(-8, -38), (3, -28), (12, -18), (22, -6), (33, 8), (46, 22), (58, 34)]
    add_path(main_path, 5.8, 0.16, 0.02, "Paths", created)

    left_path = [(-62, -29), (-49, -27), (-35, -20), (-24, -11), (-15, -2), (-7, 6)]
    add_path(left_path, 5.4, 0.16, 0.02, "Paths", created)

    central_loop = [(-20, -4), (-8, -2), (8, 1), (20, 8), (11, 14), (-2, 11), (-15, 5), (-20, -4)]
    add_path(central_loop, 3.8, 0.14, 0.02, "Paths", created)

    right_garden = [(20, -22), (34, -16), (49, -8), (60, 2), (67, 15)]
    add_path(right_garden, 4.2, 0.15, 0.02, "Paths", created)

    deck_path = [(-74, -36), (-60, -34), (-47, -30), (-35, -23), (-24, -16), (-16, -11)]
    add_path(deck_path, 7.4, 0.28, 0.45, "Decks", created)
    add_path([(-12, -4), (4, -3), (18, 2)], 6.6, 0.28, 0.45, "Decks", created)
    add_path([(8, 3), (18, 6), (28, 10)], 4.2, 0.25, 0.42, "Decks", created)

    add_box_area(-34, -6, -18, -8, 0.32, 0.55, "Decks", created)
    add_box_area(-18, 10, -8, 2, 0.32, 0.55, "Decks", created)
    add_box_area(14, 32, -4, 6, 0.32, 0.55, "Decks", created)

    island = rs.AddCylinder(sp(16, 8, 0.0), 0.55, 6.0, True)
    assign(island, "Decks", created)
    add_circle_pipe(sp(16, 8, 0.58), 6.1, 0.08, "Decks", created)

    add_pavilion(-55, 36, 14.3, 28.0, 9.5, 18.4, 0.45, created)
    add_pavilion(-8, 38, 14.3, 18.0, 8.5, 18.8, 0.45, created)
    add_pavilion(41, 38, 14.3, 24.0, 9.0, 18.6, 0.45, created)
    add_pavilion(70, 36, 14.3, 18.0, 8.5, 17.9, 0.45, created)

    add_pavilion(-24, -12, 0.55, 22.0, 10.0, 5.2, 0.36, created)
    add_pavilion(-1, -6, 0.55, 18.0, 8.0, 5.5, 0.36, created)

    rail_points = [(-70, 33), (-50, 33), (-26, 34), (-4, 35), (18, 35), (42, 35), (68, 33)]
    for i in range(len(rail_points) - 1):
        add_pipe_line(sp(rail_points[i][0], rail_points[i][1], 15.2), sp(rail_points[i + 1][0], rail_points[i + 1][1], 15.2), 0.05, "Furniture", created)

    upper_palms = [(-69, 41, 14.3, 10.0, 4.4), (-48, 42, 14.3, 8.8, 4.0), (-18, 43, 14.3, 9.5, 4.4),
                   (10, 41, 14.3, 8.0, 3.7), (40, 43, 14.3, 10.5, 4.8), (60, 41, 14.3, 8.6, 4.0)]
    lower_palms = [(-54, -33, 0.0, 8.5, 3.8), (-36, -28, 0.0, 7.5, 3.4), (-8, -24, 0.0, 7.8, 3.6),
                   (6, -18, 0.0, 8.0, 3.7), (20, -27, 0.0, 8.2, 3.9), (32, -16, 0.0, 7.4, 3.2),
                   (42, -30, 0.0, 7.8, 3.5), (52, -20, 0.0, 8.3, 3.8), (8, 14, 0.0, 7.0, 3.2)]
    for data in upper_palms + lower_palms:
        add_palm(data[0], data[1], data[2], data[3], data[4], created)

    trees = [
        (-64, 20, 0.0, 5.5, 3.4), (-56, 13, 0.0, 4.5, 2.9), (-49, 8, 0.0, 4.2, 2.8),
        (-39, 5, 0.0, 4.6, 3.1), (-28, 8, 0.0, 5.0, 3.6), (-15, 18, 0.0, 6.0, 4.0),
        (-2, 21, 0.0, 5.4, 3.8), (16, 20, 0.0, 5.6, 4.2), (30, 15, 0.0, 5.0, 3.6),
        (40, 9, 0.0, 4.8, 3.5), (52, 6, 0.0, 4.2, 3.0), (60, -4, 0.0, 5.8, 4.6),
        (58, 17, 0.0, 5.4, 4.0), (44, 24, 0.0, 5.0, 3.8), (26, 27, 0.0, 4.6, 3.4),
        (6, 29, 0.0, 4.2, 3.1), (-20, 29, 0.0, 4.9, 3.5), (-42, 28, 0.0, 4.8, 3.3),
        (67, -18, 0.0, 4.2, 3.0), (58, -26, 0.0, 4.6, 3.3),
    ]
    for data in trees:
        add_tree(data[0], data[1], data[2], data[3], data[4], created)

    shrubs = [
        (-70, -39, 0.0, 1.0), (-60, -35, 0.0, 1.1), (-47, -31, 0.0, 0.9), (-30, -25, 0.0, 1.2),
        (-10, -30, 0.0, 1.1), (10, -31, 0.0, 1.0), (26, -24, 0.0, 1.0), (40, -23, 0.0, 1.0),
        (54, -27, 0.0, 1.1), (66, -12, 0.0, 0.9), (58, 5, 0.0, 1.0), (46, 13, 0.0, 1.1),
        (27, 17, 0.0, 1.0), (4, 18, 0.0, 1.1), (-18, 16, 0.0, 1.0), (-38, 14, 0.0, 1.0),
        (-53, 23, 0.0, 1.1), (18, 30, 0.0, 1.2), (-4, 31, 0.0, 1.0),
    ]
    for data in shrubs:
        add_shrub(data[0], data[1], data[2], data[3], created)

    add_rock_cluster(63, 4, 0.0, created)

    add_boat(-5, 1, 0.24, 7.5, 2.4, created)
    add_boat(6, -5, 0.24, 4.8, 1.8, created)

    for bench in [(-32, -10, 0.0, 22), (6, -20, 0.0, 10), (36, -12, 0.0, 38), (51, 11, 0.0, -30), (-12, 12, 0.0, 12)]:
        add_bench(bench[0], bench[1], bench[2], bench[3], created)

    for pole in [(-20, -6, 0.0, 4.5), (14, -10, 0.0, 4.8), (40, -6, 0.0, 5.2), (60, 10, 0.0, 5.0), (-48, -24, 0.0, 4.5)]:
        add_light_pole(pole[0], pole[1], pole[2], pole[3], created)

    rs.UnselectAllObjects()
    if created:
        rs.SelectObjects(created)

    rs.EnableRedraw(True)
    rs.Redraw()


rs.EnableRedraw(False)
build_scene()
