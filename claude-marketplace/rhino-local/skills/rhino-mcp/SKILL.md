---
name: rhino-mcp
description: Use Rhino through a local Rhino MCP server. Trigger when the user asks to create, edit, inspect, select, render, screenshot, save, or organize geometry in Rhino, or when they mention RhinoMCP, localhost:4862, or Rhino viewport capture.
---

# Rhino MCP

Use this skill when Claude is working against a live Rhino session through the `rhino` MCP server.

## Preconditions

Before using Rhino tools, make sure:

1. Rhino is open.
2. The `RhinoMCP` command has been run in Rhino.
3. The local MCP server is available at `http://localhost:4862/`.

If Rhino is not responding, ask the user to:

1. Open Rhino.
2. Run `RhinoMCP`.
3. Restart Claude if the `rhino` server does not appear.

## Core Workflow

Choose the least fragile path:

- For simple native operations, prefer Rhino commands through `run_command`.
- For structured or repeated geometry generation, use Rhino Python through `run_python`.
- Before screenshots or framing, inspect the model with `get_selection` or `list_objects`.
- When capturing images, frame the target first with `zoom_to_object` or a bounding box.
- Use `get_viewport_image` for viewport captures instead of asking the user for screenshots unless Rhino-side capture fails.

## Good Patterns

### Create geometry

- Boxes, lines, circles, layers, view changes: use `run_command`.
- More detailed procedural geometry: use `run_python`.

### Inspect model state

Use:

- `get_selection`
- `list_objects`
- `zoom_to_object`

Always verify what is selected before acting on "the selected model," because mixed selections are common.

### Capture images

Use `get_viewport_image` with an explicit view or camera framing.

Good defaults:

- `displayMode: Arctic` for clean presentation captures
- `displayMode: Technical` for line-focused previews
- `restoreState: true` unless the user wants the viewport changed permanently

### Save and close

If the user asks to save, prefer an explicit file path when the document name/path is unclear.

## Modeling Guidance

When building from a reference image:

1. Identify the dominant masses first.
2. Build proportions before ornament.
3. Add secondary framing, rails, and repeated members after the large forms read correctly.
4. Tell the user clearly if the result is an interpretation rather than a precise reconstruction.

If the reference is elevation-like or diagrammatic, keep symmetry disciplined and avoid random improvisation.

## Troubleshooting

### Claude cannot reach Rhino

Check:

- Rhino is still open
- `RhinoMCP` is running
- `http://localhost:4862/` is live

### Browser shows nothing useful

That is normal. The Rhino MCP endpoint is an API endpoint, not a normal webpage.

### A screenshot looks messy

Common causes:

- the selection contains multiple unrelated objects
- hidden context is still visible
- capture happened in an editing display mode

Re-check selection, isolate the target, and capture again.
