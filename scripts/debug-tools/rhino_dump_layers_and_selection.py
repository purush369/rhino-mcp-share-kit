import json

import scriptcontext as sc

output_path = r"C:\Users\Admin\Documents\Codex\2026-05-07\i-want-u-create-shortcut-of\rhino_dump_layers_and_selection.json"

doc = sc.doc

layers = []
for layer in doc.Layers:
    if layer:
        layers.append({
            "name": layer.Name,
            "full_path": layer.FullPath,
            "index": layer.LayerIndex,
            "is_deleted": layer.IsDeleted,
        })

selected = []
for obj in doc.Objects.GetSelectedObjects(False, False):
    selected.append({
        "id": str(obj.Id),
        "name": obj.Name,
        "layer_index": obj.Attributes.LayerIndex,
    })

payload = {
    "layer_count": len(layers),
    "layers": layers,
    "selection_count": len(selected),
    "selection": selected,
}

with open(output_path, "w") as f:
    json.dump(payload, f, indent=2)

print(output_path)
