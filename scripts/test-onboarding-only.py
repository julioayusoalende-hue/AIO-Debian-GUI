#!/usr/bin/env python3
"""Regresión: --onboarding-only debe fallar si el wizard no llega a abrirse."""

import contextlib
import importlib.machinery
import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "3.0")

ROOT = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader(
    "aio_onboarding_only_test", str(ROOT / "package/usr/bin/aio-debian-gui")
)
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)


def broken_onboarding(_window):
    raise RuntimeError("fallo simulado del lanzador")


def ejecutar(extensiones, durante_bucle=None):
    errores = io.StringIO()
    with (
        patch.object(sys, "argv", ["aio-debian-gui", "--onboarding-only"]),
        patch.object(app.os, "geteuid", return_value=1000),
        patch.object(app, "cargar_preferencias", return_value=app.PREFERENCIAS_DEFECTO.copy()),
        patch.object(app, "load_extensions", return_value=extensiones),
        patch.object(app, "VentanaPrincipal", side_effect=AssertionError("ventana principal innecesaria")),
        patch.object(app, "aplicar_tema"),
        patch.object(app.Gtk, "main_quit"),
        patch.object(app.Gtk, "main", side_effect=durante_bucle) as bucle,
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

for evento, esperado in (("completed", 0), ("cancelled", 2), ("destroy", 2)):
    wizard = Mock()
    def activar_evento():
        llamadas = dict(llamada.args for llamada in wizard.connect.call_args_list)
        llamadas[evento](wizard)

    codigo, _, bucle = ejecutar(
        [SimpleNamespace(launch_onboarding=lambda parent: wizard if parent is None else None)],
        activar_evento,
    )
    assert codigo == esperado and bucle
print("✔ onboarding-only: carga directa, éxito confirmado y reintento al cerrar")


# El lanzador de escritorio pasa un fichero como argumento en el arranque normal.
archivo = "/tmp/Paquete de prueba.deb"
ventana = Mock(extensions=[])
with (
    patch.object(sys, "argv", ["aio-debian-gui", archivo]),
    patch.object(app.os, "geteuid", return_value=1000),
    patch.object(app, "cargar_preferencias", return_value=app.PREFERENCIAS_DEFECTO.copy()),
    patch.object(app, "VentanaPrincipal", return_value=ventana),
    patch.object(app, "aplicar_tema"),
    patch.object(app.GLib, "timeout_add") as programar,
    patch.object(app.Gtk, "main"),
):
    app.main()
    ventana._mostrar_gestor_software.assert_called_once_with()
    programar.assert_called_once_with(100, ventana.pagina_software.open_local_file, archivo)

print("✔ apertura desde el escritorio: muestra el Gestor de software y programa la previsualización")
