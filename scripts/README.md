# Scripts

## Setup Helpers

- `load_rhino_mcp_portable.py`
  Portable Rhino-side loader that finds the installed `RhinoMcpPlatform.rhp`, loads it, and runs `RhinoMCP`.
- `create_demo_rhino_scene.py`
  Builds a small Rhino MCP demo scene that is safe to include in a GitHub repo.
- `build_demo_file_for_release.py`
  Rhino-side helper that creates the demo scene in a fresh document and saves `examples/demo-files/rhino_mcp_demo_scene.3dm`.
- `install_codex_rhino_marketplace.ps1`
  Copies the bundled Codex Rhino marketplace into the current user's `.codex` folder and adds the required config snippet if missing.
- `install_claude_rhino_marketplace.ps1`
  Copies the bundled Claude marketplace into the current user's `.claude` folder, enables the plugin, and attempts to register the Rhino MCP server.

## Model Builders

- `rhino_create_box_10.py`
  Simple test box at the origin.
- `rhino_create_roman_column.py`
  Roman-style column study.
- `rhino_create_exploded_pavilion.py`
  Early exploded pavilion study.
- `rhino_create_exploded_pavilion_v2.py`
  Refined exploded pavilion study.
- `rhino_create_detailed_lagoon_park.py`
  Detailed lagoon-park environment inspired by the reference image.
- `rhino_create_accurate_glasshouse_cluster.py`
  Multi-volume glasshouse cluster study.
- `rhino_create_world_garden_globe.py`
  Globe conservatory concept.
- `rhino_create_precise_ornament_column.py`
  Ornament column based on the provided drawing.
- `rhino_create_london_isometric_cluster.py`
  Stylized London landmark cluster.

## Debug Tools

- `rhino_create_box_10_diagnostic.py`
  Diagnostic variant used while validating Rhino connectivity.
- `rhino_delete_extra_box.py`
  Cleanup helper for removing an extra test box.
- `rhino_dump_layers_and_selection.py`
  Dumps Rhino layer/selection state for debugging.
