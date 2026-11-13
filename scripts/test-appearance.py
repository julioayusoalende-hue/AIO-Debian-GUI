#!/usr/bin/env python3
"""Validación sin entorno gráfico de la preferencia claro/oscuro del sistema."""
import ast
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath("package/usr/lib/aio-debian-gui"))
from aio_core import appearance, preferences

assert appearance.preferencia_portal(1) == "oscuro"
assert appearance.preferencia_portal(2) == "claro"
assert appearance.preferencia_portal(0) is None
assert appearance.preferencia_gnome("prefer-dark") == "oscuro"
assert appearance.preferencia_gnome("prefer-light") == "claro"
assert appearance.preferencia_gnome("default") is None
assert appearance.tema_de_nombre("Adwaita-dark") == "oscuro"
assert appearance.tema_de_nombre("Adwaita") == "claro"

defaults = {"idioma": "es", "tema": "sistema", "modo_simple": False}
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "prefs.json")
    assert preferences.cargar_preferencias(path, defaults) == defaults
    for modo in ("sistema", "claro", "oscuro"):
        data = dict(defaults, tema=modo)
        preferences.guardar_preferencias(data, path)
        assert preferences.cargar_preferencias(path, defaults) == data
    # Migración: un archivo anterior que guardaba modo manual se respeta.
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"idioma":"es","tema":"oscuro","modo_simple":false}')
    assert preferences.cargar_preferencias(path, defaults)["tema"] == "oscuro"

src = Path("package/usr/bin/aio-debian-gui").read_text(encoding="utf-8")
ast.parse(src)
assert 'combo_tema.append("sistema", traducir("Seguir el sistema"))' in src
assert 'self.gnome.connect("changed::color-scheme"' in src
assert 'self.portal.connect("g-signal", self._cambio_portal)' in src
assert 'self.gtk.connect("notify::gtk-theme-name"' in src
print("✔ tema sistema (portal/GNOME/GTK), ajustes manuales y migración de preferencias")
