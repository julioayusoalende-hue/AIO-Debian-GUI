#!/usr/bin/env python3
"""Pruebas aisladas del historial XDG y permisos del módulo core."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath("package/usr/lib/aio-debian-gui"))
from aio_core import history

with tempfile.TemporaryDirectory() as temp:
    state = os.path.join(temp, "state")
    path = history.ruta_historial(state)
    assert history.leer_historial(path) == []
    for index in range(105):
        history.guardar_registro_mantenimiento(
            ["upgrade", "autoremove"], "correcto" if index % 2 else "error",
            index == 104, ruta=path, formato="deb", version="1.1.0",
        )
    data = history.leer_historial(path)
    assert len(data) == history.MAX_HISTORIAL
    assert data[-1]["reinicio_recomendado"] is True
    assert data[-1]["version"] == "1.1.0"
    assert data[-1]["formato"] == "deb"
    assert data[-1]["tareas"] == ["upgrade", "autoremove"]
    assert (os.stat(path).st_mode & 0o777) == 0o600
    with open(path, encoding="utf-8") as handle:
        json.load(handle)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{corrupt data")
    assert history.leer_historial(path) == []
print("✔ historial modular: persistencia, privacidad, límite de 100 y corrupción")
