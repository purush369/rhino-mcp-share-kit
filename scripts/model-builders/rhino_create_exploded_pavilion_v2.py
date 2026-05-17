import math

import rhinoscriptsyntax as rs


LAYER_PREFIX = "ExplodedPavilionV2"
STRUCT_COLOR = (155, 155, 155)
PANEL_COLOR = (196, 145, 46)
TOP_COLOR = (90, 90, 90)

CX = 60.0
CY = 0.0


def layer_name(suffix):
    return LAYER_PREFIX + "_" + suffix


def ensure_layer(name, color):
    if not rs.IsLayer(name):
        rs.AddLayer(name, color)
    objs = rs.ObjectsByLayer(name, True) or []
    if objs:
        rs.DeleteObjects(objs)
    return name


def polar(radius, angle, z):
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


def assign(obj, layer, name, created):
    ids = as_ids(obj)
    for obj_id in ids:
        rs.ObjectLayer(obj_id, layer)
        rs.ObjectName(obj_id, name)
        created.append(obj_id)
    return ids


def pipe_curve(curve_id, radius, layer, name, created):
    result = rs.AddPipe(curve_id, [0.0, 1.0], [radius, radius], cap=2)
    rs.DeleteObject(curve_id)
    return assign(result, layer, name, created)


def add_ring(radius, z, pipe_radius, layer, name, created):
    curve = rs.AddCircle((CX, CY, z), radius)
    return pipe_curve(curve, pipe_radius, layer, name, created)


def add_arc(start, mid, end, radius, layer, name, created):
    curve = rs.AddArc3Pt(start, mid, end)
    return pipe_curve(curve, radius, layer, name, created)


def add_line(start, end, radius, layer, name, created):
    curve = rs.AddLine(start, end)
    return pipe_curve(curve, radius, layer, name, created)


def main():
    rs.EnableRedraw(False)

    base_layer = ensure_layer(layer_name("Base"), (220, 220, 220))
    frame_layer = ensure_layer(layer_name("Frame"), STRUCT_COLOR)
    ring_layer = ensure_layer(layer_name("Ring"), (205, 205, 205))
    panel_layer = ensure_layer(layer_name("Panels"), PANEL_COLOR)
    lower_layer = ensure_layer(layer_name("LowerDome"), STRUCT_COLOR)
    upper_layer = ensure_layer(layer_name("UpperDome"), TOP_COLOR)
    finial_layer = ensure_layer(layer_name("Finial"), TOP_COLOR)

    created = []

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
    assign([slab, podium], base_layer, "ExplodedPavilion", created)

    count = 10
    step = (2.0 * math.pi) / count
    frame_radius = 9.8

    for i in range(count):
        angle = i * step
        x = CX + frame_radius * math.cos(angle)
        y = CY + frame_radius * math.sin(angle)
        column = rs.AddCylinder((x, y, 1.0), 9.8, 0.26, True)
        cap = rs.AddCylinder((x, y, 10.6), 0.35, 0.40, True)
        assign([column, cap], frame_layer, "ExplodedPavilion", created)

    add_ring(9.9, 11.0, 0.14, frame_layer, "ExplodedPavilion", created)
    add_ring(10.9, 12.2, 0.08, frame_layer, "ExplodedPavilion", created)

    for i in range(count):
        angle = i * step
        top = polar(9.9, angle, 10.8)
        left = polar(10.9, angle - step * 0.45, 12.2)
        right = polar(10.9, angle + step * 0.45, 12.2)
        add_line(top, left, 0.05, frame_layer, "ExplodedPavilion", created)
        add_line(top, right, 0.05, frame_layer, "ExplodedPavilion", created)

    add_ring(9.5, 14.7, 0.07, ring_layer, "ExplodedPavilion", created)

    panel_count = 12
    panel_step = (2.0 * math.pi) / panel_count
    for i in range(panel_count):
        angle = i * panel_step
        p1 = polar(8.9, angle - panel_step * 0.36, 17.1)
        p2 = polar(8.9, angle + panel_step * 0.36, 17.1)
        p3 = polar(5.7, angle + panel_step * 0.18, 19.3)
        p4 = polar(5.7, angle - panel_step * 0.18, 19.3)
        panel = rs.AddSrfPt([p1, p2, p3, p4])
        assign(panel, panel_layer, "ExplodedPavilion", created)

    dome_count = 10
    dome_step = (2.0 * math.pi) / dome_count

    add_ring(2.4, 26.0, 0.05, lower_layer, "ExplodedPavilion", created)
    for i in range(dome_count):
        angle = i * dome_step
        add_arc(
            polar(9.6, angle, 21.4),
            polar(5.1, angle + dome_step * 0.22, 25.0),
            polar(2.4, angle + dome_step * 0.45, 26.0),
            0.07,
            lower_layer,
            "ExplodedPavilion",
            created,
        )
        add_arc(
            polar(9.6, angle + dome_step * 0.5, 21.4),
            polar(4.9, angle + dome_step * 0.24, 24.5),
            polar(2.4, angle, 25.8),
            0.07,
            lower_layer,
            "ExplodedPavilion",
            created,
        )

    add_ring(0.85, 32.2, 0.05, upper_layer, "ExplodedPavilion", created)
    for i in range(dome_count):
        angle = i * dome_step
        add_arc(
            polar(7.3, angle, 27.8),
            polar(4.0, angle + dome_step * 0.20, 31.0),
            polar(0.85, angle + dome_step * 0.42, 32.2),
            0.06,
            upper_layer,
            "ExplodedPavilion",
            created,
        )

    stem = rs.AddCylinder((CX, CY, 32.2), 1.3, 0.08, True)
    disc = rs.AddCylinder((CX, CY, 33.8), 0.12, 0.50, True)
    assign([stem, disc], finial_layer, "ExplodedPavilion", created)
    add_ring(0.72, 33.9, 0.04, finial_layer, "ExplodedPavilion", created)

    rs.UnselectAllObjects()
    if created:
        rs.SelectObjects(created)

    rs.EnableRedraw(True)
    rs.Redraw()


main()
