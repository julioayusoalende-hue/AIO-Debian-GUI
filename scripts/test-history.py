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
    detalles = {"upgrade": {"estado": "Error", "mensaje": "Fallo en el índice"},
                "autoremove": {"estado": "No ejecutada", "mensaje": ""}}
    history.guardar_registro_mantenimiento(["upgrade", "autoremove"], "error",
                                           ruta=path, detalles=detalles)
    assert history.leer_historial(path)[-1]["detalles"] == detalles
    programado = {"started": "2026-11-20T09:00:00+00:00", "status": "error",
                  "tasks": {"upgrade": "error"}, "errors": {"upgrade": "Fallo en el índice"}}
    registros = history.registros_programados({"history": [programado], "last_result": programado})
    assert len(registros) == 1
    assert registros[0]["detalles"]["upgrade"] == detalles["upgrade"]
    assert history.tareas_fallidas(registros[0], {"upgrade", "autoremove"}) == ["upgrade"]
    assert history.tareas_fallidas(registros[0], {"autoremove"}) == []
    assert history.tareas_fallidas(data[-1], {"upgrade"}) == []
    ref = history.referencia(registros[0])
    history.guardar_registro_mantenimiento(["flatpak-update"], "error", ruta=path,
                                           reintento_de=ref, flatpak_sistema=True)
    retry = history.leer_historial(path)[-1]
    assert retry["reintento_de"] == {"fecha": programado["started"], "origen": "Programada"}
    assert history.flatpak_del_sistema(retry)
    assert not history.flatpak_del_sistema({"tareas": ["flatpak-update"]})
    with open(path, encoding="utf-8") as handle:
        json.load(handle)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{corrupt data")
    assert history.leer_historial(path) == []
print("✔ historial modular: persistencia, privacidad, límite de 100 y corrupción")
