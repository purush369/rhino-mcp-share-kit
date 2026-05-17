import math

import rhinoscriptsyntax as rs


ROOT = "ExplodedPavilion_20260509"
LAYER_COLORS = {
    "Base": (220, 220, 220),
    "Frame": (165, 165, 165),
    "Ring": (205, 205, 205),
    "Panels": (198, 145, 44),
    "LowerDome": (145, 145, 145),
    "UpperDome": (110, 110, 110),
    "Finial": (80, 80, 80),
}

CX = 60.0
CY = 0.0


def full_layer(name):
    return ROOT + "::" + name


def ensure_layers():
    if not rs.IsLayer(ROOT):
        rs.AddLayer(ROOT, (200, 200, 200))
    for name, color in LAYER_COLORS.items():
        path = full_layer(name)
        if not rs.IsLayer(path):
            rs.AddLayer(name, color, parent=ROOT)
        rs.LayerColor(path, color)
        objs = rs.ObjectsByLayer(path, True) or []
        if objs:
            rs.DeleteObjects(objs)


def pt(radius, angle, z):
    return (
        CX + radius * math.cos(angle),
        CY + radius * math.sin(angle),
        z,
    )


def as_ids(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    return [value]


def put_on_layer(obj, layer_name, created):
    ids = as_ids(obj)
    layer = full_layer(layer_name)
    for obj_id in ids:
        rs.ObjectLayer(obj_id, layer)
        created.append(obj_id)
    return ids


def pipe_curve(curve_id, radius, layer_name, created):
    pipe = rs.AddPipe(curve_id, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve_id)
    return put_on_layer(pipe, layer_name, created)


def add_ring(radius, z, pipe_radius, layer_name, created):
    curve = rs.AddCircle((CX, CY, z), radius)
    return pipe_curve(curve, pipe_radius, layer_name, created)


def add_arc_member(p0, p1, p2, radius, layer_name, created):
    curve = rs.AddArc3Pt(p0, p1, p2)
    return pipe_curve(curve, radius, layer_name, created)


def add_line_member(p0, p1, radius, layer_name, created):
    curve = rs.AddLine(p0, p1)
    return pipe_curve(curve, radius, layer_name, created)


def build_base(created):
    layer = full_layer("Base")
    slab = rs.AddBox([
        (CX - 14, CY - 14, 0),
        (CX + 14, CY - 14, 0),
        (CX + 14, CY + 14, 0),
        (CX - 14, CY + 14, 0),
        (CX - 14, CY - 14, 1.0),
        (CX + 14, CY - 14, 1.0),
        (CX + 14, CY + 14, 1.0),
        (CX - 14, CY + 14, 1.0),
    ])
    podium = rs.AddBox([
        (CX - 8, CY - 8, 1.0),
        (CX + 8, CY - 8, 1.0),
        (CX + 8, CY + 8, 1.0),
        (CX - 8, CY + 8, 1.0),
        (CX - 8, CY - 8, 2.0),
        (CX + 8, CY - 8, 2.0),
        (CX + 8, CY + 8, 2.0),
        (CX - 8, CY + 8, 2.0),
    ])
    stair = rs.AddBox([
        (CX - 4, CY - 12, 1.0),
        (CX + 4, CY - 12, 1.0),
        (CX + 4, CY - 8, 1.0),
        (CX - 4, CY - 8, 1.0),
        (CX - 4, CY - 12, 1.6),
        (CX + 4, CY - 12, 1.6),
        (CX + 4, CY - 8, 1.6),
        (CX - 4, CY - 8, 1.6),
    ])
    for obj in [slab, podium, stair]:
        if obj:
            rs.ObjectLayer(obj, layer)
            created.append(obj)


def build_frame(created):
    count = 12
    radius = 10.0
    step = (2.0 * math.pi) / count
    top_z = 11.0
    outer_ring_z = 12.4

    for i in range(count):
        angle = i * step
        x = CX + radius * math.cos(angle)
        y = CY + radius * math.sin(angle)
        col = rs.AddCylinder((x, y, 1.0), 10.0, 0.28, True)
        cap = rs.AddCylinder((x, y, 10.9), 0.35, 0.42, True)
        base = rs.AddCylinder((x, y, 1.0), 0.35, 0.44, True)
        put_on_layer(col, "Frame", created)
        put_on_layer(cap, "Frame", created)
        put_on_layer(base, "Frame", created)

    add_ring(10.05, 11.2, 0.16, "Frame", created)
    add_ring(11.3, outer_ring_z, 0.09, "Frame", created)

    for i in range(count):
        angle = i * step
        top = pt(10.05, angle, top_z)
        left = pt(11.3, angle - step * 0.45, outer_ring_z)
        right = pt(11.3, angle + step * 0.45, outer_ring_z)
        add_line_member(top, left, 0.06, "Frame", created)
        add_line_member(top, right, 0.06, "Frame", created)


def build_ring(created):
    add_ring(9.7, 14.7, 0.08, "Ring", created)


def build_panels(created):
    count = 16
    step = (2.0 * math.pi) / count
    layer = full_layer("Panels")
    for i in range(count):
        angle = i * step
        outer_left = pt(9.1, angle - step * 0.38, 17.2)
        outer_right = pt(9.1, angle + step * 0.38, 17.2)
        inner_right = pt(5.8, angle + step * 0.20, 19.6)
        inner_left = pt(5.8, angle - step * 0.20, 19.6)
        panel = rs.AddSrfPt([outer_left, outer_right, inner_right, inner_left])
        if panel:
            rs.ObjectLayer(panel, layer)
            created.append(panel)

        tip_a = pt(4.9, angle - step * 0.12, 16.8)
        tip_b = pt(4.2, angle, 16.2)
        tip_c = pt(4.9, angle + step * 0.12, 16.8)
        tri = rs.AddSrfPt([tip_a, tip_b, tip_c])
        if tri:
            rs.ObjectLayer(tri, layer)
            created.append(tri)


def build_lower_dome(created):
    count = 12
    step = (2.0 * math.pi) / count
    base_r = 10.0
    crown_r = 2.6
    z0 = 21.6
    z1 = 26.4

    add_ring(crown_r, z1, 0.06, "LowerDome", created)

    for i in range(count):
        angle = i * step
        start_a = pt(base_r, angle, z0)
        mid_a = pt(5.4, angle + step * 0.22, z0 + 4.0)
        end_a = pt(crown_r, angle + step * 0.50, z1)
        add_arc_member(start_a, mid_a, end_a, 0.08, "LowerDome", created)

        start_b = pt(base_r, angle + step * 0.50, z0)
        mid_b = pt(5.0, angle + step * 0.25, z0 + 3.5)
        end_b = pt(crown_r, angle, z1 - 0.2)
        add_arc_member(start_b, mid_b, end_b, 0.08, "LowerDome", created)


def build_upper_dome(created):
    count = 12
    step = (2.0 * math.pi) / count
    base_r = 7.6
    crown_r = 0.95
    z0 = 28.0
    z1 = 33.0

    add_ring(crown_r, z1, 0.05, "UpperDome", created)

    for i in range(count):
        angle = i * step
        start_a = pt(base_r, angle, z0)
        mid_a = pt(4.2, angle + step * 0.20, z0 + 3.7)
        end_a = pt(crown_r, angle + step * 0.45, z1)
        add_arc_member(start_a, mid_a, end_a, 0.07, "UpperDome", created)

        start_b = pt(base_r, angle + step * 0.50, z0)
        mid_b = pt(4.0, angle + step * 0.25, z0 + 3.1)
        end_b = pt(crown_r, angle, z1 - 0.15)
        add_arc_member(start_b, mid_b, end_b, 0.07, "UpperDome", created)


def build_finial(created):
    stem = rs.AddCylinder((CX, CY, 33.0), 1.3, 0.09, True)
    disc = rs.AddCylinder((CX, CY, 34.2), 0.14, 0.55, True)
    halo = rs.AddCircle((CX, CY, 34.33), 0.78)
    put_on_layer(stem, "Finial", created)
    put_on_layer(disc, "Finial", created)
    pipe_curve(halo, 0.05, "Finial", created)


def main():
    rs.EnableRedraw(False)
    ensure_layers()

    created = []
    build_base(created)
    build_frame(created)
    build_ring(created)
    build_panels(created)
    build_lower_dome(created)
    build_upper_dome(created)
    build_finial(created)

    if created:
        group = rs.AddGroup(ROOT + "_group")
        if group:
            rs.AddObjectsToGroup(created, group)
        rs.UnselectAllObjects()
        rs.SelectObjects(created)

    rs.EnableRedraw(True)
    rs.Redraw()


main()
