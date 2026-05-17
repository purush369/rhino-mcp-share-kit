import rhinoscriptsyntax as rs


def ensure_layer(name, color=None):
    if rs.IsLayer(name):
        return name
    return rs.AddLayer(name, color)


def main():
    rs.EnableRedraw(False)

    layer = ensure_layer("RhinoMcpDemo")
    rs.CurrentLayer(layer)

    created = []

    base = rs.AddBox([
        (0, 0, 0),
        (24, 0, 0),
        (24, 24, 0),
        (0, 24, 0),
        (0, 0, 2),
        (24, 0, 2),
        (24, 24, 2),
        (0, 24, 2),
    ])
    rs.ObjectName(base, "DemoBase")
    created.append(base)

    box = rs.AddBox([
        (5, 5, 2),
        (15, 5, 2),
        (15, 15, 2),
        (5, 15, 2),
        (5, 5, 12),
        (15, 5, 12),
        (15, 15, 12),
        (5, 15, 12),
    ])
    rs.ObjectName(box, "DemoBox")
    created.append(box)

    cylinder = rs.AddCylinder((19, 8, 2), 10, 3)
    rs.ObjectName(cylinder, "DemoCylinder")
    created.append(cylinder)

    sphere = rs.AddSphere((19, 18, 7), 4)
    rs.ObjectName(sphere, "DemoSphere")
    created.append(sphere)

    curve = rs.AddInterpCurve([
        (0, -6, 0),
        (8, -4, 2),
        (16, -8, 3),
        (24, -6, 0),
    ])
    rs.ObjectName(curve, "DemoCurve")
    created.append(curve)

    dot = rs.AddTextDot("Rhino MCP Demo", (12, 12, 16))
    rs.ObjectName(dot, "DemoLabel")
    created.append(dot)

    rs.SelectObjects(created)
    rs.Command("_Zoom _Selected", echo=False)
    rs.EnableRedraw(True)

    print("Created Rhino MCP demo scene with {0} objects.".format(len(created)))


if __name__ == "__main__":
    main()
