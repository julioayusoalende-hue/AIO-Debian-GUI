#!/usr/bin/env python3
"""Flujos GTK de selección, diagnóstico, resultados y adaptación, sin mantenimiento real."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

if not Gtk.init_check([])[0]:
    print('Sin pantalla: pruebas GTK de flujo omitidas (usar xvfb-run).')
    sys.exit(0)
loader = importlib.machinery.SourceFileLoader('ui_flow', 'package/usr/bin/aio-debian-gui')
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)

def settle():
    end = time.monotonic() + .18
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(.005)

for language in ('es', 'en', 'fr', 'zh'):
    w = app.VentanaPrincipal({'idioma': language, 'tema': 'claro', 'modo_simple': False})
    w.show_all()
    settle()
    assert not w.detalles_sistema.get_expanded()
    assert not w.expansor_consola.get_expanded()
    assert not w.grupos_tareas[-1].get_expanded()
    assert all(isinstance(check, Gtk.CheckButton) for check, _ in w.switches.values())
    assert isinstance(w.chk_sin_contrasena, Gtk.Switch)
    assert not any(t in w._pasos_seleccionados() for t in ('backports-kernel-mesa', 'revertir-backports', 'nvidia-driver', 'ubuntu-hwe'))
    w._preset_flatpak(None)
    assert w._pasos_seleccionados() == ['flatpak-update']
    assert w.btn_iniciar.get_label() == app.traducir('Ejecutar 1 tarea')
    w.switches['flatpak-update'][0].set_active(False)
    assert not w.btn_iniciar.get_sensitive()
    assert w.resumen_seleccion.get_text() == app.traducir('No hay tareas seleccionadas.')
    w.switches['upgrade'][0].set_active(True)
    w.switches['autoclean'][0].set_active(True)
    assert w.btn_iniciar.get_label() == app.traducir('Ejecutar %d tareas') % 2
    assert app.traducir('Actualizar los paquetes del sistema') in w.resumen_seleccion.get_text()

    def cancel_preview():
        dialogs = [d for d in Gtk.Window.list_toplevels() if isinstance(d, Gtk.MessageDialog)]
        assert len(dialogs) == 1
        dialog = dialogs[0]
        assert app.traducir('Actualizar los paquetes del sistema') in dialog.get_property('secondary-text')
        dialog.response(Gtk.ResponseType.CANCEL)
        return GLib.SOURCE_REMOVE
    GLib.idle_add(cancel_preview)
    assert not w._confirmar_tareas(w._pasos_seleccionados())

    if 'revertir-backports' in w.switches:
        w.switches['revertir-backports'][0].set_active(True)
        assert w._pasos_seleccionados() == ['revertir-backports']
        assert not w.switches['upgrade'][0].get_sensitive()
        w.switches['revertir-backports'][0].set_active(False)
        assert w.switches['upgrade'][0].get_sensitive()
    w._preset_completo(None)

    ok = {'name': 'Estado de dpkg', 'status': 'ok', 'detail': 'ok', 'advice': ''}
    warning = {'name': 'Espacio en /', 'status': 'warning', 'detail': 'disk', 'advice': 'Libera espacio antes de grandes actualizaciones.'}
    unknown = {**ok, 'status': 'unknown', 'detail': 'unavailable'}
    w._resumir_diagnostico([ok])
    assert w.estado_diagnostico == 'Sin incidencias'
    w._resumir_diagnostico([ok, warning])
    assert w.estado_diagnostico == 'Requiere atención'
    assert app.traducir(warning['advice']) in w.consejo_sistema.get_text()
    w._resumir_diagnostico([ok, unknown])
    assert w.estado_diagnostico == 'No comprobado'
    w._resumir_diagnostico([], 'timeout')
    assert w.estado_diagnostico == 'No comprobado'

    w.tareas_en_ejecucion = ['upgrade', 'autoclean']
    w._preparar_resultados(w.tareas_en_ejecucion)
    w._procesar('##STEP:1:2:Actualizar paquetes')
    assert w.resultados_tareas['upgrade'][1] == 'En curso'
    w._procesar('##RESULT:upgrade:0')
    assert w.resultados_tareas['upgrade'][1] == 'Completada'
    w._procesar('##RESULT:autoclean:1')
    assert w.resultados_tareas['autoclean'][1] == 'Error'
    assert w.expansor_consola.get_expanded()
    w.expansor_consola.set_expanded(False)
    w._escribir('technical log\n')
    assert not w.expansor_consola.get_expanded()
    w._escribir('failure\n', 'error')
    assert w.expansor_consola.get_expanded()
    w.expansor_consola.set_expanded(False)
    w.scroll_resultados.hide()
    # Una segunda confirmación cancelada debe liberar el estado ocupado.
    w.en_curso = True
    w.proceso = None
    with patch.object(w, '_continuar_mantenimiento', return_value=None):
        w._terminar_preflight(['upgrade'], app.core_preflight.Report(False, []), None)
    assert not w.en_curso

    for width in (1160, 700, 600, 1161, 1400):
        w.resize(width, 900)
        settle()
        actual = w.get_size()[0]
        assert actual <= width + 1, (language, width, actual)
        panels = w.paneles_principales
        if actual < 900:
            assert panels.get_orientation() == Gtk.Orientation.VERTICAL, (language, width, actual)
            assert w.separador_paneles.get_orientation() == Gtk.Orientation.HORIZONTAL
        else:
            assert panels.get_orientation() == Gtk.Orientation.HORIZONTAL, (language, width, actual)
            left, right = w.panel_izquierdo, w.panel_derecho
            assert abs(left.get_allocated_width() - right.get_allocated_width()) <= 1
            px = panels.translate_coordinates(w, 0, 0)[0]
            sep = w.separador_paneles
            sx = sep.translate_coordinates(w, 0, 0)[0]
            assert abs(sx + sep.get_allocated_width()/2 - px - panels.get_allocated_width()/2) <= 1, (language, width, actual, sx, sep.get_allocated_width(), px, panels.get_allocated_width(), sep.get_visible())
        if os.environ.get('AIO_UI_SCREENSHOTS') and width in (600, 1160) and language == 'es':
            directory = Path(os.environ['AIO_UI_SCREENSHOTS'])
            directory.mkdir(parents=True, exist_ok=True)
            window = w.get_window()
            shot = app.Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
            shot.savev(str(directory / f'ui-{width}.png'), 'png', [], [])
    w.destroy()
    settle()
w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': True})
w.show_all()
settle()
assert not w.expansor_consola.get_visible()
w._escribir('error visible en modo simple', 'error')
settle()
assert w.expansor_consola.get_visible() and w.expansor_consola.get_expanded()
assert w.log.get_mapped()
inicio, fin = w.buf.get_bounds()
assert 'error visible en modo simple' in w.buf.get_text(inicio, fin, True)
w.destroy()
print('GTK: selección, confirmación, exclusión Stable, diagnóstico, consola, resultados y adaptación en cuatro idiomas OK')
