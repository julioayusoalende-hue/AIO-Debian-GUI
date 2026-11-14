#!/usr/bin/env python3
"""Regresión: no ejecutar ni ofrecer gestores de instantáneas en AiO."""
from pathlib import Path

gui = Path("package/usr/bin/aio-debian-gui").read_text(encoding="utf-8")
helper = Path("package/usr/lib/aio-debian-gui/aio-debian-gui-helper").read_text(encoding="utf-8")
for token in ("--snapshot-provider", "--snapshot-before", "--snapshot-options",
              "crear_instantanea_previa", "opciones_instantanea"):
    assert token not in gui, f"Integración de instantáneas reintroducida en GUI: {token}"
    assert token not in helper, f"Integración de instantáneas reintroducida en helper: {token}"
assert "comando_pkexec(helper, lang, *pasos)" in gui, "La GUI debe pasar solo tareas al helper"
assert 'local pasos=() s' in helper, "El helper debe validar las tareas"
print("OK: no hay integración de instantáneas en GUI ni helper")
