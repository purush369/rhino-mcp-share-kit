import math
import traceback

import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System


SCENE_NAME = "WorldGardenGlobe"
PREFIX = "WorldGardenGlobe_20260509"

OX = 700.0
OY = 0.0

LAYERS = {
    "Site": (224, 216, 205),
    "Water": (136, 191, 219),
    "Landscape": (172, 200, 158),
    "GlobeFrame": (205, 205, 205),
    "Continents": (230, 230, 228),
    "Terraces": (214, 214, 208),
    "Ramps": (206, 202, 196),
    "Columns": (196, 196, 192),
    "Railings": (120, 120, 120),
    "Portal": (215, 215, 210),
    "Gardens": (118, 166, 110),
    "Fountains": (176, 186, 193),
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


def add_geometry(geometry, key, created):
    if isinstance(geometry, rg.Brep):
        obj_id = sc.doc.Objects.AddBrep(geometry)
    elif isinstance(geometry, rg.Curve):
        obj_id = sc.doc.Objects.AddCurve(geometry)
    else:
        return None
    if obj_id == System.Guid.Empty:
        return None
    assign(obj_id, key, created)
    return obj_id


def add_curve_pipe(curve_geom, radius, key, created):
    curve_id = sc.doc.Objects.AddCurve(curve_geom)
    if curve_id == System.Guid.Empty:
        return []
    pipe = rs.AddPipe(curve_id, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve_id)
    return assign(pipe, key, created)


def add_line_pipe(start, end, radius, key, created):
    curve = rs.AddLine(start, end)
    if not curve:
        return []
    pipe = rs.AddPipe(curve, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve)
    return assign(pipe, key, created)


def add_box(x0, x1, y0, y1, z0, z1, key, created):
    obj_id = rs.AddBox([
        wp(x0, y0, z0),
        wp(x1, y0, z0),
        wp(x1, y1, z0),
        wp(x0, y1, z0),
        wp(x0, y0, z1),
        wp(x1, y0, z1),
        wp(x1, y1, z1),
        wp(x0, y1, z1),
    ])
    assign(obj_id, key, created)
    return obj_id


def normalize2d(x, y):
    length = math.sqrt(x * x + y * y)
    if length < 0.0001:
        return (1.0, 0.0)
    return (x / length, y / length)


def add_segment_box(p0, p1, width, height, base_z, key, created):
    x0, y0 = p0
    x1, y1 = p1
    vx = x1 - x0
    vy = y1 - y0
    length = math.sqrt(vx * vx + vy * vy)
    if length < 0.01:
        return None
    ux = vx / length
    uy = vy / length
    plane = rg.Plane(
        wp((x0 + x1) * 0.5, (y0 + y1) * 0.5, base_z),
        rg.Vector3d(ux, uy, 0.0),
        rg.Vector3d(-uy, ux, 0.0),
    )
    box = rg.Box(
        plane,
        rg.Interval(-length * 0.5, length * 0.5),
        rg.Interval(-width * 0.5, width * 0.5),
        rg.Interval(0.0, height),
    )
    obj_id = sc.doc.Objects.AddBrep(box.ToBrep())
    assign(obj_id, key, created)
    return obj_id


def add_poly_surface(points, z, key, created):
    poly = [wp(x, y, z) for x, y in points]
    if poly[0] != poly[-1]:
        poly.append(poly[0])
    curve = rg.PolylineCurve(poly)
    breps = rg.Brep.CreatePlanarBreps(curve, sc.doc.ModelAbsoluteTolerance)
    ids = []
    if breps:
        for brep in breps:
            obj_id = sc.doc.Objects.AddBrep(brep)
            if obj_id != System.Guid.Empty:
                ids.extend(assign(obj_id, key, created))
    return ids


def add_extruded_poly(points, z, height, key, created):
    poly = [wp(x, y, z) for x, y in points]
    if poly[0] != poly[-1]:
        poly.append(poly[0])
    curve = rg.PolylineCurve(poly)
    breps = rg.Brep.CreatePlanarBreps(curve, sc.doc.ModelAbsoluteTolerance)
    ids = []
    if breps:
        vector = rg.Vector3d(0.0, 0.0, height)
        for brep in breps:
            extr = rg.BrepFace.CreateExtrusion(brep.Faces[0], rg.LineCurve(rg.Point3d(0, 0, 0), rg.Point3d(0, 0, height)), True)
            if extr:
                obj_id = sc.doc.Objects.AddBrep(extr)
                if obj_id != System.Guid.Empty:
                    ids.extend(assign(obj_id, key, created))
    return ids


def sphere_point(radius, lat_deg, lon_deg):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    x = radius * math.cos(lat) * math.cos(lon)
    y = radius * math.cos(lat) * math.sin(lon)
    z = radius * math.sin(lat)
    return rg.Point3d(OX + x, OY + y, z)


def add_great_circle(angle_deg, axis="z", radius=27.0, pipe_radius=0.65, key="GlobeFrame", created=None):
    created = created or []
    base_circle = rg.Circle(rg.Point3d(OX, OY, 0.0), radius).ToNurbsCurve()
    if axis == "x":
        xform = rg.Transform.Rotation(math.radians(90.0), rg.Vector3d.YAxis, rg.Point3d(OX, OY, 0.0))
    elif axis == "y":
        xform = rg.Transform.Rotation(math.radians(90.0), rg.Vector3d.XAxis, rg.Point3d(OX, OY, 0.0))
    else:
        xform = rg.Transform.Identity
    base_circle.Transform(xform)
    if abs(angle_deg) > 0.001:
        rot = rg.Transform.Rotation(math.radians(angle_deg), rg.Vector3d.ZAxis, rg.Point3d(OX, OY, 0.0))
        base_circle.Transform(rot)
    return add_curve_pipe(base_circle, pipe_radius, key, created)


def add_latitude_ring(lat_deg, radius=27.0, pipe_radius=0.28, created=None):
    created = created or []
    z = radius * math.sin(math.radians(lat_deg))
    r = radius * math.cos(math.radians(lat_deg))
    curve = rg.Circle(rg.Point3d(OX, OY, z), r).ToNurbsCurve()
    return add_curve_pipe(curve, pipe_radius, "GlobeFrame", created)


def add_meridian_arc(lon_deg, lat0, lat1, radius=27.0, pipe_radius=0.24, created=None):
    created = created or []
    pts = []
    steps = 24
    for i in range(steps + 1):
        t = float(i) / float(steps)
        lat = lat0 + (lat1 - lat0) * t
        pts.append(sphere_point(radius, lat, lon_deg))
    curve = rg.Curve.CreateInterpolatedCurve(pts, 3)
    return add_curve_pipe(curve, pipe_radius, "GlobeFrame", created)


def arc_points(cx, cy, r, a0, a1, count):
    pts = []
    for i in range(count):
        t = float(i) / float(count - 1)
        ang = math.radians(a0 + (a1 - a0) * t)
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    return pts


def add_annular_sector(cx, cy, r_outer, r_inner, a0, a1, z, height, key, created):
    outer = arc_points(cx, cy, r_outer, a0, a1, 24)
    inner = arc_points(cx, cy, r_inner, a1, a0, 24)
    poly = outer + inner
    return add_extruded_poly(poly, z, height, key, created)


def add_stair_run(p0, p1, width, z0, z1, steps, key, created):
    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0
    rise = (z1 - z0) / float(steps)
    for i in range(steps):
        t0 = float(i) / float(steps)
        t1 = float(i + 1) / float(steps)
        sx0 = x0 + dx * t0
        sy0 = y0 + dy * t0
        sx1 = x0 + dx * t1
        sy1 = y0 + dy * t1
        add_segment_box((sx0, sy0), (sx1, sy1), width, rise, z0 + rise * i, key, created)


def add_circular_rail(cx, cy, radius, z, post_count, created):
    curve = rg.Circle(rg.Point3d(OX + cx, OY + cy, z + 1.02), radius).ToNurbsCurve()
    add_curve_pipe(curve, 0.10, "Railings", created)
    for i in range(post_count):
        ang = (360.0 * i) / float(post_count)
        x = cx + math.cos(math.radians(ang)) * radius
        y = cy + math.sin(math.radians(ang)) * radius
        add_line_pipe(wp(x, y, z), wp(x, y, z + 1.02), 0.08, "Railings", created)


def add_arc_rail(cx, cy, radius, a0, a1, z, post_count, created):
    pts = [wp(x, y, z + 1.02) for x, y in arc_points(cx, cy, radius, a0, a1, 36)]
    curve = rg.Curve.CreateInterpolatedCurve(pts, 3)
    add_curve_pipe(curve, 0.10, "Railings", created)
    for i in range(post_count):
        t = float(i) / float(max(1, post_count - 1))
        ang = a0 + (a1 - a0) * t
        x = cx + math.cos(math.radians(ang)) * radius
        y = cy + math.sin(math.radians(ang)) * radius
        add_line_pipe(wp(x, y, z), wp(x, y, z + 1.02), 0.08, "Railings", created)


def add_tree(x, y, z, trunk_h, crown_r, created):
    trunk = rs.AddCylinder(wp(x, y, z), trunk_h, max(0.18, crown_r * 0.12), True)
    assign(trunk, "Gardens", created)
    spheres = [
        rs.AddSphere(wp(x, y, z + trunk_h + crown_r * 0.45), crown_r),
        rs.AddSphere(wp(x - crown_r * 0.55, y, z + trunk_h + crown_r * 0.10), crown_r * 0.70),
        rs.AddSphere(wp(x + crown_r * 0.55, y + crown_r * 0.15, z + trunk_h + crown_r * 0.06), crown_r * 0.68),
    ]
    for obj_id, scale in zip(spheres, [(1.3, 1.0, 0.72), (1.0, 1.1, 0.80), (1.05, 0.95, 0.76)]):
        if obj_id:
            rs.ScaleObject(obj_id, rs.SurfaceAreaCentroid(obj_id)[0], scale, False)
            assign(obj_id, "Gardens", created)


def add_shrub(x, y, z, radius, created):
    obj_id = rs.AddSphere(wp(x, y, z + radius * 0.6), radius)
    if obj_id:
        rs.ScaleObject(obj_id, rs.SurfaceAreaCentroid(obj_id)[0], (1.35, 1.0, 0.52), False)
        assign(obj_id, "Gardens", created)


def add_fountain(cx, cy, r_outer, r_inner, z, created):
    add_annular_sector(cx, cy, r_outer, r_inner, 0.0, 360.0, z, 0.38, "Fountains", created)
    bowl = rs.AddSphere(wp(cx, cy, z + 0.58), r_inner * 0.45)
    if bowl:
        rs.ScaleObject(bowl, rs.SurfaceAreaCentroid(bowl)[0], (1.0, 1.0, 0.35), False)
        assign(bowl, "Fountains", created)
    jet = rs.AddCylinder(wp(cx, cy, z + 0.38), 0.95, 0.08, True)
    assign(jet, "Water", created)


def add_hex_portal(cx, cy, z0, radius, depth, created):
    pts = []
    for i in range(6):
        a = math.radians(60.0 * i + 30.0)
        pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
    add_extruded_poly(pts, z0, depth, "Portal", created)

    inner_r = radius * 0.44
    for i in range(6):
        a = math.radians(60.0 * i + 30.0)
        x = cx + math.cos(a) * inner_r
        y = cy + math.sin(a) * inner_r
        add_line_pipe(wp(cx, cy, z0 + depth * 0.5), wp(x, y, z0 + depth * 0.5), 0.11, "Portal", created)
    for i in range(6):
        a0 = math.radians(60.0 * i + 30.0)
        a1 = math.radians(60.0 * ((i + 1) % 6) + 30.0)
        p0 = wp(cx + math.cos(a0) * inner_r, cy + math.sin(a0) * inner_r, z0 + depth * 0.5)
        p1 = wp(cx + math.cos(a1) * inner_r, cy + math.sin(a1) * inner_r, z0 + depth * 0.5)
        add_line_pipe(p0, p1, 0.09, "Portal", created)


def add_ring_columns(radius, count, z0, h, created):
    for i in range(count):
        ang = math.radians((360.0 * i) / float(count))
        x = math.cos(ang) * radius
        y = math.sin(ang) * radius
        shaft = rs.AddCylinder(wp(x, y, z0), h, 0.38, True)
        cap = rs.AddCylinder(wp(x, y, z0 + h), 0.28, 0.58, True)
        base = rs.AddCylinder(wp(x, y, z0 - 0.15), 0.15, 0.54, True)
        assign([shaft, cap, base], "Columns", created)


def add_support_leg(x0, y0, z0, x1, y1, z1, created):
    add_line_pipe(wp(x0, y0, z0), wp(x1, y1, z1), 0.56, "Columns", created)


def continent_brep(lat, lon, width, height, pts2d, thickness, created):
    center = sphere_point(27.0, lat, lon)
    normal = rg.Vector3d(center.X - OX, center.Y - OY, center.Z)
    normal.Unitize()
    tangent1 = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, normal)
    if tangent1.IsTiny():
        tangent1 = rg.Vector3d.XAxis
    tangent1.Unitize()
    tangent2 = rg.Vector3d.CrossProduct(normal, tangent1)
    tangent2.Unitize()
    plane = rg.Plane(center, tangent1, tangent2)

    poly = []
    for x, y in pts2d:
        pt = plane.PointAt(x * width, y * height)
        poly.append(pt)
    if poly[0] != poly[-1]:
        poly.append(poly[0])
    curve = rg.PolylineCurve(poly)
    breps = rg.Brep.CreatePlanarBreps(curve, sc.doc.ModelAbsoluteTolerance)
    if not breps:
        return
    vec = normal * thickness
    for brep in breps:
        face = brep.Faces[0]
        srf = face.DuplicateFace(False)
        ext = rg.BrepFace.CreateExtrusion(srf.Faces[0], rg.LineCurve(rg.Point3d(0, 0, 0), rg.Point3d(vec.X, vec.Y, vec.Z)), True)
        if ext:
            add_geometry(ext, "Continents", created)


