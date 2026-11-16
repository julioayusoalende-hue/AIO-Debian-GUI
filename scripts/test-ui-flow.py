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
    assert w.notebook.get_n_pages() == 3
    assert [w.notebook.get_tab_label_text(w.notebook.get_nth_page(i))
            for i in range(2)] == [
                app.traducir('Configuración y mantenimiento'), app.traducir('Backup')
            ]
    assert w.notebook.get_tab_label_text(w.notebook.get_nth_page(2)) == \
        app.traducir('Apps recomendadas')
    assert set(w.backup_buttons) == {'timeshift', 'deja-dup'}
    assert all(button.get_image() is not None for button in w.backup_buttons.values())
    for app_id, button in w.backup_buttons.items():
        row = button.get_parent()
        assert row.get_orientation() == Gtk.Orientation.VERTICAL
        assert len(row.get_children()) == 2
        description = row.get_children()[1]
        assert isinstance(description, Gtk.Label)
        assert description.get_text() == app.traducir(app.APLICACIONES_BACKUP[app_id]['description'])
    w.notebook.set_current_page(1)
    w.resize(600, 900)
    settle()
    assert w.get_size()[0] <= 601, (language, w.get_size())
    assert all(button.get_mapped() for button in w.backup_buttons.values())
    w.notebook.set_current_page(2)
    settle()
    assert w.get_size()[0] <= 601, (language, w.get_size())
    assert all(button.get_mapped() for button in w.recommended_buttons.values())
    assert len(w.recommended_grid.get_children()) == 10
    expected_names = ['Celluloid', 'Feishin', 'GIMP', 'Google Chrome', 'HandBrake',
                      'Plex', 'Spotify', 'Switcheroo', 'Video Downloader', 'VLC']
    assert [item['name'] for item in app.APPS_RECOMENDADAS] == expected_names
    for index, name in enumerate(expected_names):
        card = w.recommended_grid.get_child_at(index % 2, index // 2)
        assert card is not None
        contents = card.get_child().get_children()
        header = contents[0].get_children()
        assert isinstance(header[0], Gtk.Image)
        assert header[1].get_text() == name
        assert contents[1].get_text() == app.traducir(
            app.APPS_RECOMENDADAS[index]['description'])
        fallback_theme = type(
            'FallbackTheme', (), {'has_icon': lambda self, icon: icon == app.APPS_RECOMENDADAS[index]['fallback_icon']}
        )()
        assert app.nombre_icono_recomendada(
            {'icon': 'missing-app-icon', 'fallback_icon': app.APPS_RECOMENDADAS[index]['fallback_icon']},
            fallback_theme,
        ) == app.APPS_RECOMENDADAS[index]['fallback_icon']
    assert {key for key in w.recommended_buttons if key[1] == 'deb'} == {
        ('celluloid', 'deb'), ('gimp', 'deb'), ('handbrake', 'deb'), ('vlc', 'deb')
    }
    assert ('feishin', 'flatpak') in w.recommended_buttons
    assert ('feishin', 'deb-download') in w.recommended_buttons
    assert ('plex', 'flatpak') in w.recommended_buttons
    assert ('google-chrome', 'deb-download') in w.recommended_buttons
    w.notebook.set_current_page(0)
    settle()
    if language != 'es':
        assert app.traducir('Operación en curso') != 'Operación en curso'
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

# Backup: abrir aplicaciones presentes, pedir confirmación para instalar las ausentes,
# mantener los controles ocupados durante la detección y no bloquear el cierre en reposo.
w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
w.show_all()
settle()

class ImmediateThread:
    def __init__(self, target, daemon=False):
        self.target = target

    def start(self):
        self.target()

with patch.object(w, '_mensaje') as message:
    assert not w._al_cerrar()
    w.backup_action_in_progress = True
    assert w._al_cerrar()
    message.assert_called_once()
    w.backup_action_in_progress = False

# Apps recomendadas: fuentes separadas, ejecuciones seguras y confirmación de instalación.
gimp = next(item for item in app.APPS_RECOMENDADAS if item['id'] == 'gimp')
apt_installed = app.subprocess.CompletedProcess([], 0, stdout='installed', stderr='')
with patch.object(app.subprocess, 'run', return_value=apt_installed), \
     patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(app.Gio.Subprocess, 'new') as launch:
    w._accion_app_recomendada(w.recommended_buttons[('gimp', 'deb')], 'gimp', 'deb')
    settle()
    launch.assert_not_called()
    assert w.recommended_indicators[('gimp', 'deb')].get_visible()
    assert not w.recommended_buttons[('gimp', 'deb')].get_sensitive()

vlc = next(item for item in app.APPS_RECOMENDADAS if item['id'] == 'vlc')
flatpak_installed = app.subprocess.CompletedProcess(
    [], 0, stdout='org.videolan.VLC\n', stderr=''
)
with patch.object(app.subprocess, 'run', return_value=flatpak_installed), \
     patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(app.Gio.Subprocess, 'new') as launch:
    w._accion_app_recomendada(w.recommended_buttons[('vlc', 'flatpak')], 'vlc', 'flatpak')
    settle()
    launch.assert_not_called()
    assert w.recommended_indicators[('vlc', 'flatpak')].get_visible()

with patch.object(app, 'comando_host', side_effect=lambda *args: list(args)), \
     patch.object(w, '_comprobar_deb_recomendada', return_value=False), \
     patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(app.Gio.AppInfo, 'launch_default_for_uri') as open_url:
    w._accion_app_recomendada(
        w.recommended_buttons[('google-chrome', 'deb-download')],
        'google-chrome', 'deb-download',
    )
    settle()
    open_url.assert_called_once_with('https://www.google.com/chrome/', None)

missing_apt = app.subprocess.CompletedProcess(
    [], 1, stdout='', stderr='dpkg-query: no packages found matching gimp'
)
install_result = app.subprocess.CompletedProcess(
    [], 0, stdout='##RECOMMENDED:installed:gimp\n', stderr=''
)
w.recommended_installed.pop(('gimp', 'deb'))
with patch.object(app.subprocess, 'run', side_effect=[missing_apt, install_result]), \
     patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
     patch.object(app, 'helper_mantenimiento', return_value='/test/helper'), \
     patch.object(app, 'helper_disponible', return_value=True), \
     patch.object(app, 'comando_pkexec',
                  return_value=['pkexec', '/test/helper', '--recommended-install', 'gimp']), \
     patch.object(app.Gio.Subprocess, 'new') as launch:
    w._accion_app_recomendada(
        w.recommended_buttons[('gimp', 'deb')], 'gimp', 'deb'
    )
    settle()
    launch.assert_not_called()
    assert w.recommended_indicators[('gimp', 'deb')].get_visible()

missing_flatpak = app.subprocess.CompletedProcess([], 0, stdout='', stderr='')
flathub_remote = app.subprocess.CompletedProcess([], 0, stdout='flathub\n', stderr='')
user_remote_result = app.subprocess.CompletedProcess([], 0, stdout='', stderr='')
flatpak_install_result = app.subprocess.CompletedProcess([], 0, stdout='', stderr='')
w.recommended_installed.pop(('vlc', 'flatpak'))
with patch.object(app.subprocess, 'run',
                  side_effect=[missing_flatpak, user_remote_result, flatpak_install_result]) as run, \
     patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
     patch.object(app.Gio.Subprocess, 'new') as launch:
    w._accion_app_recomendada(
        w.recommended_buttons[('vlc', 'flatpak')], 'vlc', 'flatpak'
    )
    settle()
    run.assert_any_call(
        ['flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub',
         'https://dl.flathub.org/repo/flathub.flatpakrepo'],
        capture_output=True, text=True, timeout=60,
    )
    run.assert_any_call(
        ['flatpak', 'install', '--user', '--noninteractive', '--assumeyes',
         'flathub', 'org.videolan.VLC'],
        capture_output=True, text=True, timeout=600,
    )
    launch.assert_not_called()
    assert w.recommended_indicators[('vlc', 'flatpak')].get_visible()

video_id = 'com.github.unrud.VideoDownloader'
with patch.object(app.subprocess, 'run',
                  side_effect=[missing_flatpak, user_remote_result, flatpak_install_result]) as run, \
     patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
     patch.object(app.Gio.Subprocess, 'new') as launch:
    w._accion_app_recomendada(
        w.recommended_buttons[('video-downloader', 'flatpak')], 'video-downloader', 'flatpak'
    )
    settle()
    run.assert_any_call(
        ['flatpak', 'install', '--user', '--noninteractive', '--assumeyes',
         'flathub', video_id], capture_output=True, text=True, timeout=600,
    )
    launch.assert_not_called()
    assert w.recommended_indicators[('video-downloader', 'flatpak')].get_visible()
    assert w.recommended_status.get_text() == ''

w.recommended_installed.pop(('video-downloader', 'flatpak'))
with patch.object(app.subprocess, 'run',
                  return_value=app.subprocess.CompletedProcess([], 0, stdout=video_id + '\n', stderr='')), \
     patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(app.Gio.Subprocess, 'new') as launch:
    w._accion_app_recomendada(
        w.recommended_buttons[('video-downloader', 'flatpak')], 'video-downloader', 'flatpak'
    )
    settle()
    launch.assert_not_called()
    assert w.recommended_indicators[('video-downloader', 'flatpak')].get_visible()
    assert w.recommended_status.get_text() == ''

w.recommended_installed.pop(('video-downloader', 'flatpak'))
w.recommended_indicators[('video-downloader', 'flatpak')].hide()
with patch.object(app.subprocess, 'run', side_effect=[
        missing_flatpak, user_remote_result,
        app.subprocess.CompletedProcess([], 1, stdout='', stderr='installation failed')]), \
     patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
     patch.object(w, '_mensaje') as message:
    w._accion_app_recomendada(
        w.recommended_buttons[('video-downloader', 'flatpak')], 'video-downloader', 'flatpak'
    )
    settle()
    message.assert_called_once()
    assert w.recommended_status.get_text() == ''
    assert not w.recommended_indicators[('video-downloader', 'flatpak')].get_visible()

# La consulta por pestaña distingue formatos y detecta DEB descargados externamente.
with patch.object(w, '_comprobar_deb_recomendada',
                  side_effect=lambda package: package in {'gimp', 'google-chrome-stable'}), \
     patch.object(w, '_flatpaks_recomendadas_instaladas', return_value={video_id}), \
     patch.object(app.threading, 'Thread', ImmediateThread):
    w._cambiar_pestana_recomendadas(None, None, 2)
    settle()
    assert w.recommended_indicators[('gimp', 'deb')].get_visible()
    assert not w.recommended_indicators[('gimp', 'flatpak')].get_visible()
    assert w.recommended_indicators[('gimp', 'deb')].get_text() == app.traducir('Instalado')
    assert 'foreground="#258b45"' in w.recommended_indicators[('gimp', 'deb')].get_label()
    assert w.recommended_indicators[('google-chrome', 'deb-download')].get_visible()
    assert w.recommended_indicators[('video-downloader', 'flatpak')].get_visible()
    assert not w.recommended_buttons[('google-chrome', 'deb-download')].get_sensitive()
    with patch.object(app.Gio.AppInfo, 'launch_default_for_uri') as open_url:
        w._accion_app_recomendada(None, 'google-chrome', 'deb-download')
        open_url.assert_not_called()

with patch.object(w, '_comprobar_deb_recomendada', return_value=False), \
     patch.object(w, '_flatpaks_recomendadas_instaladas', side_effect=RuntimeError('test error')), \
     patch.object(app.threading, 'Thread', ImmediateThread):
    w._cambiar_pestana_recomendadas(None, None, 2)
    settle()
    assert not w.recommended_indicators[('video-downloader', 'flatpak')].get_visible()
    assert w.recommended_status.get_text() == app.traducir(
        'No se pudo comprobar el estado de algunas aplicaciones.')
    assert 'test error' in w.recommended_status.get_tooltip_text()

# Una lectura antigua no debe sobrescribir el resultado de una instalación posterior.
w.recommended_scan_generation += 1
w._marcar_recomendada_instalada('video-downloader', 'flatpak')
w._recomendadas_comprobadas(w.recommended_scan_generation - 1, {}, [])
assert w.recommended_indicators[('video-downloader', 'flatpak')].get_visible()

with patch.object(w, '_cambiar_pestana_recomendadas') as refresh:
    w.notebook.set_current_page(2)
    refresh.reset_mock()
    w._refrescar_recomendadas_al_volver(None, None)
    refresh.assert_called_once_with(w.notebook, None, 2)
w.notebook.set_current_page(0)

for app_id, definition in app.APLICACIONES_BACKUP.items():
    installed = app.subprocess.CompletedProcess([], 0, stdout='installed', stderr='')
    with patch.object(app.subprocess, 'run', return_value=installed), \
         patch.object(app.threading, 'Thread', ImmediateThread), \
         patch.object(app.Gio.Subprocess, 'new') as launch:
        w._accion_backup(w.backup_buttons[app_id], app_id)
        assert not w.backup_buttons[app_id].get_sensitive()
        settle()
        launch.assert_called_once_with(app.comando_host(definition['command']),
                                      app.Gio.SubprocessFlags.NONE)

    missing = app.subprocess.CompletedProcess(
        [], 1, stdout='', stderr='dpkg-query: no packages found matching ' + definition['package']
    )
    with patch.object(app.subprocess, 'run', return_value=missing), \
         patch.object(app.threading, 'Thread', ImmediateThread), \
         patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
         patch.object(w, '_instalar_aplicacion_backup') as install:
        w._accion_backup(w.backup_buttons[app_id], app_id)
        settle()
        install.assert_called_once_with(app_id)

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

# El refresco precede al diagnóstico y un fallo no se presenta como lectura actual.
w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
w.show_all()
settle()
for refresh_error in (None, 'Autorización cancelada'):
    calls = []
    def refresh(command):
        calls.append('refresh')
        assert command == ['test-refresh']
        return refresh_error
    def diagnose():
        calls.append('diagnose')
        return [{'name': 'Actualizaciones pendientes', 'status': 'ok',
                 'detail': '0 actualizaciones disponibles según los índices APT locales.', 'advice': ''}]
    def app_update(*args):
        calls.append('app')
        return {'status': 'current', 'detail': 'Al día'}
    with patch.object(app, 'formato_actualizacion', return_value='deb'), \
         patch.object(app, 'version_app', return_value='2.7.7'), \
         patch.object(app, 'es_flatpak', return_value=False), \
         patch.object(app, 'helper_mantenimiento', return_value='helper'), \
         patch.object(app, 'comando_pkexec', return_value=['test-refresh']), \
         patch.object(app.core_diagnostics, 'refresh_apt_indices', side_effect=refresh), \
         patch.object(app.core_diagnostics, 'run_diagnostics', side_effect=diagnose), \
         patch.object(app.core_updates, 'estado_actualizacion_app', side_effect=app_update), \
         patch.object(w, '_diagnostico_terminado', wraps=w._diagnostico_terminado) as finished:
        w._abrir_diagnostico()
        deadline = time.monotonic() + 5
        while w.diagnostico_en_curso and time.monotonic() < deadline:
            settle()
        assert not w.diagnostico_en_curso
        assert calls == ['refresh', 'diagnose', 'app']
        results = finished.call_args.args[1]
        pending = next(item for item in results if item['name'] == 'Actualizaciones pendientes')
        version = next(item for item in results if item['name'] == 'Versión de AiO Debian GUI')
        assert pending['status'] == ('unknown' if refresh_error else 'ok')
        assert version['status'] == ('unknown' if refresh_error else 'ok')
        w.ventana_diagnostico.destroy()
        settle()
w.destroy()

# La guía muestra dos bloques independientes y no ejecuta la instalación.
with patch.object(app, 'formato_actualizacion', return_value='flatpak'):
    w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
    w.show_all()
    settle()
    with patch.object(app.core_host_integration, 'commands',
                      return_value=('EXTRACCION', 'INSTALACION')) as generate:
        w._abrir_guia_integracion()
        settle()
        dialogs = [d for d in Gtk.Window.list_toplevels()
                   if isinstance(d, Gtk.Dialog) and d.get_title() == 'Guía de integración del anfitrión']
        assert len(dialogs) == 1
        dialog = dialogs[0]
        def children(widget):
            yield widget
            if isinstance(widget, Gtk.Container):
                for child in widget.get_children():
                    yield from children(child)
        widgets = list(children(dialog))
        views = [widget for widget in widgets if isinstance(widget, Gtk.TextView)]
        assert len(views) == 2 and all(not view.get_editable() for view in views)
        texts = [view.get_buffer().get_text(*view.get_buffer().get_bounds(), True) for view in views]
        assert texts == ['EXTRACCION', 'INSTALACION']
        buttons = {widget.get_label(): widget for widget in widgets if isinstance(widget, Gtk.Button)}
        buttons['Copiar extracción'].clicked()
        assert Gtk.Clipboard.get(app.Gdk.SELECTION_CLIPBOARD).wait_for_text() == 'EXTRACCION'
        buttons['Copiar instalación'].clicked()
        assert Gtk.Clipboard.get(app.Gdk.SELECTION_CLIPBOARD).wait_for_text() == 'INSTALACION'
        generate.assert_called_once()
        dialog.destroy()
    w.destroy()
print('GTK: selección, confirmación, exclusión Stable, diagnóstico, consola, resultados y adaptación en cuatro idiomas OK')
