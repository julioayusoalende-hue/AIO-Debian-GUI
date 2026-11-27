#!/usr/bin/env python3
"""Regresión GTK del dimensionado y desplazamiento de Diagnósticos AyusOS."""

import sys
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

if not Gtk.init_check([])[0]:
    print("Sin pantalla: prueba GTK de diagnósticos omitida (usar xvfb-run).")
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "package/usr/lib/aio-debian-gui"))
sys.path.insert(0, str(ROOT / "ayusos-control-center/package/usr/lib/aio-debian-gui/extensions"))

from ayusos.pages import AyusOSPagesMixin


class Host(AyusOSPagesMixin):
    @staticmethod
    def _pagina_tarjetas():
        pagina = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        pagina.set_border_width(14)
        return pagina

    @staticmethod
    def _etiqueta_estado():
        estado = Gtk.Label(xalign=0)
        estado.set_no_show_all(True)
        estado.set_line_wrap(True)
        estado.connect("notify::label", lambda lbl, _: lbl.set_visible(bool(lbl.get_text())))
        return estado

    def _abrir_recuperacion(self):
        pass


def settle():
    limite = time.monotonic() + 0.4
    while time.monotonic() < limite:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.005)


host = Host()
pagina = host._pagina_ayusos_diagnostics()
assert host.diagnostics_page_scroll.get_policy() == (
    Gtk.PolicyType.AUTOMATIC,
    Gtk.PolicyType.AUTOMATIC,
)
assert host.diagnostics_results_scroll.get_policy() == (
    Gtk.PolicyType.AUTOMATIC,
    Gtk.PolicyType.AUTOMATIC,
)
assert host.diagnostics_status.get_max_width_chars() == 90

detalle = host._texto_detalle_diagnostico([
    {"name": "Índices APT", "detail": "Último índice: hace 0 días.", "advice": "Revisa apt update."},
    {"name": "Módulos DKMS", "detail": "DKMS no está instalado."},
])
assert "Índices APT: Último índice" in detalle
assert "Revisa apt update." in detalle
assert "[{" not in detalle

host._diagnostics_done(True, {
    "core": {"ok": True, "details": [
        {"name": "Índices APT", "detail": "Correcto", "advice": "Ninguna"},
    ]},
    "apt": {"ok": False, "message": "Revisar el repositorio"},
    "_summary": {"passed": 1, "total": 2},
})
assert host.diagnostics_store.iter_n_children(None) == 2
assert "1/2" in host.diagnostics_status.get_text()

ventana = Gtk.Window()
ventana.set_default_size(520, 360)
ventana.add(pagina)
ventana.show_all()
settle()
assert host.diagnostics_page_scroll.get_vscrollbar().get_visible(), (
    "La página debe mostrar desplazamiento vertical cuando no cabe"
)
assert host.diagnostics_results_scroll.get_vscrollbar().get_visible(), (
    "El árbol debe mostrar desplazamiento vertical cuando no caben los resultados"
)
assert host.diagnostics_page_scroll.get_hscrollbar().get_visible(), (
    "La página debe mostrar desplazamiento horizontal si el contenido no cabe"
)
assert host.diagnostics_results_scroll.get_hscrollbar().get_visible(), (
    "El árbol debe mostrar desplazamiento horizontal si las columnas no caben"
)
ventana.destroy()
print("✔ Diagnósticos AyusOS: tamaño adaptable y barras de desplazamiento automáticas")
