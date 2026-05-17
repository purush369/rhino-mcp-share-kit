import os

import Rhino
import rhinoscriptsyntax as rs

from create_demo_rhino_scene import main as create_demo_scene


LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_demo_file_for_release.log")


def log(message):
    with open(LOG_PATH, "ab") as handle:
        handle.write((str(message) + "\n").encode("utf-8"))


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_output_path():
    path = os.path.join(repo_root(), "examples", "demo-files")
    if not os.path.isdir(path):
        os.makedirs(path)
    return os.path.join(path, "rhino_mcp_demo_scene.3dm")


def main():
    output_path = build_output_path()
    log("=== build demo start ===")
    log("output_path={0}".format(output_path))

    try:
        rs.Command("_-New _None", echo=False)
        log("new command sent")
    except Exception:
        log("new command failed")

    create_demo_scene()
    log("demo scene created")

    save_command = '_-SaveAs "{0}" _Enter'.format(output_path)
    save_ok = rs.Command(save_command, echo=False)
    log("save_ok={0}".format(save_ok))
    print("Saved demo file: {0}".format(output_path))
    print("Save command result: {0}".format(save_ok))

    log("exit command sent")
    Rhino.RhinoApp.RunScript("_Exit", False)


if __name__ == "__main__":
    main()