def main():
    rs.EnableRedraw(False)
    ensure_layers()
    created = []

    site_outline = [
        (-34.0, -20.0),
        (-24.0, -25.0),
        (-8.0, -28.0),
        (9.0, -28.5),
        (24.0, -24.0),
        (34.0, -18.0),
        (31.0, 0.0),
        (26.0, 11.0),
        (16.0, 19.0),
        (0.0, 22.0),
        (-16.0, 18.0),
        (-27.0, 10.0),
        (-33.0, 0.0),
    ]
    add_extruded_poly(site_outline, -1.2, 1.2, "Site", created)
    add_poly_surface(site_outline, 0.0, "Landscape", created)

    water_a = arc_points(-30.0, -18.0, 12.0, -20.0, 150.0, 28)
    water_b = arc_points(-28.0, -17.5, 7.5, 150.0, -20.0, 28)
    add_poly_surface(water_a + water_b, -0.42, "Water", created)

    water_c = arc_points(30.0, -18.5, 7.4, 30.0, 170.0, 20)
    water_d = arc_points(30.0, -18.5, 4.2, 170.0, 30.0, 20)
    add_poly_surface(water_c + water_d, -0.38, "Water", created)

    add_annular_sector(0.0, -2.0, 28.0, 23.0, 180.0, 360.0, 0.0, 0.55, "Site", created)
    add_stair_run((-10.5, -27.0), (10.5, -27.0), 10.8, 0.0, 2.0, 7, "Site", created)

    add_fountain(-17.0, -20.5, 3.0, 1.9, 0.02, created)
    add_fountain(17.0, -20.5, 3.0, 1.9, 0.02, created)
    add_fountain(0.0, -23.0, 2.6, 1.6, 0.02, created)

    # Globe frame
    add_great_circle(0.0, "x", 27.0, 0.78, "GlobeFrame", created)
    add_great_circle(90.0, "x", 27.0, 0.78, "GlobeFrame", created)
    add_great_circle(28.0, "y", 27.0, 0.70, "GlobeFrame", created)
    add_great_circle(-34.0, "y", 27.0, 0.70, "GlobeFrame", created)
    add_great_circle(18.0, "z", 27.0, 0.52, "GlobeFrame", created)
    add_great_circle(78.0, "z", 27.0, 0.52, "GlobeFrame", created)
    for lat in (-45.0, -25.0, -8.0, 8.0, 25.0, 45.0):
        add_latitude_ring(lat, 27.0, 0.18 if abs(lat) < 9 else 0.22, created)
    for lon in (-150.0, -105.0, -60.0, -20.0, 25.0, 70.0, 115.0, 155.0):
        add_meridian_arc(lon, -70.0, 75.0, 27.0, 0.16, created)

    # Continents
    continent_brep(48.0, -78.0, 10.5, 7.0, [(-0.9, 0.2), (-0.6, 0.5), (-0.2, 0.55), (0.15, 0.35), (0.35, 0.10), (0.20, -0.15), (-0.10, -0.25), (-0.35, -0.45), (-0.70, -0.28), (-0.95, -0.02)], 0.85, created)
    continent_brep(30.0, 36.0, 16.0, 8.5, [(-0.95, 0.20), (-0.55, 0.55), (-0.10, 0.62), (0.25, 0.45), (0.72, 0.34), (1.0, 0.05), (0.80, -0.18), (0.36, -0.10), (0.10, -0.40), (-0.22, -0.55), (-0.65, -0.38), (-0.98, -0.06)], 0.92, created)
    continent_brep(-22.0, 134.0, 7.2, 4.8, [(-0.75, 0.12), (-0.35, 0.40), (0.08, 0.36), (0.48, 0.18), (0.70, -0.08), (0.50, -0.35), (0.08, -0.42), (-0.28, -0.30), (-0.65, -0.12)], 0.65, created)
    continent_brep(4.0, -18.0, 8.2, 10.5, [(-0.45, 0.70), (-0.18, 0.95), (0.10, 0.88), (0.28, 0.55), (0.14, 0.28), (0.18, -0.05), (0.05, -0.42), (-0.12, -0.75), (-0.38, -0.96), (-0.52, -0.58), (-0.60, -0.18), (-0.58, 0.22)], 0.58, created)

    # Interior terraces
    add_annular_sector(0.0, 0.0, 20.0, 13.8, 206.0, 350.0, 3.0, 0.55, "Terraces", created)
    add_annular_sector(0.0, 1.0, 18.0, 11.2, 200.0, 338.0, 8.0, 0.55, "Terraces", created)
    add_annular_sector(0.0, 1.4, 15.4, 8.8, 198.0, 330.0, 12.6, 0.55, "Terraces", created)
    add_annular_sector(0.0, 1.8, 12.4, 6.8, 196.0, 322.0, 17.0, 0.55, "Terraces", created)
    add_annular_sector(0.0, 2.2, 9.0, 4.8, 194.0, 314.0, 21.0, 0.55, "Terraces", created)

    add_annular_sector(0.0, 0.0, 14.6, 8.2, 35.0, 138.0, 5.2, 0.45, "Ramps", created)
    add_annular_sector(0.0, 1.0, 12.4, 7.1, 30.0, 124.0, 10.2, 0.45, "Ramps", created)
    add_annular_sector(0.0, 1.7, 10.2, 5.6, 24.0, 112.0, 14.8, 0.45, "Ramps", created)
    add_annular_sector(0.0, 2.1, 8.2, 4.5, 18.0, 96.0, 19.2, 0.45, "Ramps", created)

    add_ring_columns(21.0, 10, 0.2, 8.8, created)
    add_support_leg(-11.0, -2.0, 0.0, -5.0, 1.0, 10.0, created)
    add_support_leg(11.0, -2.0, 0.0, 5.0, 1.0, 10.0, created)
    add_support_leg(-6.0, 10.0, 0.0, -2.0, 5.0, 11.0, created)
    add_support_leg(6.0, 10.0, 0.0, 2.0, 5.0, 11.0, created)
    core = rs.AddCylinder(wp(0.0, 0.0, -0.2), 23.5, 1.5, True)
    assign(core, "Columns", created)

    add_arc_rail(0.0, 0.0, 19.7, 208.0, 348.0, 3.55, 18, created)
    add_arc_rail(0.0, 1.0, 17.7, 202.0, 336.0, 8.55, 16, created)
    add_arc_rail(0.0, 1.4, 15.0, 200.0, 328.0, 13.15, 14, created)
    add_arc_rail(0.0, 1.8, 12.0, 198.0, 320.0, 17.55, 12, created)
    add_arc_rail(0.0, 2.2, 8.6, 196.0, 312.0, 21.55, 10, created)
    add_circular_rail(0.0, -7.5, 10.4, 1.0, 20, created)

    # Portal and foreground court
    add_hex_portal(0.0, -5.5, 1.2, 6.4, 0.5, created)
    add_hex_portal(0.0, -5.5, 8.2, 4.4, 0.35, created)

    add_ring_columns(13.5, 12, 0.0, 10.8, created)
    add_annular_sector(0.0, -7.0, 16.8, 12.8, 180.0, 360.0, 10.4, 0.45, "Terraces", created)
    add_arc_rail(0.0, -7.0, 16.5, 184.0, 356.0, 10.85, 18, created)

    # Gardens
    for data in [
        (-8.5, -6.0, 0.0, 4.6, 2.2),
        (8.0, -6.5, 0.0, 4.2, 2.0),
        (-10.0, 4.0, 3.0, 3.8, 1.8),
        (10.5, 3.0, 3.0, 3.8, 1.8),
        (-4.5, 7.0, 8.0, 3.2, 1.6),
        (6.0, 6.6, 8.0, 3.3, 1.7),
        (-3.0, 7.8, 12.6, 3.0, 1.5),
        (4.0, 8.6, 12.6, 3.0, 1.5),
        (0.0, 6.2, 17.0, 2.8, 1.4),
    ]:
        add_tree(data[0], data[1], data[2], data[3], data[4], created)

    shrubs = [
        (-13.0, -10.0, 0.0), (-9.5, -11.2, 0.0), (-6.8, -9.0, 0.0), (-3.2, -11.4, 0.0),
        (3.8, -11.0, 0.0), (7.2, -9.2, 0.0), (11.0, -10.8, 0.0), (13.5, -8.6, 0.0),
        (-13.5, 2.0, 3.0), (-9.0, 1.0, 3.0), (9.0, 1.0, 3.0), (13.0, 2.4, 3.0),
        (-8.2, 9.0, 8.0), (-2.0, 9.5, 8.0), (5.0, 9.8, 8.0), (10.0, 8.2, 8.0),
        (-2.5, 11.2, 12.6), (3.8, 11.0, 12.6), (-1.0, 9.6, 17.0), (2.0, 10.0, 17.0),
        (0.0, 8.8, 21.0), (-20.0, -18.0, 0.0), (20.0, -18.0, 0.0), (0.0, -21.0, 0.0),
    ]
    for x, y, z in shrubs:
        add_shrub(x, y, z, 1.0 if z < 1.0 else 0.85, created)

    rs.UnselectAllObjects()
    if created:
        rs.SelectObjects(created)
    rs.EnableRedraw(True)
    rs.Redraw()


try:
    main()
except Exception:
    log_path = r"C:\Users\Admin\AppData\Local\RhinoMCP\world_garden_globe_error.log"
    message = traceback.format_exc()
    handle = open(log_path, "w")
    handle.write(message)
    handle.close()
    print(message)
