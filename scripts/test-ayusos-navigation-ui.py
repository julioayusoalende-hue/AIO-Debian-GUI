#!/usr/bin/env python3
"""Comprueba la ubicación de las acciones de AyusOS en la ventana real."""
import runpy
import sys
import time
from pathlib import Path
from unittest.mock import patch

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

if not Gtk.init_check([])[0]:
    print("Sin pantalla: prueba GTK de navegación omitida (usar xvfb-run).")
    sys.exit(0)

root = Path(__file__).resolve().parent.parent
app = runpy.run_path(str(root / "package/usr/bin/aio-debian-gui"), run_name="ayusos_navigation_ui")
sys.path.insert(0, str(root / "ayusos-control-center/package/usr/lib/aio-debian-gui/extensions"))
from ayusos import branding, extension

preferencias = {"idioma": "es", "tema": "claro", "modo_simple": False}
window_type = app["VentanaPrincipal"]
for es_ayusos in (False, True):
    with patch.dict(window_type.__init__.__globals__, {"load_extensions": lambda: [extension.Extension()]}), \
         patch.object(extension, "es_ayusos", return_value=es_ayusos), \
         patch.object(extension, "is_recovery_boot", return_value=False):
        window = window_type(preferencias)
    try:
        window.show_all()
        notebook = window.notebook
        titles = [notebook.get_tab_label_text(page) for page in notebook.get_children()]
        assert not {"Actualización AyusOS", "Snapshots", "Diagnósticos AyusOS"}.intersection(titles)
        buttons = [widget for widget in window.fila_sistema_operativo.get_children()
                   if isinstance(widget, Gtk.Button)]
        timeshift = window.secciones_backup["timeshift"]
        expanders = [widget for widget in timeshift.get_children() if isinstance(widget, Gtk.Expander)]
        assert len(buttons) == len(expanders) == int(es_ayusos)
        if not es_ayusos:
            continue
        assert "Branding AyusOS" in titles
        assert buttons[0].get_label() == "Actualizar AyusOS"
        assert window.fila_sistema_operativo.get_children()[0].get_text()
        buttons[0].clicked()
        dialog = window.ventana_actualizacion_ayusos
        assert dialog.get_visible() and dialog.get_transient_for() == window
        assert window.ayusos_check_btn.get_toplevel() == dialog
        assert notebook.get_current_page() == 0
        dialog.response(Gtk.ResponseType.CLOSE)
        assert not dialog.get_visible()
        buttons[0].clicked()
        assert window.ventana_actualizacion_ayusos == dialog and dialog.get_visible()
        dialog.response(Gtk.ResponseType.CLOSE)

        logo_path = root / "ayusos-control-center/package/usr/share/ayusos-control-center/ayusos-logo.png"
        with patch.object(extension, "es_ayusos", return_value=True), \
             patch.object(extension, "get_ayusos_version", return_value="1.4"), \
             patch.object(branding, "LOGO", logo_path), \
             patch.dict(window_type._actualizar_detalles_sistema.__globals__, {
                 "informacion_sistema": lambda nombre: ([("Sistema operativo", nombre)], ""),
             }):
            window.btn_detalles_sistema.clicked()
            context = GLib.MainContext.default()
            limite = time.monotonic() + 3
            while window.cargando_detalles_sistema and time.monotonic() < limite:
                context.iteration(False)
                time.sleep(0.005)
            assert not window.cargando_detalles_sistema
        details = window.ventana_detalles_sistema
        grid = window.grid_detalles_sistema
        logo = grid.get_parent().get_children()[0]
        assert logo.get_accessible().get_name() == "Logotipo de AyusOS Linux"
        assert grid.get_child_at(1, 0).get_text() == "AyusOS Linux 1.4", grid.get_child_at(1, 0).get_text()
        details.response(Gtk.ResponseType.CLOSE)

        notebook.set_current_page(titles.index("Backup"))
        snapshots = expanders[0]
        assert snapshots.get_label() == "Instantáneas de Timeshift"
        assert not snapshots.get_expanded()
        snapshots.set_expanded(True)
        assert window.snapshots_list.get_ancestor(Gtk.Expander) == snapshots
        assert window.backup_buttons["timeshift"].get_parent().get_parent() == timeshift
        assert window.backup_buttons["deja-dup"].get_parent().get_parent() != timeshift
    finally:
        window.destroy()

print("✔ AyusOS: actualización en Mantenimiento e instantáneas en Timeshift")
