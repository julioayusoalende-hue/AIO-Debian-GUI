#!/usr/bin/env python3
"""Checks for experimental Snap without requiring snapd or Snap Store credentials."""
import ast
from pathlib import Path

script = Path("package/usr/bin/aio-debian-gui")
tree = ast.parse(script.read_text(encoding="utf8"))
functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
env = {"os": __import__("os"), "__file__": "/snap/aio-debian-gui/current/usr/bin/aio-debian-gui",
       "es_flatpak": lambda: False}
import os
env["os"].environ["SNAP"] = "/snap/aio-debian-gui/current"
exec(compile(ast.Module(body=[functions["formato_actualizacion"]], type_ignores=[]),
             str(script), "exec"), env)
assert env["formato_actualizacion"]() == "snap"
snap = Path("snap/snapcraft.yaml").read_text()
assert "confinement: classic" in snap and "grade: devel" in snap
assert "python3-gi" in snap
assert 'snap/local/aio-debian-gui-snap-launch' in snap
assert "SNAP_VERSION" in script.read_text()
assert "if os.environ.get(\"SNAP\"):" in script.read_text()
print("✔ Snap experimental identificado; sin actualizaciones AppImage ni instalación implícita de helper")
