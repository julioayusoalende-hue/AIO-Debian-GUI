#!/usr/bin/env python3
"""Tests de historial locales sin cargar GTK ni modificar el sistema."""
import ast
import datetime
import json
import os
import tempfile
import types

source = "package/usr/bin/aio-debian-gui"
with open(source, encoding="utf-8") as handle:
    tree = ast.parse(handle.read(), source)
functions = {"ruta_historial", "leer_historial", "guardar_registro_mantenimiento"}
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in functions]
assert {n.name for n in nodes} == functions
with tempfile.TemporaryDirectory() as temp:
    state = os.path.join(temp, "state")
    ctx = {
        "os": os, "json": json, "tempfile": tempfile, "datetime": datetime,
        "GLib": types.SimpleNamespace(get_user_state_dir=lambda: state),
        "PRGNAME": "aio-debian-gui", "MAX_HISTORIAL": 100,
        "formato_actualizacion": lambda: "deb", "version_app": lambda: "1.0.20",
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), source, "exec"), ctx)
    read, save = ctx["leer_historial"], ctx["guardar_registro_mantenimiento"]
    assert read() == []
    for index in range(105):
        save(["upgrade", "autoremove"], "correcto" if index % 2 else "error", index == 104)
    data = read()
    assert len(data) == 100
    assert data[-1]["reinicio_recomendado"] is True
    assert data[-1]["version"] == "1.0.20"
    assert data[-1]["tareas"] == ["upgrade", "autoremove"]
    path = ctx["ruta_historial"]()
    assert (os.stat(path).st_mode & 0o777) == 0o600
    with open(path, encoding="utf-8") as handle:
        json.load(handle)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{corrupt data")
    assert read() == []
print("✔ historial: serialización, privacidad, límite de 100 entradas y tolerancia a corrupción")
