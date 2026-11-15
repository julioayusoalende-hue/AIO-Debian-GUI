#!/usr/bin/env python3
"""Evita mezclar GDK 4 con GTK 3 al importar la GUI."""
import ast
from pathlib import Path
path = Path("package/usr/bin/aio-debian-gui")
tree = ast.parse(path.read_text(encoding="utf-8"))
required = {}
for index, node in enumerate(tree.body):
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        call = node.value
        if isinstance(call.func, ast.Attribute) and call.func.attr == "require_version" and len(call.args) >= 2:
            if isinstance(call.args[0], ast.Constant) and isinstance(call.args[1], ast.Constant):
                required[call.args[0].value] = (call.args[1].value, index)
    if isinstance(node, ast.ImportFrom) and node.module == "gi.repository":
        for name in ("Gtk", "Gdk"):
            assert required.get(name, (None,))[0] == "3.0", f"{name} debe fijarse a 3.0 antes del import"
            assert required[name][1] < index, f"{name} require_version debe ir antes del import"
        break
else:
    raise AssertionError("No se encontró import de gi.repository")
print("OK: GTK 3 y GDK 3 fijados antes de importar")
