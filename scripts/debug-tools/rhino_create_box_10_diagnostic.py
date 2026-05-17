import json
import traceback

import Rhino
import scriptcontext as sc
from Rhino.Geometry import BoundingBox
from Rhino.Geometry import Box
from Rhino.Geometry import Point3d

result = {}
output_path = r"C:\Users\Admin\Documents\Codex\2026-05-07\i-want-u-create-shortcut-of\rhino_create_box_10_result.json"

try:
    doc = sc.doc
    result["doc_name"] = doc.Name
    result["object_count_before"] = doc.Objects.Count

    bbox = BoundingBox(Point3d(0, 0, 0), Point3d(10, 10, 10))
    box = Box(bbox)
    brep = box.ToBrep()

    result["bbox_is_valid"] = bbox.IsValid
    result["box_is_valid"] = box.IsValid
    result["brep_is_none"] = brep is None

    obj_id = doc.Objects.AddBrep(brep)
    result["object_id"] = str(obj_id)

    doc.Views.Redraw()
    result["object_count_after"] = doc.Objects.Count
except Exception:
    result["error"] = traceback.format_exc()

with open(output_path, "w") as f:
    json.dump(result, f, indent=2)

print(output_path)
