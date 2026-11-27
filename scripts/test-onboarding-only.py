#!/usr/bin/env python3
"""Regresión: --onboarding-only debe fallar si el wizard no llega a abrirse."""

import contextlib
import importlib.machinery
import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import gi

gi.require_version("Gtk", "3.0")

ROOT = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader(
    "aio_onboarding_only_test", str(ROOT / "package/usr/bin/aio-debian-gui")
)
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)


class FakeWindow:
    def __init__(self, extensions):
        self.extensions = extensions

    def connect(self, *_args):
        return 1


def broken_onboarding(_window):
    raise RuntimeError("fallo simulado del lanzador")


def ejecutar(extensiones):
    ventana = FakeWindow(extensiones)
    errores = io.StringIO()
    with (
        patch.object(sys, "argv", ["aio-debian-gui", "--onboarding-only"]),
        patch.object(app.os, "geteuid", return_value=1000),
        patch.object(app, "cargar_preferencias", return_value=app.PREFERENCIAS_DEFECTO.copy()),
        patch.object(app, "VentanaPrincipal", return_value=ventana),
        patch.object(app, "aplicar_tema"),
        patch.object(app.Gtk, "main") as bucle,
        contextlib.redirect_stderr(errores),
    ):
        try:
            app.main()
        except SystemExit as exc:
            codigo = exc.code
        else:
            codigo = None
    return codigo, errores.getvalue(), bucle.called


codigo, errores, bucle = ejecutar([])
assert codigo == 2 and not bucle, (codigo, errores, bucle)
assert "Onboarding no disponible" in errores

codigo, errores, bucle = ejecutar([
    SimpleNamespace(launch_onboarding=broken_onboarding),
])
assert codigo == 2 and not bucle, (codigo, errores, bucle)
assert "No se pudo abrir el onboarding" in errores

print("✔ onboarding-only: ausencia y fallo del lanzador devuelven error sin abrir la ventana")
