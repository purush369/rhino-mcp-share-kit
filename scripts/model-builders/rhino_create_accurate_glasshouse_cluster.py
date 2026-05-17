import math
import traceback

import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System


SCENE_NAME = "AccurateGlasshouseCluster"
PREFIX = "AccurateGlasshouseCluster_20260509"

OX = 340.0
OY = 0.0

LAYERS = {
    "Site": (220, 214, 206),
    "Landscape": (191, 212, 186),
    "Court": (205, 187, 165),
    "Bridges": (223, 184, 188),
    "Rails": (176, 152, 152),
    "Walls": (164, 164, 164),
    "Shell": (214, 235, 240),
    "Frame": (112, 126, 132),
    "Interiors": (212, 142, 148),
    "EntryBlocks": (242, 241, 237),
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
    elif isinstance(geometry, rg.Surface):
        obj_id = sc.doc.Objects.AddSurface(geometry)
    else:
        return None
    if obj_id == System.Guid.Empty:
        return None
    assign(obj_id, key, created)
    return obj_id


def add_curve_pipe(points, radius, key, created):
    curve = rs.AddInterpCurve(points, 3)
    if not curve:
        return []
    pipe = rs.AddPipe(curve, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve)
    return assign(pipe, key, created)


def add_line_pipe(start, end, radius, key, created):
    curve = rs.AddLine(start, end)
    if not curve:
        return []
    pipe = rs.AddPipe(curve, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve)
    return assign(pipe, key, created)


def add_curve_geom_pipe(curve_geom, radius, key, created):
    curve_id = sc.doc.Objects.AddCurve(curve_geom)
    if curve_id == System.Guid.Empty:
        return []
    pipe = rs.AddPipe(curve_id, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve_id)
    return assign(pipe, key, created)


def add_polyline_surface(points, z, key, created):
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


def add_path(points, width, height, base_z, key, created):
    ids = []
    for i in range(len(points) - 1):
        obj_id = add_segment_box(points[i], points[i + 1], width, height, base_z, key, created)
        if obj_id:
            ids.append(obj_id)
    return ids


def ellipse_xy(cx, cy, rx, ry, rot_deg, angle_deg):
    ang = math.radians(angle_deg)
    rot = math.radians(rot_deg)
    local_x = math.cos(ang) * rx
    local_y = math.sin(ang) * ry
    x = local_x * math.cos(rot) - local_y * math.sin(rot)
    y = local_x * math.sin(rot) + local_y * math.cos(rot)
    return (cx + x, cy + y)


def ellipse_point(cx, cy, rx, ry, rot_deg, angle_deg, z):
    x, y = ellipse_xy(cx, cy, rx, ry, rot_deg, angle_deg)
    return wp(x, y, z)


def add_ellipse_curve(cx, cy, rx, ry, rot_deg, z, key, created, pipe_radius=None):
    plane = rg.Plane(wp(cx, cy, z), rg.Vector3d.XAxis, rg.Vector3d.YAxis)
    if abs(rot_deg) > 0.001:
        plane.Rotate(math.radians(rot_deg), rg.Vector3d.ZAxis)
    curve = rg.Ellipse(plane, rx, ry).ToNurbsCurve()
    if pipe_radius:
        return add_curve_geom_pipe(curve, pipe_radius, key, created)
    return add_geometry(curve, key, created)


def add_ellipse_walk(cx, cy, rx, ry, rot_deg, z, width, height, key, created, segments=36):
    points = []
    for i in range(segments):
        angle = (360.0 * i) / float(segments)
        points.append(ellipse_xy(cx, cy, rx, ry, rot_deg, angle))
    points.append(points[0])
    for i in range(len(points) - 1):
        add_segment_box(points[i], points[i + 1], width, height, z, key, created)


def add_low_wall(points, thickness, z0, z1, key, created, closed=True):
    poly = list(points)
    if closed and poly[0] != poly[-1]:
        poly.append(poly[0])
    for i in range(len(poly) - 1):
        add_segment_box(poly[i], poly[i + 1], thickness, z1 - z0, z0, key, created)


def add_column_ring(cx, cy, rx, ry, rot_deg, sx, sy, z0, height, radius, angles, key, created):
    for angle_deg in angles:
        x, y = ellipse_xy(cx, cy, rx * sx, ry * sy, rot_deg, angle_deg)
        column = rs.AddCylinder(wp(x, y, z0), height, radius, True)
        assign(column, key, created)


def add_railed_path(points, width, deck_h, base_z, created, rail_h=1.05, rail_radius=0.06, post_radius=0.04):
    for i in range(len(points) - 1):
        p0 = points[i]
        p1 = points[i + 1]
        add_segment_box(p0, p1, width, deck_h, base_z, "Bridges", created)

        x0, y0 = p0
        x1, y1 = p1
        vx = x1 - x0
        vy = y1 - y0
        length = math.sqrt(vx * vx + vy * vy)
        if length < 0.01:
            continue
        nx = -vy / length
        ny = vx / length
        edge_offset = width * 0.5 - 0.18
        top_z = base_z + deck_h + rail_h
        post_z0 = base_z + deck_h

        left0 = wp(x0 + nx * edge_offset, y0 + ny * edge_offset, top_z)
        left1 = wp(x1 + nx * edge_offset, y1 + ny * edge_offset, top_z)
        right0 = wp(x0 - nx * edge_offset, y0 - ny * edge_offset, top_z)
        right1 = wp(x1 - nx * edge_offset, y1 - ny * edge_offset, top_z)
        add_line_pipe(left0, left1, rail_radius, "Rails", created)
        add_line_pipe(right0, right1, rail_radius, "Rails", created)

        divisions = max(2, int(length / 4.0) + 1)
        for step in range(divisions + 1):
            t = float(step) / float(divisions)
            px = x0 + vx * t
            py = y0 + vy * t
            for side in (-1.0, 1.0):
                sx = px + nx * edge_offset * side
                sy = py + ny * edge_offset * side
                add_line_pipe(wp(sx, sy, post_z0), wp(sx, sy, top_z), post_radius, "Rails", created)


def add_planter(cx, cy, width, depth, z0, h, created):
    add_box(cx - width * 0.5, cx + width * 0.5, cy - depth * 0.5, cy + depth * 0.5, z0, z0 + h, "Bridges", created)
    add_box(cx - width * 0.38, cx + width * 0.38, cy - depth * 0.38, cy + depth * 0.38, z0 + h, z0 + h + 0.18, "Landscape", created)


def normalize2d(x, y):
    length = math.sqrt(x * x + y * y)
    if length < 0.0001:
        return (1.0, 0.0)
    return (x / length, y / length)


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


def transform_brep(brep, rx, ry, rot_deg, cx, cy):
    xform = rg.Transform.Scale(rg.Plane.WorldXY, rx, ry, 1.0)
    brep.Transform(xform)
    if abs(rot_deg) > 0.001:
        brep.Transform(rg.Transform.Rotation(math.radians(rot_deg), rg.Vector3d.ZAxis, rg.Point3d.Origin))
    brep.Transform(rg.Transform.Translation(OX + cx, OY + cy, 0.0))
    return brep


def make_wall_surface(height, rx, ry, rot_deg, cx, cy):
    line = rg.LineCurve(rg.Point3d(1.0, 0.0, 0.0), rg.Point3d(1.0, 0.0, height))
    axis = rg.Line(rg.Point3d(0.0, 0.0, -2.0), rg.Point3d(0.0, 0.0, height + 2.0))
    rev = rg.RevSurface.Create(line, axis)
    return transform_brep(rg.Brep.CreateFromSurface(rev), rx, ry, rot_deg, cx, cy)


def make_roof_surface(profile_points, rx, ry, rot_deg, cx, cy):
    pts = [rg.Point3d(r, 0.0, z) for r, z in profile_points]
    curve = rg.Curve.CreateInterpolatedCurve(pts, 3)
    axis = rg.Line(rg.Point3d(0.0, 0.0, -2.0), rg.Point3d(0.0, 0.0, pts[0].Z + 2.0))
    rev = rg.RevSurface.Create(curve, axis)
    return transform_brep(rg.Brep.CreateFromSurface(rev), rx, ry, rot_deg, cx, cy)


def make_roof_profile(wall_h, dome_h, mode):
    top = wall_h + dome_h
    if mode == "flat":
        return [
            (0.00, top),
            (0.20, wall_h + dome_h * 0.99),
            (0.55, wall_h + dome_h * 0.90),
            (0.90, wall_h + dome_h * 0.45),
            (1.00, wall_h),
        ]
    if mode == "pointed":
        return [
            (0.00, top),
            (0.12, wall_h + dome_h * 0.97),
            (0.34, wall_h + dome_h * 0.82),
            (0.68, wall_h + dome_h * 0.50),
            (0.92, wall_h + dome_h * 0.18),
            (1.00, wall_h),
        ]
    if mode == "low":
        return [
            (0.00, top),
            (0.26, wall_h + dome_h * 0.93),
            (0.62, wall_h + dome_h * 0.72),
            (0.92, wall_h + dome_h * 0.28),
            (1.00, wall_h),
        ]
    return [
        (0.00, top),
        (0.18, wall_h + dome_h * 0.97),
        (0.48, wall_h + dome_h * 0.83),
        (0.84, wall_h + dome_h * 0.42),
        (1.00, wall_h),
    ]


def add_planar_ellipse(cx, cy, rx, ry, rot_deg, z, key, created):
    plane = rg.Plane(wp(cx, cy, z), rg.Vector3d.XAxis, rg.Vector3d.YAxis)
    if abs(rot_deg) > 0.001:
        plane.Rotate(math.radians(rot_deg), rg.Vector3d.ZAxis)
    curve = rg.Ellipse(plane, rx, ry).ToNurbsCurve()
    breps = rg.Brep.CreatePlanarBreps(curve, sc.doc.ModelAbsoluteTolerance)
    ids = []
    if breps:
        for brep in breps:
            obj_id = sc.doc.Objects.AddBrep(brep)
            if obj_id != System.Guid.Empty:
                ids.extend(assign(obj_id, key, created))
    return ids


def add_frame_sections(brep, cx, cy, z_values, radial_angles, oblique_angles, key, created, pipe_radius=None):
    tol = sc.doc.ModelAbsoluteTolerance
    origin = wp(cx, cy, 0.0)

    for z in z_values:
        plane = rg.Plane(wp(cx, cy, z), rg.Vector3d.XAxis, rg.Vector3d.YAxis)
        ok, curves, _ = rg.Intersect.Intersection.BrepPlane(brep, plane, tol)
        if ok and curves:
            for curve in curves:
                if pipe_radius:
                    add_curve_geom_pipe(curve, pipe_radius, key, created)
                else:
                    add_geometry(curve, key, created)

    for angle_deg in radial_angles:
        ang = math.radians(angle_deg)
        radial = rg.Vector3d(math.cos(ang), math.sin(ang), 0.0)
        plane = rg.Plane(origin, radial, rg.Vector3d.ZAxis)
        ok, curves, _ = rg.Intersect.Intersection.BrepPlane(brep, plane, tol)
        if ok and curves:
            for curve in curves:
                if pipe_radius:
                    add_curve_geom_pipe(curve, pipe_radius, key, created)
                else:
                    add_geometry(curve, key, created)

    for angle_deg, tilt_sign in oblique_angles:
        ang = math.radians(angle_deg)
        radial = rg.Vector3d(math.cos(ang), math.sin(ang), 0.0)
        tangent = rg.Vector3d(-math.sin(ang), math.cos(ang), 0.0)
        lifted = rg.Vector3d(tangent.X, tangent.Y, 0.55 * tilt_sign)
        plane = rg.Plane(origin, radial, lifted)
        ok, curves, _ = rg.Intersect.Intersection.BrepPlane(brep, plane, tol)
        if ok and curves:
            for curve in curves:
                if pipe_radius:
                    add_curve_geom_pipe(curve, pipe_radius, key, created)
                else:
                    add_geometry(curve, key, created)


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


def add_portal_frame(cx, cy, rx, ry, rot_deg, angle_deg, z0, height, width, depth, radius, created):
    outer_x, outer_y = ellipse_xy(cx, cy, rx, ry, rot_deg, angle_deg)
    inward_x, inward_y = normalize2d(cx - outer_x, cy - outer_y)
    tangent_x, tangent_y = (-inward_y, inward_x)

    base_x = outer_x + inward_x * depth
    base_y = outer_y + inward_y * depth

    left_x = base_x + tangent_x * width * 0.5
    left_y = base_y + tangent_y * width * 0.5
    right_x = base_x - tangent_x * width * 0.5
    right_y = base_y - tangent_y * width * 0.5

    add_line_pipe(wp(left_x, left_y, z0), wp(left_x, left_y, z0 + height), radius, "Frame", created)
    add_line_pipe(wp(right_x, right_y, z0), wp(right_x, right_y, z0 + height), radius, "Frame", created)
    add_line_pipe(wp(left_x, left_y, z0 + height), wp(right_x, right_y, z0 + height), radius, "Frame", created)


def add_entry_block(cx, cy, width, depth, z0, z1, rot_deg, created):
    add_box(-width * 0.5, width * 0.5, -depth * 0.5, depth * 0.5, z0, z1, "EntryBlocks", created)
    latest = created[-1]
    rs.RotateObject(latest, wp(0.0, 0.0, 0.0), rot_deg, None, True)
    rs.MoveObject(latest, rg.Vector3d(cx, cy, 0.0))
    return latest


def add_hex_court_lines(created):
    size = 2.0
    ids = []
    for row in range(-2, 3):
        for col in range(-3, 4):
            x = -2.0 + col * size * 1.58 + (row % 2) * size * 0.79
            y = -8.5 + row * size * 1.35
            if x < -11.0 or x > 10.5 or y < -15.0 or y > -2.2:
                continue
            pts = []
            for i in range(6):
                a = math.radians(60.0 * i + 30.0)
                pts.append(wp(x + math.cos(a) * size, y + math.sin(a) * size, 0.28))
            pts.append(pts[0])
            curve = sc.doc.Objects.AddCurve(rg.PolylineCurve(pts))
            ids.extend(assign(curve, "Frame", created))
    return ids


def add_interior_ribbon(cx, cy, rx, ry, rot_deg, z0, z1, start_deg, end_deg, radius, created):
    rot = math.radians(rot_deg)
    pts = []
    count = 32
    span = end_deg - start_deg
    for i in range(count):
        t = float(i) / float(count - 1)
        ang = math.radians(start_deg + span * t)
        local_x = math.cos(ang) * rx
        local_y = math.sin(ang) * ry
        x = local_x * math.cos(rot) - local_y * math.sin(rot)
        y = local_x * math.sin(rot) + local_y * math.cos(rot)
        z = z0 + (z1 - z0) * t + math.sin(t * math.pi) * 0.35
        pts.append(wp(cx + x, cy + y, z))
    return add_curve_pipe(pts, radius, "Interiors", created)


def add_greenhouse(spec, created):
    cx = spec["cx"]
    cy = spec["cy"]
    rx = spec["rx"]
    ry = spec["ry"]
    rot_deg = spec["rot"]
    wall_h = spec["wall_h"]
    dome_h = spec["dome_h"]
    roof_mode = spec["roof"]
    frame_radius_wall = spec.get("frame_radius_wall", 0.09)
    frame_radius_roof = spec.get("frame_radius_roof", frame_radius_wall * 0.90)
    ring_radius = spec.get("ring_radius", frame_radius_wall * 1.15)

    floor_scale = spec.get("floor_scale", 0.62)
    wall = make_wall_surface(wall_h, rx, ry, rot_deg, cx, cy)
    roof = make_roof_surface(make_roof_profile(wall_h, dome_h, roof_mode), rx, ry, rot_deg, cx, cy)
    add_geometry(wall, "Shell", created)
    add_geometry(roof, "Shell", created)

    add_planar_ellipse(cx, cy, rx * 0.96, ry * 0.96, rot_deg, 0.04, "Landscape", created)
    add_planar_ellipse(cx, cy, rx * floor_scale, ry * floor_scale, rot_deg, 0.08, "Landscape", created)

    wall_z = [wall_h * factor for factor in spec.get("wall_levels", (0.16, 0.30, 0.44, 0.58, 0.72, 0.86))]
    roof_z = [wall_h + dome_h * factor for factor in spec.get("roof_levels", (0.10, 0.22, 0.34, 0.46, 0.58, 0.70, 0.82, 0.92))]
    radial_angles = []
    for step in spec["radials"] + spec.get("extra_radials", []):
        angle = rot_deg + step
        if angle not in radial_angles:
            radial_angles.append(angle)
    oblique = []
    for step in spec["oblique"]:
        oblique.append((rot_deg + step, 1.0))
        oblique.append((rot_deg + step + 14.0, -1.0))

    add_frame_sections(wall, cx, cy, wall_z, radial_angles, [], "Frame", created, frame_radius_wall)
    add_frame_sections(roof, cx, cy, roof_z, radial_angles[: max(6, len(radial_angles) - 1)], oblique, "Frame", created, frame_radius_roof)

    for z in spec.get("brace_rings", []):
        add_ellipse_curve(cx, cy, rx * 0.985, ry * 0.985, rot_deg, z, "Frame", created, ring_radius)

    for ring in spec.get("rings", []):
        add_ellipse_walk(
            cx,
            cy,
            rx * ring["sx"],
            ry * ring["sy"],
            rot_deg + ring.get("rot_add", 0.0),
            ring["z"],
            ring["width"],
            ring.get("height", 0.18),
            "Interiors",
            created,
            ring.get("segments", 36),
        )

    for col in spec.get("columns", []):
        add_column_ring(
            cx,
            cy,
            rx,
            ry,
            rot_deg,
            col["sx"],
            col["sy"],
            col["z0"],
            col["height"],
            col["radius"],
            col["angles"],
            "Frame",
            created,
        )

    oculus = spec.get("oculus")
    if oculus:
        add_ellipse_curve(cx, cy, rx * oculus["sx"], ry * oculus["sy"], rot_deg, oculus["z"], "Frame", created, oculus.get("radius", frame_radius_roof * 1.2))

    for portal in spec.get("portals", []):
        add_portal_frame(
            cx,
            cy,
            rx,
            ry,
            rot_deg,
            portal["angle"],
            portal.get("z0", 0.0),
            portal["height"],
            portal["width"],
            portal["depth"],
            portal.get("radius", frame_radius_wall * 1.1),
            created,
        )

    for ribbon in spec.get("ribbons", []):
        add_interior_ribbon(
            cx,
            cy,
            rx * ribbon["sx"],
            ry * ribbon["sy"],
            rot_deg + ribbon.get("rot_add", 0.0),
            ribbon["z0"],
            ribbon["z1"],
            ribbon["a0"],
            ribbon["a1"],
            ribbon["radius"],
            created,
        )


def main():
    rs.EnableRedraw(False)
    ensure_layers()
    created = []

    site_boundary = [
        (-58.0, -21.0),
        (-52.0, 17.0),
        (-40.0, 27.0),
        (-14.0, 33.0),
        (8.0, 36.0),
        (22.0, 32.0),
        (38.0, 30.0),
        (55.0, 20.0),
        (60.0, 4.0),
        (57.0, -13.0),
        (46.0, -24.0),
        (23.0, -29.0),
        (-4.0, -30.0),
        (-22.0, -27.0),
        (-42.0, -26.0),
    ]
    add_polyline_surface(site_boundary, 0.0, "Landscape", created)
    add_low_wall(site_boundary, 0.72, -1.15, 0.15, "Walls", created, True)

    court_poly = [
        (-8.0, -3.0),
        (1.5, -1.2),
        (12.5, -2.6),
        (15.0, -8.2),
        (8.0, -15.0),
        (-3.8, -14.0),
        (-10.5, -8.8),
    ]
    add_polyline_surface(court_poly, 0.18, "Court", created)
    add_polyline_surface([
        (-5.8, -4.6),
        (0.8, -3.8),
        (8.5, -5.0),
        (10.4, -9.0),
        (6.0, -12.8),
        (-2.6, -11.8),
        (-6.8, -8.4),
    ], -0.62, "Court", created)
    add_low_wall(court_poly, 0.42, 0.18, 1.45, "Walls", created, True)
    add_hex_court_lines(created)

    add_railed_path([(-38.0, 9.5), (-12.0, 4.2), (4.0, 2.0), (19.0, 1.4), (34.0, 4.6)], 4.2, 0.55, 2.15, created)
    add_railed_path([(3.8, 1.8), (10.5, -7.4), (18.5, -18.2)], 3.7, 0.55, 2.05, created)
    add_railed_path([(-18.5, 18.2), (-10.0, 25.0)], 2.6, 0.45, 2.55, created)
    add_railed_path([(31.0, 4.1), (40.5, 5.0)], 2.8, 0.45, 2.35, created)
    add_railed_path([(18.8, -18.0), (24.8, -26.8)], 2.3, 0.35, 1.65, created)
    add_planter(-15.0, 3.6, 2.2, 1.2, 2.72, 0.46, created)
    add_planter(2.8, 1.6, 2.0, 1.1, 2.72, 0.46, created)
    add_planter(18.5, 1.4, 2.0, 1.1, 2.72, 0.46, created)
    add_planter(9.0, -7.0, 1.8, 1.0, 2.62, 0.42, created)
    add_stair_run((-1.4, -2.0), (4.1, -9.4), 3.1, 0.20, 2.05, 7, "Bridges", created)
    add_stair_run((17.3, -17.1), (22.6, -24.9), 2.1, 0.10, 1.65, 6, "Bridges", created)
    add_stair_run((-12.0, 4.2), (-8.0, 3.3), 4.0, 1.55, 2.15, 4, "Bridges", created)

    houses = [
        {
            "cx": -32.0,
            "cy": -3.5,
            "rx": 12.8,
            "ry": 9.6,
            "rot": -14.0,
            "wall_h": 5.4,
            "dome_h": 7.2,
            "roof": "low",
            "frame_radius_wall": 0.08,
            "frame_radius_roof": 0.075,
            "ring_radius": 0.095,
            "radials": [0.0, 28.0, 56.0, 84.0, 112.0, 140.0],
            "extra_radials": [14.0, 42.0, 70.0, 98.0, 126.0, 154.0],
            "oblique": [8.0, 40.0, 72.0, 104.0],
            "brace_rings": [1.2, 2.8, 4.5, 5.4],
            "rings": [
                {"sx": 0.74, "sy": 0.66, "z": 2.25, "width": 0.86},
                {"sx": 0.45, "sy": 0.40, "z": 4.85, "width": 0.72, "height": 0.16},
            ],
            "columns": [
                {"sx": 0.72, "sy": 0.60, "z0": 0.05, "height": 4.95, "radius": 0.12, "angles": [15.0, 95.0, 180.0, 260.0]},
            ],
            "oculus": {"sx": 0.14, "sy": 0.12, "z": 11.15, "radius": 0.09},
            "portals": [
                {"angle": 244.0, "height": 2.6, "width": 2.8, "depth": 0.7},
            ],
            "ribbons": [
                {"sx": 0.62, "sy": 0.55, "z0": 2.6, "z1": 4.9, "a0": 220.0, "a1": 20.0, "radius": 0.28},
            ],
        },
        {
            "cx": -26.5,
            "cy": 14.0,
            "rx": 15.4,
            "ry": 11.6,
            "rot": -9.0,
            "wall_h": 6.6,
            "dome_h": 8.8,
            "roof": "round",
            "frame_radius_wall": 0.085,
            "frame_radius_roof": 0.078,
            "ring_radius": 0.10,
            "radials": [0.0, 24.0, 48.0, 72.0, 96.0, 120.0, 144.0],
            "extra_radials": [12.0, 36.0, 60.0, 84.0, 108.0, 132.0, 156.0],
            "oblique": [10.0, 34.0, 58.0, 82.0, 106.0],
            "brace_rings": [1.5, 3.2, 5.0, 6.6],
            "rings": [
                {"sx": 0.76, "sy": 0.68, "z": 2.95, "width": 0.94},
                {"sx": 0.48, "sy": 0.42, "z": 5.95, "width": 0.76, "height": 0.16},
            ],
            "columns": [
                {"sx": 0.72, "sy": 0.62, "z0": 0.05, "height": 5.9, "radius": 0.14, "angles": [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]},
            ],
            "oculus": {"sx": 0.15, "sy": 0.13, "z": 13.8, "radius": 0.095},
            "portals": [
                {"angle": 344.0, "height": 2.9, "width": 3.0, "depth": 0.8},
                {"angle": 245.0, "height": 2.5, "width": 2.4, "depth": 0.7, "radius": 0.08},
            ],
            "ribbons": [
                {"sx": 0.60, "sy": 0.54, "z0": 3.0, "z1": 6.0, "a0": 195.0, "a1": 22.0, "radius": 0.30},
            ],
        },
        {
            "cx": 1.5,
            "cy": 20.0,
            "rx": 20.8,
            "ry": 14.2,
            "rot": 8.0,
            "wall_h": 11.0,
            "dome_h": 9.0,
            "roof": "flat",
            "frame_radius_wall": 0.10,
            "frame_radius_roof": 0.09,
            "ring_radius": 0.115,
            "radials": [0.0, 22.0, 44.0, 66.0, 88.0, 110.0, 132.0, 154.0],
            "extra_radials": [11.0, 33.0, 55.0, 77.0, 99.0, 121.0, 143.0, 165.0],
            "oblique": [8.0, 28.0, 48.0, 68.0, 88.0, 108.0],
            "brace_rings": [2.0, 4.2, 6.5, 8.6, 11.0],
            "rings": [
                {"sx": 0.78, "sy": 0.60, "z": 4.15, "width": 1.12},
                {"sx": 0.52, "sy": 0.38, "z": 8.30, "width": 0.84, "height": 0.16},
            ],
            "columns": [
                {"sx": 0.75, "sy": 0.61, "z0": 0.05, "height": 8.8, "radius": 0.16, "angles": [5.0, 50.0, 95.0, 140.0, 185.0, 230.0, 275.0, 320.0]},
            ],
            "oculus": {"sx": 0.19, "sy": 0.14, "z": 18.9, "radius": 0.11},
            "portals": [
                {"angle": 212.0, "height": 3.1, "width": 3.4, "depth": 0.9},
                {"angle": 332.0, "height": 3.0, "width": 3.0, "depth": 0.8},
            ],
            "ribbons": [
                {"sx": 0.68, "sy": 0.51, "z0": 4.2, "z1": 9.0, "a0": 215.0, "a1": 10.0, "radius": 0.34},
                {"sx": 0.44, "sy": 0.34, "z0": 7.6, "z1": 11.8, "a0": 182.0, "a1": 350.0, "radius": 0.22},
            ],
        },
        {
            "cx": 20.0,
            "cy": 9.5,
            "rx": 16.2,
            "ry": 13.2,
            "rot": 12.0,
            "wall_h": 12.8,
            "dome_h": 13.8,
            "roof": "pointed",
            "frame_radius_wall": 0.105,
            "frame_radius_roof": 0.095,
            "ring_radius": 0.12,
            "radials": [0.0, 20.0, 40.0, 60.0, 80.0, 100.0, 120.0, 140.0, 160.0],
            "extra_radials": [10.0, 30.0, 50.0, 70.0, 90.0, 110.0, 130.0, 150.0, 170.0],
            "oblique": [6.0, 24.0, 42.0, 60.0, 78.0, 96.0, 114.0],
            "brace_rings": [2.2, 5.0, 7.8, 10.5, 12.8],
            "rings": [
                {"sx": 0.76, "sy": 0.62, "z": 5.15, "width": 1.08},
                {"sx": 0.50, "sy": 0.40, "z": 10.15, "width": 0.82, "height": 0.16},
            ],
            "columns": [
                {"sx": 0.74, "sy": 0.60, "z0": 0.05, "height": 10.6, "radius": 0.16, "angles": [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]},
            ],
            "oculus": {"sx": 0.14, "sy": 0.11, "z": 24.9, "radius": 0.12},
            "portals": [
                {"angle": 190.0, "height": 3.4, "width": 3.2, "depth": 0.95},
                {"angle": 350.0, "height": 3.0, "width": 2.6, "depth": 0.8},
            ],
            "ribbons": [
                {"sx": 0.70, "sy": 0.58, "z0": 5.0, "z1": 11.2, "a0": 210.0, "a1": 5.0, "radius": 0.34},
                {"sx": 0.46, "sy": 0.36, "z0": 10.2, "z1": 15.4, "a0": 195.0, "a1": 6.0, "radius": 0.22},
            ],
        },
        {
            "cx": 45.0,
            "cy": 7.8,
            "rx": 15.4,
            "ry": 12.1,
            "rot": 5.0,
            "wall_h": 10.0,
            "dome_h": 11.0,
            "roof": "round",
            "frame_radius_wall": 0.095,
            "frame_radius_roof": 0.086,
            "ring_radius": 0.11,
            "radials": [0.0, 24.0, 48.0, 72.0, 96.0, 120.0, 144.0],
            "extra_radials": [12.0, 36.0, 60.0, 84.0, 108.0, 132.0, 156.0],
            "oblique": [8.0, 32.0, 56.0, 80.0, 104.0],
            "brace_rings": [1.8, 4.1, 6.4, 8.3, 10.0],
            "rings": [
                {"sx": 0.76, "sy": 0.62, "z": 4.35, "width": 0.98},
                {"sx": 0.48, "sy": 0.38, "z": 8.35, "width": 0.78, "height": 0.16},
            ],
            "columns": [
                {"sx": 0.74, "sy": 0.60, "z0": 0.05, "height": 8.6, "radius": 0.15, "angles": [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]},
            ],
            "oculus": {"sx": 0.16, "sy": 0.13, "z": 18.8, "radius": 0.105},
            "portals": [
                {"angle": 192.0, "height": 3.0, "width": 3.1, "depth": 0.85},
                {"angle": 354.0, "height": 2.8, "width": 2.5, "depth": 0.7},
            ],
            "ribbons": [
                {"sx": 0.66, "sy": 0.53, "z0": 4.4, "z1": 8.6, "a0": 200.0, "a1": 18.0, "radius": 0.32},
            ],
        },
        {
            "cx": 19.0,
            "cy": -20.0,
            "rx": 11.6,
            "ry": 8.8,
            "rot": -6.0,
            "wall_h": 5.6,
            "dome_h": 6.8,
            "roof": "low",
            "frame_radius_wall": 0.08,
            "frame_radius_roof": 0.074,
            "ring_radius": 0.09,
            "radials": [0.0, 30.0, 60.0, 90.0, 120.0, 150.0],
            "extra_radials": [15.0, 45.0, 75.0, 105.0, 135.0, 165.0],
            "oblique": [12.0, 42.0, 72.0, 102.0],
            "brace_rings": [1.2, 2.8, 4.2, 5.6],
            "rings": [
                {"sx": 0.74, "sy": 0.64, "z": 2.35, "width": 0.84},
            ],
            "columns": [
                {"sx": 0.70, "sy": 0.58, "z0": 0.05, "height": 5.0, "radius": 0.12, "angles": [20.0, 110.0, 200.0, 290.0]},
            ],
            "oculus": {"sx": 0.15, "sy": 0.12, "z": 10.9, "radius": 0.085},
            "portals": [
                {"angle": 20.0, "height": 2.5, "width": 2.6, "depth": 0.7},
            ],
            "ribbons": [
                {"sx": 0.58, "sy": 0.50, "z0": 2.7, "z1": 5.0, "a0": 215.0, "a1": 25.0, "radius": 0.28},
            ],
        },
    ]

    for spec in houses:
        add_greenhouse(spec, created)

    add_box(23.0, 28.2, 0.6, 4.6, 0.0, 3.6, "EntryBlocks", created)
    add_box(46.8, 51.8, 2.0, 5.2, 0.0, 3.1, "EntryBlocks", created)
    add_box(21.5, 26.3, -22.4, -18.7, 0.0, 3.0, "EntryBlocks", created)
    add_box(-2.0, 1.2, 27.6, 31.2, 0.0, 2.9, "EntryBlocks", created)
    add_box(20.8, 27.0, 0.2, 1.4, 2.45, 2.82, "EntryBlocks", created)
    add_box(46.2, 50.8, 4.7, 6.0, 2.25, 2.60, "EntryBlocks", created)
    add_box(20.2, 23.0, -18.6, -17.2, 1.65, 2.00, "EntryBlocks", created)

    add_path([(-58.0, -19.8), (-46.0, -22.4), (-30.0, -24.0), (-10.0, -27.2), (8.0, -28.0)], 2.5, 0.18, 0.08, "Site", created)
    add_path([(-56.0, 16.2), (-48.0, 22.0), (-38.0, 26.0)], 2.1, 0.18, 0.08, "Site", created)

    rs.UnselectAllObjects()
    if created:
        rs.SelectObjects(created)
    rs.EnableRedraw(True)
    rs.Redraw()


try:
    main()
except Exception:
    log_path = r"C:\Users\Admin\AppData\Local\RhinoMCP\accurate_glasshouse_error.log"
    message = traceback.format_exc()
    handle = open(log_path, "w")
    handle.write(message)
    handle.close()
    print(message)
