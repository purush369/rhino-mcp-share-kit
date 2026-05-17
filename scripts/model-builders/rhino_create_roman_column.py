import math

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System

from Rhino.DocObjects import ObjectAttributes
from Rhino.Geometry import Box
from Rhino.Geometry import Brep
from Rhino.Geometry import Circle
from Rhino.Geometry import Cylinder
from Rhino.Geometry import Interval
from Rhino.Geometry import LoftType
from Rhino.Geometry import Plane
from Rhino.Geometry import Point3d
from Rhino.Geometry import Vector3d
from System.Drawing import Color


LAYER_NAME = "RomanColumn_20260509"
OBJECT_NAME = "RomanColumn"

CX = 20.0
CY = 5.0

PLINTH_HALF = 2.1
PLINTH_HEIGHT = 0.55

BASE_LOWER_RADIUS = 1.55
BASE_LOWER_HEIGHT = 0.30
BASE_UPPER_RADIUS = 1.35
BASE_UPPER_HEIGHT = 0.40

SHAFT_RADIUS = 1.10
SHAFT_HEIGHT = 11.60
FLUTE_COUNT = 12
FLUTE_RADIUS = 0.18
FLUTE_CENTER_RADIUS = 0.98

NECK_RADIUS = 1.18
NECK_HEIGHT = 0.22
ECHINUS_BOTTOM_RADIUS = 1.18
ECHINUS_TOP_RADIUS = 1.72
ECHINUS_HEIGHT = 0.85
ABACUS_HALF = 1.95
ABACUS_HEIGHT = 0.42


def ensure_layer():
    if rs.IsLayer(LAYER_NAME):
        for obj_id in rs.ObjectsByLayer(LAYER_NAME, True) or []:
            rs.DeleteObject(obj_id)
    else:
        rs.AddLayer(LAYER_NAME, Color.FromArgb(201, 180, 142))
    return sc.doc.Layers.FindByFullPath(LAYER_NAME, Rhino.RhinoMath.UnsetIntIndex)


def make_attributes(layer_index):
    attr = ObjectAttributes()
    attr.LayerIndex = layer_index
    attr.Name = OBJECT_NAME
    return attr


def add_brep(brep, attr):
    if brep is None:
        return System.Guid.Empty
    return sc.doc.Objects.AddBrep(brep, attr)


def make_box_brep(cx, cy, half, z0, z1):
    return Box(
        Plane.WorldXY,
        Interval(cx - half, cx + half),
        Interval(cy - half, cy + half),
        Interval(z0, z1),
    ).ToBrep()


def make_cylinder_brep(cx, cy, z0, height, radius):
    circle = Circle(Plane(Point3d(cx, cy, z0), Vector3d.ZAxis), radius)
    return Cylinder(circle, height).ToBrep(True, True)


def make_loft_brep(cx, cy, z0, z1, r0, r1, tol):
    c0 = Circle(Plane(Point3d(cx, cy, z0), Vector3d.ZAxis), r0).ToNurbsCurve()
    c1 = Circle(Plane(Point3d(cx, cy, z1), Vector3d.ZAxis), r1).ToNurbsCurve()
    lofts = Brep.CreateFromLoft([c0, c1], Point3d.Unset, Point3d.Unset, LoftType.Normal, False)
    if not lofts:
        return None
    capped = lofts[0].CapPlanarHoles(tol)
    return capped if capped else lofts[0]


def flute_shaft(shaft_brep, z0, height, tol):
    cutters = []
    cutter_height = height + 0.12
    cutter_z = z0 - 0.06
    for i in range(FLUTE_COUNT):
        angle = (2.0 * math.pi * i) / FLUTE_COUNT
        px = CX + math.cos(angle) * FLUTE_CENTER_RADIUS
        py = CY + math.sin(angle) * FLUTE_CENTER_RADIUS
        cutter = make_cylinder_brep(px, py, cutter_z, cutter_height, FLUTE_RADIUS)
        if cutter is not None:
            cutters.append(cutter)

    if not cutters:
        return shaft_brep

    result = Brep.CreateBooleanDifference([shaft_brep], cutters, tol)
    if result and len(result) > 0:
        return result[0]
    return shaft_brep


def main():
    tol = sc.doc.ModelAbsoluteTolerance
    layer_index = ensure_layer()
    attr = make_attributes(layer_index)

    created_ids = []
    z = 0.0

    plinth_id = add_brep(make_box_brep(CX, CY, PLINTH_HALF, z, z + PLINTH_HEIGHT), attr)
    if plinth_id != System.Guid.Empty:
        created_ids.append(plinth_id)
    z += PLINTH_HEIGHT - 0.02

    lower_base_id = add_brep(make_cylinder_brep(CX, CY, z, BASE_LOWER_HEIGHT, BASE_LOWER_RADIUS), attr)
    if lower_base_id != System.Guid.Empty:
        created_ids.append(lower_base_id)
    z += BASE_LOWER_HEIGHT - 0.02

    upper_base_id = add_brep(make_cylinder_brep(CX, CY, z, BASE_UPPER_HEIGHT, BASE_UPPER_RADIUS), attr)
    if upper_base_id != System.Guid.Empty:
        created_ids.append(upper_base_id)
    z += BASE_UPPER_HEIGHT - 0.02

    shaft_brep = make_cylinder_brep(CX, CY, z, SHAFT_HEIGHT, SHAFT_RADIUS)
    shaft_brep = flute_shaft(shaft_brep, z, SHAFT_HEIGHT, tol)
    shaft_id = add_brep(shaft_brep, attr)
    if shaft_id != System.Guid.Empty:
        created_ids.append(shaft_id)
    z += SHAFT_HEIGHT - 0.02

    neck_id = add_brep(make_cylinder_brep(CX, CY, z, NECK_HEIGHT, NECK_RADIUS), attr)
    if neck_id != System.Guid.Empty:
        created_ids.append(neck_id)
    z += NECK_HEIGHT - 0.02

    echinus_id = add_brep(
        make_loft_brep(CX, CY, z, z + ECHINUS_HEIGHT, ECHINUS_BOTTOM_RADIUS, ECHINUS_TOP_RADIUS, tol),
        attr,
    )
    if echinus_id != System.Guid.Empty:
        created_ids.append(echinus_id)
    z += ECHINUS_HEIGHT - 0.02

    abacus_id = add_brep(make_box_brep(CX, CY, ABACUS_HALF, z, z + ABACUS_HEIGHT), attr)
    if abacus_id != System.Guid.Empty:
        created_ids.append(abacus_id)

    group_name = rs.AddGroup(LAYER_NAME + "_group")
    if group_name:
        rs.AddObjectsToGroup(created_ids, group_name)

    rs.SelectObjects(created_ids)
    sc.doc.Views.Redraw()


main()
