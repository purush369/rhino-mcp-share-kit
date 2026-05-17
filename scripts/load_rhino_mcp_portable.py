import os
import traceback

import Rhino


PACKAGE_ROOT = os.path.join(
    os.environ.get("APPDATA", ""),
    "McNeel",
    "Rhinoceros",
    "packages",
    "8.0",
    "Rhino-MCP-Platform",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "load_rhino_mcp_portable.log")


def log(message):
    try:
        text_type = unicode
    except NameError:
        text_type = str

    text = message if isinstance(message, text_type) else str(message)
    with open(LOG_PATH, "ab") as handle:
        handle.write((text + u"\n").encode("utf-8"))


def find_plugin_path():
    candidates = []
    if not os.path.isdir(PACKAGE_ROOT):
        return None

    for root, _dirs, files in os.walk(PACKAGE_ROOT):
        if "RhinoMcpPlatform.rhp" in files:
            candidates.append(os.path.join(root, "RhinoMcpPlatform.rhp"))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0]


try:
    log("=== Rhino MCP portable loader start ===")
    log("Package root: {0}".format(PACKAGE_ROOT))

    plugin_path = find_plugin_path()
    log("Resolved plugin path: {0}".format(plugin_path))

    if not plugin_path or not os.path.exists(plugin_path):
        raise RuntimeError("Could not find RhinoMcpPlatform.rhp under {0}".format(PACKAGE_ROOT))

    result, plugin_id = Rhino.PlugIns.PlugIn.LoadPlugIn(plugin_path)
    log("LoadPlugIn result: {0}".format(result))
    log("Plugin id: {0}".format(plugin_id))

    run_result = Rhino.RhinoApp.RunScript("_RhinoMCP", False)
    log("RunScript(_RhinoMCP) result: {0}".format(run_result))
except Exception:
    log("EXCEPTION")
    log(traceback.format_exc())
