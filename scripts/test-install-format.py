#!/usr/bin/env python3
"""Detección de formato del lanzador, sin importar GTK ni modificar el sistema."""
import ast
import os
source = "package/usr/bin/aio-debian-gui"
with open(source, encoding="utf-8") as handle:
    tree = ast.parse(handle.read(), filename=source)
found = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "formato_actualizacion")
assert any(isinstance(n, ast.Constant) and n.value == "deb" for n in ast.walk(found))
for fname, flatpak, appdir, expected in [
    ("/usr/bin/aio-debian-gui", False, None, "deb"),
    ("/tmp/AppDir/usr/bin/aio-debian-gui", False, "/tmp/AppDir", "appimage"),
    ("/app/bin/aio-debian-gui", True, None, "flatpak"),
    ("/tmp/aio-debian-gui", False, None, None),
]:
    original = os.environ.get("APPDIR")
    if appdir is None:
        os.environ.pop("APPDIR", None)
    else:
        os.environ["APPDIR"] = appdir
    env = {"os": os, "__file__": fname, "es_flatpak": lambda: flatpak}
    exec(compile(ast.Module(body=[found], type_ignores=[]), source, "exec"), env)
    assert env["formato_actualizacion"]() == expected, (fname, expected)
    if original is None:
        os.environ.pop("APPDIR", None)
    else:
        os.environ["APPDIR"] = original
print("✔ la cabecera distingue DEB, AppImage, Flatpak y código fuente")
