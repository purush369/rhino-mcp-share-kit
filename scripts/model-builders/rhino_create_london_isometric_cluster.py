import math
import traceback

import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System


SCENE_NAME = "LondonIsometricCluster"
PREFIX = "LondonIsometricCluster_20260509"
LOG_PATH = r"C:\Users\Admin\AppData\Local\RhinoMCP\london_isometric_cluster_error.log"

OX = 1580.0
OY = 220.0

LAYERS = {
    "Site": (216, 202, 182),
    "River": (95, 191, 224),
    "Roads": (181, 166, 151),
    "Bridge": (167, 144, 118),
    "Parliament": (183, 152, 103),
    "BigBen": (201, 166, 88),
    "Eye": (131, 176, 191),
    "Skyscrapers": (91, 157, 188),
    "Buildings": (165, 145, 120),
    "Roofs": (209, 111, 95),
    "Vehicles": (214, 63, 57),
    "Boats": (242, 244, 245),
    "Landscape": (133, 174, 114),
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


def add_curve_pipe(curve, radius, key, created):
    curve_id = sc.doc.Objects.AddCurve(curve)
    if curve_id == System.Guid.Empty:
        return []
    pipe = rs.AddPipe(curve_id, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve_id)
    return assign(pipe, key, created)


def box_brep(x0, x1, y0, y1, z0, z1):
    return rg.Box(
        rg.Plane.WorldXY,
        rg.Interval(OX + x0, OX + x1),
        rg.Interval(OY + y0, OY + y1),
        rg.Interval(z0, z1),
    ).ToBrep()


def loft_circles(specs, x=0.0, y=0.0):
    tol = sc.doc.ModelAbsoluteTolerance
    curves = []
    for z, rx, ry in specs:
        ellipse = rg.Ellipse(rg.Plane(wp(x, y, z), rg.Vector3d.ZAxis), rx, ry)
        curves.append(ellipse.ToNurbsCurve())
    lofts = rg.Brep.CreateFromLoft(curves, rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, False)
    if not lofts:
        return None
    capped = lofts[0].CapPlanarHoles(tol)
    return capped if capped else lofts[0]


def extrude_poly(points, z, height):
    poly = [wp(x, y, z) for x, y in points]
    if poly[0] != poly[-1]:
        poly.append(poly[0])
    curve = rg.PolylineCurve(poly)
    extr = rg.Extrusion.Create(curve, height, True)
    return extr.ToBrep() if extr else None


def add_poly(points, z, height, key, created):
    return add_brep(extrude_poly(points, z, height), key, created)


def tapered_poly(points0, z0, points1, z1):
    curves = []
    for points, z in ((points0, z0), (points1, z1)):
        poly = [wp(x, y, z) for x, y in points]
        if poly[0] != poly[-1]:
            poly.append(poly[0])
        curves.append(rg.PolylineCurve(poly))
    lofts = rg.Brep.CreateFromLoft(curves, rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Straight, False)
    if not lofts:
        return None
    capped = lofts[0].CapPlanarHoles(sc.doc.ModelAbsoluteTolerance)
    return capped if capped else lofts[0]


def add_cylinder(radius, z0, z1, x=0.0, y=0.0, key=None, created=None):
    circle = rg.Circle(rg.Plane(wp(x, y, z0), rg.Vector3d.ZAxis), radius)
    brep = rg.Cylinder(circle, z1 - z0).ToBrep(True, True)
    if key and created is not None:
        return add_brep(brep, key, created)
    return brep


def transform_brep(brep, xform):
    copy = brep.DuplicateBrep()
    copy.Transform(xform)
    return copy


def rotate_xy(x, y, deg):
    ang = math.radians(deg)
    return (
        x * math.cos(ang) - y * math.sin(ang),
        x * math.sin(ang) + y * math.cos(ang),
    )


def add_segment_box(p0, p1, width, z0, z1, key, created):
    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.01:
        return None
    ux = dx / length
    uy = dy / length
    plane = rg.Plane(
        wp((x0 + x1) * 0.5, (y0 + y1) * 0.5, z0),
        rg.Vector3d(ux, uy, 0.0),
        rg.Vector3d(-uy, ux, 0.0),
    )
    box = rg.Box(
        plane,
        rg.Interval(-length * 0.5, length * 0.5),
        rg.Interval(-width * 0.5, width * 0.5),
        rg.Interval(0.0, z1 - z0),
    )
    return add_brep(box.ToBrep(), key, created)


def arch_curve(x0, x1, y, z0, rise):
    xm = (x0 + x1) * 0.5
    pts = [wp(x0, y, z0), wp(xm, y, z0 + rise), wp(x1, y, z0)]
    return rg.Curve.CreateInterpolatedCurve(pts, 3)


def add_barrel_roof(x0, x1, y0, y1, z0, rise, key, created):
    c0 = arch_curve(x0, x1, y0, z0, rise)
    c1 = arch_curve(x0, x1, y1, z0, rise)
    lofts = rg.Brep.CreateFromLoft([c0, c1], rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, False)
    if not lofts:
        return None
    sides = []
    for y in (y0, y1):
        pts = [wp(x0, y, z0), wp((x0 + x1) * 0.5, y, z0 + rise), wp(x1, y, z0)]
        poly = rg.PolylineCurve(pts + [pts[0]])
        breps = rg.Brep.CreatePlanarBreps(poly, sc.doc.ModelAbsoluteTolerance)
        if breps:
            sides.extend(list(breps))
    joined = rg.Brep.JoinBreps([lofts[0]] + sides, sc.doc.ModelAbsoluteTolerance)
    return add_brep(joined[0] if joined else lofts[0], key, created)


def add_facade_grid_x(x0, x1, y, z0, z1, nx, nz, outward, key, created, depth=0.09, mullion=0.05):
    if outward >= 0.0:
        fy0, fy1 = y, y + depth
    else:
        fy0, fy1 = y - depth, y
    step_x = float(x1 - x0) / float(nx)
    for i in range(nx + 1):
        x = x0 + step_x * i
        add_brep(box_brep(x - mullion, x + mullion, fy0, fy1, z0, z1), key, created)
    step_z = float(z1 - z0) / float(nz)
    for j in range(1, nz):
        z = z0 + step_z * j
        add_brep(box_brep(x0, x1, fy0, fy1, z - mullion, z + mullion), key, created)


def add_facade_grid_y(x, y0, y1, z0, z1, ny, nz, outward, key, created, depth=0.09, mullion=0.05):
    if outward >= 0.0:
        fx0, fx1 = x, x + depth
    else:
        fx0, fx1 = x - depth, x
    step_y = float(y1 - y0) / float(ny)
    for i in range(ny + 1):
        y = y0 + step_y * i
        add_brep(box_brep(fx0, fx1, y - mullion, y + mullion, z0, z1), key, created)
    step_z = float(z1 - z0) / float(nz)
    for j in range(1, nz):
        z = z0 + step_z * j
        add_brep(box_brep(fx0, fx1, y0, y1, z - mullion, z + mullion), key, created)


def add_context_building(x0, y0, width, depth, height, created, roof_mode="setback", grid=(4, 5)):
    x1 = x0 + width
    y1 = y0 + depth
    add_brep(box_brep(x0, x1, y0, y1, 0.94, height), "Buildings", created)
    add_facade_grid_x(x0, x1, y0, 1.2, height - 0.4, grid[0], grid[1], -1.0, "Buildings", created)
    add_facade_grid_x(x0, x1, y1, 1.2, height - 0.4, grid[0], grid[1], 1.0, "Buildings", created)
    add_facade_grid_y(x0, y0, y1, 1.2, height - 0.4, grid[0], grid[1], -1.0, "Buildings", created)
    add_facade_grid_y(x1, y0, y1, 1.2, height - 0.4, grid[0], grid[1], 1.0, "Buildings", created)
    if roof_mode == "setback":
        add_brep(box_brep(x0 + 0.16, x1 - 0.16, y0 + 0.16, y1 - 0.16, height, height + 0.86), "Roofs", created)
    elif roof_mode == "crown":
        add_brep(box_brep(x0 - 0.06, x1 + 0.06, y0 - 0.06, y1 + 0.06, height, height + 0.44), "Roofs", created)
        add_brep(box_brep(x0 + width * 0.18, x1 - width * 0.18, y0 + depth * 0.18, y1 - depth * 0.18, height + 0.44, height + 1.2), "Roofs", created)


def add_merlon_row(x0, x1, y0, y1, z0, count, key, created):
    span = float(x1 - x0) / float(count)
    for i in range(count):
        xa = x0 + span * i + span * 0.18
        xb = x0 + span * i + span * 0.82
        add_brep(box_brep(xa, xb, y0, y1, z0, z0 + 0.72), key, created)


def add_tree(x, y, scale, created):
    add_cylinder(0.14 * scale, 0.6, 2.9 * scale + 0.6, x, y, "Landscape", created)
    crown = loft_circles([
        (2.8 * scale + 0.6, 0.7 * scale, 0.7 * scale),
        (3.5 * scale + 0.6, 1.25 * scale, 1.15 * scale),
        (4.4 * scale + 0.6, 0.95 * scale, 0.95 * scale),
    ], x, y)
    add_brep(crown, "Landscape", created)


def add_bus(x, y, length, heading_deg, created):
    body = box_brep(-length * 0.5, length * 0.5, -0.52, 0.52, 0.9, 2.1)
    roof = box_brep(-length * 0.42, length * 0.42, -0.40, 0.40, 2.1, 2.9)
    xform = rg.Transform.Rotation(math.radians(heading_deg), rg.Vector3d.ZAxis, wp(0.0, 0.0, 0.0))
    shift = rg.Transform.Translation(x, y, 0.0)
    for geom in (body, roof):
        geom.Transform(xform)
        geom.Transform(shift)
        add_brep(geom, "Vehicles", created)


def add_boat(x, y, scale, created):
    hull = loft_circles([
        (0.65, 1.4 * scale, 0.46 * scale),
        (1.15, 1.15 * scale, 0.42 * scale),
        (1.55, 0.75 * scale, 0.22 * scale),
    ], x, y)
    add_brep(hull, "Boats", created)
    cabin = box_brep(-0.34 * scale, 0.34 * scale, -0.18 * scale, 0.18 * scale, 1.55, 2.05)
    cabin.Transform(rg.Transform.Translation(x, y, 0.0))
    add_brep(cabin, "Boats", created)


def build_site(created):
    site_pts = [(-54, -26), (-20, -30), (6, -28), (32, -20), (54, -6), (56, 30), (-54, 28)]
    add_poly(site_pts, 0.0, 0.8, "Site", created)
    river_pts = [(-54, 4), (-40, 8), (-24, 11), (-8, 14), (10, 15), (28, 13), (48, 9), (56, 7), (56, 18), (-54, 18)]
    add_poly(river_pts, 0.82, 0.12, "River", created)
    quay_north = [(-54, 18), (56, 18), (56, 22), (-54, 24)]
    quay_south = [(-54, 2), (56, 5), (56, 1), (-54, -2)]
    add_poly(quay_north, 0.82, 0.18, "Roads", created)
    add_poly(quay_south, 0.82, 0.18, "Roads", created)
    add_poly([(-44, -18), (-10, -18), (-10, -7), (-44, -7)], 0.82, 0.12, "Roads", created)
    add_poly([(10, -18), (40, -18), (40, -8), (10, -8)], 0.82, 0.12, "Roads", created)
    add_poly([(-7, -4), (6, -4), (6, 2), (-7, 2)], 0.82, 0.12, "Roads", created)
    for x, y in [(-50, 24), (-39, 24), (-28, 23), (20, -22), (35, -16), (44, 22)]:
        add_tree(x, y, 0.92, created)


def build_parliament(created):
    add_brep(box_brep(-49.8, -23.4, -5.2, 4.1, 0.94, 8.9), "Parliament", created)
    add_facade_grid_x(-49.8, -23.4, 4.1, 1.1, 8.5, 18, 5, 1.0, "Parliament", created, depth=0.12, mullion=0.035)
    add_facade_grid_x(-49.8, -23.4, -5.2, 1.1, 8.5, 18, 5, -1.0, "Parliament", created, depth=0.10, mullion=0.03)
    add_brep(box_brep(-49.4, -23.8, -5.6, 4.5, 8.9, 10.1), "Roofs", created)
    add_merlon_row(-49.2, -24.0, 4.2, 4.85, 10.1, 20, "Parliament", created)
    add_merlon_row(-49.2, -24.0, -5.95, -5.3, 10.1, 20, "Parliament", created)
    for x in [-47.7, -45.0, -42.3, -39.6, -36.9, -34.2, -31.5, -28.8, -26.1]:
        add_brep(box_brep(x - 0.24, x + 0.24, -5.8, 4.7, 0.94, 11.8), "Parliament", created)
        add_brep(box_brep(x - 0.48, x + 0.48, -5.95, 4.85, 11.8, 12.55), "Parliament", created)
        spire = loft_circles([(12.55, 0.24, 0.24), (14.3, 0.11, 0.11), (15.8, 0.02, 0.02)], x, -0.4)
        add_brep(spire, "Parliament", created)
    hall = tapered_poly(
        [(-46.6, -8.4), (-28.3, -8.4), (-28.8, -5.8), (-46.1, -5.8)],
        1.0,
        [(-45.4, -7.2), (-29.4, -7.2), (-29.8, -6.1), (-45.1, -6.1)],
        8.2,
    )
    add_brep(hall, "Parliament", created)
    add_brep(box_brep(-45.8, -29.0, -8.0, -6.0, 8.2, 10.9), "Roofs", created)
    tower = box_brep(-20.2, -16.4, -2.1, 2.1, 0.94, 35.6)
    add_brep(tower, "BigBen", created)
    add_facade_grid_x(-20.2, -16.4, 2.1, 1.0, 34.8, 4, 10, 1.0, "BigBen", created, depth=0.08, mullion=0.03)
    add_facade_grid_x(-20.2, -16.4, -2.1, 1.0, 34.8, 4, 10, -1.0, "BigBen", created, depth=0.08, mullion=0.03)
    for z in [18.0, 22.0, 26.0, 30.0]:
        add_brep(box_brep(-20.8, -15.8, -2.7, 2.7, z, z + 0.72), "BigBen", created)
    for y in (-2.35, 2.35):
        add_cylinder(0.72, 27.9, 28.2, -18.3, y, "BigBen", created)
    for x in (-19.55, -17.05):
        add_cylinder(0.72, 27.9, 28.2, x, 0.0, "BigBen", created)
    lantern = box_brep(-19.25, -17.35, -1.05, 1.05, 35.6, 38.1)
    add_brep(lantern, "BigBen", created)
    spire = loft_circles([
        (38.1, 0.82, 0.82),
        (41.1, 0.34, 0.34),
        (44.8, 0.08, 0.08),
    ], -18.3, 0.0)
    add_brep(spire, "BigBen", created)
    add_segment_box((-22.8, -1.25), (-13.8, -1.25), 1.35, 0.94, 7.3, "Parliament", created)


def build_london_eye(created):
    center = wp(-2.2, 8.8, 14.0)
    plane = rg.Plane(center, rg.Vector3d(math.cos(math.radians(22.0)), math.sin(math.radians(22.0)), 0.0), rg.Vector3d.ZAxis)
    outer = rg.Circle(plane, 9.7).ToNurbsCurve()
    inner = rg.Circle(plane, 8.85).ToNurbsCurve()
    add_curve_pipe(outer, 0.18, "Eye", created)
    add_curve_pipe(inner, 0.08, "Eye", created)
    hub = rg.Sphere(center, 0.38).ToBrep()
    add_brep(hub, "Eye", created)
    rim_circle = rg.Circle(plane, 9.25)
    for i in range(24):
        ang = (2.0 * math.pi * i) / 24.0
        pt = rim_circle.PointAt(ang)
        spoke = rg.LineCurve(center, pt)
        add_curve_pipe(spoke, 0.03, "Eye", created)
        pod = loft_circles([
            (pt.Z - 0.34, 0.18, 0.13),
            (pt.Z, 0.34, 0.22),
            (pt.Z + 0.34, 0.18, 0.13),
        ], pt.X - OX, pt.Y - OY)
        add_brep(pod, "Eye", created)
    for ang in [0, 30, 60, 90, 120, 150]:
        pts = []
        for r in [3.0, 6.0, 8.9]:
            pts.append(rg.Circle(plane, r).PointAt(math.radians(ang)))
        add_curve_pipe(rg.Curve.CreateInterpolatedCurve(pts, 2), 0.025, "Eye", created)
    for side in (-1.0, 1.0):
        add_curve_pipe(rg.LineCurve(wp(-6.9, 5.2 * side + 5.8, 0.94), wp(-2.4, 7.3 * side + 5.8, 10.8)), 0.10, "Eye", created)
        add_curve_pipe(rg.LineCurve(wp(2.2, 6.0 * side + 5.0, 0.94), wp(-1.6, 7.5 * side + 5.0, 9.6)), 0.10, "Eye", created)
    add_brep(box_brep(-6.5, 2.6, 2.7, 6.0, 0.94, 1.45), "Eye", created)
    add_segment_box((-7.4, 4.4), (2.8, 4.2), 0.34, 1.45, 1.88, "Eye", created)


def bridge_tower(x, y, created):
    add_brep(box_brep(x - 1.35, x + 1.35, y - 1.2, y + 1.2, 0.94, 15.8), "Bridge", created)
    add_facade_grid_x(x - 1.35, x + 1.35, y + 1.2, 1.2, 15.3, 3, 7, 1.0, "Bridge", created, depth=0.06, mullion=0.03)
    add_facade_grid_x(x - 1.35, x + 1.35, y - 1.2, 1.2, 15.3, 3, 7, -1.0, "Bridge", created, depth=0.06, mullion=0.03)
    add_brep(box_brep(x - 1.65, x + 1.65, y - 1.45, y + 1.45, 15.8, 17.0), "Bridge", created)
    for offset in (-0.72, 0.0, 0.72):
        add_segment_box((x - 1.35, y + offset), (x + 1.35, y + offset), 0.10, 6.2, 13.9, "Bridge", created)
    roof = tapered_poly(
        [(x - 1.25, y - 1.05), (x + 1.25, y - 1.05), (x + 0.85, y + 1.05), (x - 0.85, y + 1.05)],
        17.0,
        [(x - 0.46, y - 0.34), (x + 0.46, y - 0.34), (x + 0.32, y + 0.34), (x - 0.32, y + 0.34)],
        19.4,
    )
    add_brep(roof, "Roofs", created)


def build_tower_bridge(created):
    add_segment_box((14.0, 11.2), (36.0, 11.0), 2.3, 6.0, 6.9, "Bridge", created)
    bridge_tower(19.0, 11.3, created)
    bridge_tower(30.5, 11.0, created)
    add_segment_box((19.0, 11.3), (30.5, 11.0), 1.3, 15.2, 16.0, "Bridge", created)
    north_curve = rg.Curve.CreateInterpolatedCurve(
        [wp(14.0, 11.55, 6.9), wp(18.0, 11.55, 12.7), wp(19.0, 11.55, 15.2), wp(24.7, 11.35, 18.8), wp(30.5, 11.15, 15.2), wp(32.0, 11.15, 12.8), wp(36.0, 11.0, 6.9)],
        3,
    )
    south_curve = rg.Curve.CreateInterpolatedCurve(
        [wp(14.0, 10.45, 6.9), wp(18.0, 10.45, 12.7), wp(19.0, 10.45, 15.2), wp(24.7, 10.65, 18.8), wp(30.5, 10.85, 15.2), wp(32.0, 10.85, 12.8), wp(36.0, 11.0, 6.9)],
        3,
    )
    add_curve_pipe(north_curve, 0.06, "Bridge", created)
    add_curve_pipe(south_curve, 0.06, "Bridge", created)
    for t in [0.08, 0.16, 0.24, 0.32, 0.40, 0.50, 0.60, 0.68, 0.76, 0.84, 0.92]:
        p0 = north_curve.PointAtNormalizedLength(t)
        p1 = wp(p0.X - OX, 11.0, 7.2)
        add_curve_pipe(rg.LineCurve(p0, p1), 0.035, "Bridge", created)
    for t0, t1 in [(0.10, 0.18), (0.22, 0.30), (0.34, 0.42), (0.58, 0.66), (0.70, 0.78), (0.82, 0.90)]:
        p0 = north_curve.PointAtNormalizedLength(t0)
        p1 = south_curve.PointAtNormalizedLength(t1)
        add_curve_pipe(rg.LineCurve(p0, p1), 0.025, "Bridge", created)


def build_station_and_roads(created):
    add_brep(box_brep(-18, 6, -23, -10, 0.94, 3.1), "Buildings", created)
    add_barrel_roof(-18, 6, -23, -10, 3.1, 6.0, "Roofs", created)
    for x in [-16, -12, -8, -4, 0, 4]:
        add_segment_box((x, -23.0), (x, -10.0), 0.22, 3.1, 8.7, "Roofs", created)
    add_facade_grid_x(-18, 6, -10.0, 1.2, 3.0, 12, 2, 1.0, "Buildings", created, depth=0.08, mullion=0.03)
    add_segment_box((-22, -15), (11, -15), 3.2, 0.94, 1.6, "Roads", created)
    add_segment_box((6, -4), (18, 3.5), 3.0, 0.94, 1.6, "Roads", created)
    add_segment_box((5, 1), (15, 8), 2.6, 0.94, 1.6, "Roads", created)


def build_shard(created):
    base0 = [(40.8, 4.1), (44.8, 3.0), (47.2, 7.3), (42.9, 8.4)]
    base1 = [(41.3, 4.7), (44.2, 4.0), (46.2, 6.9), (43.0, 7.7)]
    tiers = [
        (base0, 0.94, base1, 20.0),
        (base1, 20.0, [(41.8, 5.1), (43.9, 4.6), (45.4, 6.7), (43.0, 7.3)], 38.0),
        ([(41.8, 5.1), (43.9, 4.6), (45.4, 6.7), (43.0, 7.3)], 38.0, [(42.3, 5.6), (43.7, 5.3), (44.6, 6.4), (43.0, 6.8)], 56.0),
        ([(42.3, 5.6), (43.7, 5.3), (44.6, 6.4), (43.0, 6.8)], 56.0, [(42.8, 5.95), (43.25, 5.85), (43.58, 6.16), (43.0, 6.42)], 70.0),
    ]
    for p0, z0, p1, z1 in tiers:
        add_brep(tapered_poly(p0, z0, p1, z1), "Skyscrapers", created)
    for ratio in [0.16, 0.30, 0.44, 0.58, 0.72, 0.86]:
        z = 0.94 + (70.0 - 0.94) * ratio
        add_segment_box((41.2, 4.9), (46.2, 6.9), 0.07, z, z + 0.14, "Skyscrapers", created)
    for pts in [
        [(40.8, 4.1, 0.94), (42.8, 5.95, 70.0)],
        [(44.8, 3.0, 0.94), (43.25, 5.85, 70.0)],
        [(47.2, 7.3, 0.94), (43.58, 6.16, 70.0)],
        [(42.9, 8.4, 0.94), (43.0, 6.42, 70.0)],
    ]:
        add_curve_pipe(rg.LineCurve(wp(*pts[0]), wp(*pts[1])), 0.05, "Skyscrapers", created)


def build_gherkin(created):
    shell = loft_circles([
        (0.94, 2.3, 1.8),
        (7.0, 3.4, 2.6),
        (14.0, 4.2, 3.2),
        (22.0, 3.6, 2.8),
        (29.0, 2.1, 1.6),
    ], 30.5, -6.0)
    add_brep(shell, "Skyscrapers", created)
    for z in [4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 27.0]:
        ring = rg.Ellipse(rg.Plane(wp(30.5, -6.0, z), rg.Vector3d.ZAxis), 3.7, 2.8).ToNurbsCurve()
        add_curve_pipe(ring, 0.05, "Skyscrapers", created)
    for ang in [14, 46, 78, 110, 142, 174]:
        pts = []
        for z in [1.5, 7.0, 13.0, 19.0, 25.0, 28.0]:
            rx = 3.7 - 1.5 * abs((z - 14.0) / 15.0)
            ry = 2.8 - 1.2 * abs((z - 14.0) / 15.0)
            x = 30.5 + math.cos(math.radians(ang + z * 7.0)) * rx
            y = -6.0 + math.sin(math.radians(ang + z * 7.0)) * ry
            pts.append(wp(x, y, z))
        add_curve_pipe(rg.Curve.CreateInterpolatedCurve(pts, 3), 0.035, "Skyscrapers", created)


def build_city_hall(created):
    hall = loft_circles([
        (0.94, 3.0, 2.2),
        (3.0, 4.1, 2.9),
        (6.2, 3.5, 2.5),
        (10.6, 1.8, 1.4),
    ], 26.0, -13.6)
    xform = rg.Transform.Rotation(math.radians(-18.0), rg.Vector3d.YAxis, wp(26.0, -13.6, 5.0))
    hall.Transform(xform)
    add_brep(hall, "Skyscrapers", created)


def build_st_pauls(created):
    add_brep(box_brep(6.0, 17.0, 20.1, 28.1, 0.94, 7.9), "Buildings", created)
    add_facade_grid_x(6.0, 17.0, 20.1, 1.2, 7.7, 8, 3, -1.0, "Buildings", created, depth=0.08, mullion=0.03)
    add_facade_grid_x(6.0, 17.0, 28.1, 1.2, 7.7, 8, 3, 1.0, "Buildings", created, depth=0.08, mullion=0.03)
    for x in [7.2, 8.6, 10.0, 11.4, 12.8, 14.2, 15.6]:
        add_brep(box_brep(x - 0.16, x + 0.16, 19.4, 20.2, 0.94, 5.8), "Buildings", created)
    drum = add_cylinder(2.6, 7.9, 12.8, 11.5, 24.1, "Buildings", created)
    dome = loft_circles([
        (12.8, 2.6, 2.6),
        (15.6, 3.4, 3.4),
        (18.6, 2.0, 2.0),
        (21.8, 0.16, 0.16),
    ], 11.5, 24.1)
    add_brep(dome, "Roofs", created)
    for x in [8.0, 15.0]:
        add_brep(box_brep(x - 0.84, x + 0.84, 20.8, 22.7, 7.9, 14.4), "Buildings", created)
        spire = loft_circles([(14.4, 0.34, 0.34), (17.4, 0.14, 0.14), (19.3, 0.04, 0.04)], x, 21.7)
        add_brep(spire, "Roofs", created)


def build_generic_buildings(created):
    specs = [
        (-9.0, 19.0, 3.2, 2.8, 13.6, "setback"),
        (-5.0, 21.0, 3.6, 3.1, 17.2, "crown"),
        (-0.8, 18.8, 3.0, 2.7, 11.8, "setback"),
        (4.0, 19.8, 4.1, 3.0, 13.4, "setback"),
        (17.2, 19.4, 3.8, 3.0, 14.2, "setback"),
        (21.8, 21.6, 3.2, 2.7, 18.5, "crown"),
        (26.0, 19.8, 3.8, 3.1, 12.8, "setback"),
        (31.0, 19.0, 3.4, 2.8, 10.8, "setback"),
        (35.0, 18.6, 3.0, 2.5, 12.1, "setback"),
        (39.0, 19.5, 3.2, 2.8, 11.0, "setback"),
        (8.8, -21.8, 5.1, 4.0, 10.4, "setback"),
        (15.0, -21.5, 4.4, 3.7, 11.2, "setback"),
        (20.2, -20.8, 4.0, 3.5, 13.2, "crown"),
        (25.0, -20.2, 4.5, 3.8, 12.4, "setback"),
        (30.4, -19.4, 5.0, 4.0, 11.0, "setback"),
        (36.2, -18.2, 4.4, 3.5, 10.6, "setback"),
        (41.0, -15.4, 3.3, 2.7, 16.0, "crown"),
        (-47.8, 10.2, 3.2, 2.8, 9.0, "setback"),
        (-43.8, 12.4, 3.4, 2.9, 9.8, "setback"),
        (-39.4, 13.2, 3.2, 2.8, 10.8, "setback"),
        (-35.4, 14.0, 3.6, 3.0, 11.4, "setback"),
        (-31.0, 14.8, 3.8, 3.2, 12.2, "crown"),
        (-26.2, 14.4, 3.2, 2.8, 11.0, "setback"),
        (46.0, 20.0, 3.2, 2.7, 10.5, "setback"),
        (49.8, 18.2, 2.8, 2.4, 9.2, "setback"),
    ]
    for x, y, w, d, h, roof_mode in specs:
        add_context_building(x, y, w, d, h, created, roof_mode=roof_mode, grid=(max(3, int(round(w + 1.0))), max(3, int(round(h / 3.0)))))


def build_transport(created):
    add_bus(-30.0, -14.8, 2.6, 0.0, created)
    add_bus(-2.5, -15.0, 2.7, 0.0, created)
    add_bus(13.0, 1.8, 2.5, 34.0, created)
    add_bus(23.0, 11.0, 2.3, 0.0, created)
    add_boat(-31.0, 9.7, 0.9, created)
    add_boat(-6.0, 12.8, 1.0, created)
    add_boat(13.5, 13.0, 0.85, created)


def main():
    ensure_layers()
    created = []
    build_site(created)
    build_parliament(created)
    build_london_eye(created)
    build_tower_bridge(created)
    build_station_and_roads(created)
    build_shard(created)
    build_gherkin(created)
    build_city_hall(created)
    build_st_pauls(created)
    build_generic_buildings(created)
    build_transport(created)
    rs.SelectObjects(created)
    sc.doc.Views.Redraw()


try:
    main()
except Exception:
    with open(LOG_PATH, "w") as handle:
        handle.write(traceback.format_exc())
    raise
