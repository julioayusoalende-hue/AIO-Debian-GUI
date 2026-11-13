#!/usr/bin/env python3
"""Pruebas sin GUI de configuración y validación del módulo de preferencias."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath("package/usr/lib/aio-debian-gui"))
from aio_core import preferences

DEFAULTS = {"idioma": "es", "tema": "sistema", "modo_simple": False}
with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, "preferences.json")
    assert preferences.cargar_preferencias(path, DEFAULTS) == DEFAULTS
    values = dict(DEFAULTS, idioma="fr", tema="oscuro", modo_simple=True)
    preferences.guardar_preferencias(values, path)
    assert preferences.cargar_preferencias(path, DEFAULTS) == values
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == values

    for invalid in [dict(DEFAULTS, idioma="unsupported"),
                    dict(DEFAULTS, tema="unsafe"),
                    dict(DEFAULTS, modo_simple="True")]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(invalid, f)
        try:
            preferences.cargar_preferencias(path, DEFAULTS)
        except ValueError:
            pass
        else:
            raise AssertionError("Se aceptaron preferencias incorrectas")

    with open(path, "w", encoding="utf-8") as f:
        f.write("[]")
    try:
        preferences.cargar_preferencias(path, DEFAULTS)
    except ValueError:
        pass
    else:
        raise AssertionError("Se aceptó un JSON sin objeto")
print("✔ preferencias modulares: persistencia, valores, validación y datos malformados")
