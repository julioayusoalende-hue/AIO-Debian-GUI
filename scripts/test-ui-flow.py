#!/usr/bin/env python3
"""Flujos GTK de selección, diagnóstico, resultados y adaptación, sin mantenimiento real."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

from aio_core import health_dashboard as _hd
_ofrecer_real = _hd.HealthDashboard._ofrecer_solucion
_hd.HealthDashboard._ofrecer_solucion = lambda self, results: False

def settle():
    end = time.monotonic() + .18
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(.005)

def esperar_disposicion(ventana, ancho):
    paneles = ventana.paneles_principales
    orientacion = Gtk.Orientation.VERTICAL if ancho < 900 else Gtk.Orientation.HORIZONTAL
    # Un runner lento puede tardar en procesar el redimensionado: se reintenta
    # la petición en cada vuelta y se da más margen que el timeout de un clic.
    limite = time.monotonic() + 10
    while time.monotonic() < limite:
        settle()
        actual = ventana.get_size()[0]
        if abs(actual - ancho) > 1 or paneles.get_orientation() != orientacion:
            if abs(actual - ancho) > 1:
                ventana.resize(ancho, ventana.get_size()[1])
            continue
        if orientacion == Gtk.Orientation.VERTICAL:
            return
        if (not ventana.restaurar_proporcion_paneles
                and abs(ventana.panel_izquierdo.get_allocated_width() - paneles.get_position()) <= 1):
            return
    raise AssertionError(
        f"GTK no completó el redimensionado a {ancho}px "
        f"(ventana={ventana.get_size()[0]}, posición={paneles.get_position()}, "
        f"columna={ventana.panel_izquierdo.get_allocated_width()})")


for distro, version, expected in (
    ('debian', '13', ['appimage']),
    ('ayusos', '0.1', ['appimage']),
    ('ubuntu', '24.04', ['appimage']),
    ('ubuntu', '26.04', ['deb', 'appimage']),
    ('ubuntu', '26.10', ['deb', 'appimage']),
    ('ubuntu', '28.04', ['deb', 'appimage']),
):
    assert [canal['type'] for canal in app.canales_ghostty(
        {'ID': distro, 'VERSION_ID': version})] == expected

for os_release, esperado in (
    ('ID=ayusos\nVERSION_ID="0.1"\nPRETTY_NAME="AyusOS Linux 0.1 (base Debian 13)"\n',
     'AyusOS Linux 0.1'),
    ('ID=debian\nVERSION_ID="13"\nNAME="AyusOS Linux"\nPRETTY_NAME="AyusOS Linux 0.3"\n',
     'AyusOS Linux 0.3'),
    ('ID=debian\nVERSION_ID="13"\nLOGO=ayusos-logo\n', 'AyusOS Linux'),
):
    with patch.object(app, 'leer_texto', return_value=os_release):
        ayusos = app.datos_distribucion_anfitrion()
        assert app.distribucion_anfitrion() == 'debian'
        assert app.sistema_operativo().startswith(esperado)
    with patch.object(app, 'datos_distribucion_anfitrion', return_value=ayusos):
        ventana = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
        _, sistema = ventana.get_titlebar().get_custom_title().get_children()
        logo, nombre = sistema.get_children()
        assert logo.get_accessible().get_name() == 'Logotipo de AyusOS Linux'
        assert logo.get_pixbuf().get_width() == 16
        assert nombre.get_text() == esperado
        detalles = ventana._crear_detalles_sistema()
        scroll = next(w for w in detalles.get_content_area().get_children()
                      if isinstance(w, Gtk.ScrolledWindow))
        imagen = scroll.get_child().get_child().get_children()[0]
        assert imagen.get_accessible().get_name() == 'Logotipo de AyusOS Linux'
        assert imagen.get_pixbuf().get_width() == 100
        detalles.destroy()
        ventana.destroy()

with patch.object(app.urllib.request, 'urlopen') as request:
    request.return_value.__enter__.return_value.geturl.return_value = (
        "https://github.com/pkgforge-dev/ghostty-appimage/releases/tag/v1.4.0"
    )
    for arch in ('x86_64', 'aarch64'):
        assert app.url_appimage_ghostty(arch) == (
            f'https://github.com/pkgforge-dev/ghostty-appimage/releases/download/v1.4.0/'
            f'Ghostty-1.4.0-{arch}.AppImage'
        )

with patch.object(app.urllib.request, 'urlopen', side_effect=app.urllib.error.HTTPError(
        app.GHOSTTY_APPIMAGE_RELEASES, 403, 'Forbidden', {}, None)):
    assert app.url_appimage_ghostty('x86_64') == f'{app.GHOSTTY_APPIMAGE_RELEASES}/latest'

for distro, version, texto in (('debian', '13', 'Debian 13'), ('ubuntu', '26.04', 'Ubuntu 26.04')):
    with patch.object(app, 'datos_distribucion_anfitrion', return_value={'ID': distro, 'VERSION_ID': version}), \
         patch.object(app, 'version_app', return_value='1.0.2~preview3'), \
         patch.object(app, 'novedades_version', return_value='• Mejora <GTK>'):
        ventana = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
        titulo, sistema = ventana.get_titlebar().get_custom_title().get_children()
        nombre, boton_version, canal = titulo.get_children()
        assert canal is ventana.etiqueta_canal_actualizaciones
        version_app = boton_version.get_child()
        assert nombre.get_text() == 'AiO Debian'
        assert version_app.get_text() == '1.0.2~preview3'
        assert version_app.get_style_context().has_class('aio-header-version')
        logo, etiqueta_sistema = sistema.get_children()
        assert logo.get_storage_type() == Gtk.ImageType.PIXBUF
        assert etiqueta_sistema.get_text() == texto

        ventana.show_all()
        settle()
        cabecera = ventana.get_titlebar()
        _, y_sistema = sistema.translate_coordinates(cabecera, 0, 0)
        assert y_sistema + sistema.get_allocated_height() <= cabecera.get_allocated_height() - 3
        assert boton_version.get_can_focus()
        boton_version.clicked()
        settle()
        novedades = next(dialogo for dialogo in Gtk.Window.list_toplevels()
                         if isinstance(dialogo, Gtk.Dialog) and dialogo.get_transient_for() == ventana
                         and dialogo.get_title() == 'Novedades de esta versión')
        assert novedades.get_visible() and novedades.get_resizable()
        area = ventana.get_display().get_monitor_at_window(ventana.get_window()).get_workarea()
        assert novedades.get_default_size() == (min(820, area.width * 9 // 10),
                                                min(560, area.height * 9 // 10))
        scroll_notas = next(widget for widget in novedades.get_content_area().get_children()
                            if isinstance(widget, Gtk.ScrolledWindow))
        buffer = scroll_notas.get_child().get_buffer()
        assert buffer.get_text(*buffer.get_bounds(), True) == '• Mejora <GTK>'
        novedades.get_widget_for_response(Gtk.ResponseType.CLOSE).clicked()
        settle()
        assert not novedades.get_visible()
        ventana.btn_detalles_sistema.clicked()
        settle()
        dialogo = ventana.ventana_detalles_sistema
        assert dialogo.get_visible() and dialogo.get_transient_for() == ventana
        assert dialogo.get_size()[0] == ventana.get_size()[0]
        scroll = next(widget for widget in dialogo.get_content_area().get_children()
                      if isinstance(widget, Gtk.ScrolledWindow))
        detalles = scroll.get_child().get_child()
        logo_detalles, grid, *extras = detalles.get_children()
        assert logo_detalles.get_storage_type() == Gtk.ImageType.PIXBUF
        assert logo_detalles.get_accessible().get_name() == app.logo_distribucion(distro)[1]
        filas, _ = app.informacion_sistema()
        assert len(grid.get_children()) == 2 * len(filas)
        assert all(grid.get_child_at(1, i).get_selectable() for i in range(len(filas)))
        assert extras == ([ventana.nvidia_info_label] if distro == 'debian' else [])

        dialogo.close()
        settle()
        assert not dialogo.get_visible()
        ventana.resize(ventana.get_size()[0] + 80, ventana.get_size()[1])
        settle()
        ventana.btn_detalles_sistema.clicked()
        settle()
        assert ventana.ventana_detalles_sistema == dialogo
        assert dialogo.get_size()[0] == ventana.get_size()[0]
        dialogo.response(Gtk.ResponseType.CLOSE)
        assert not dialogo.get_visible()
        ventana.destroy()

with patch.object(app.Vte.Terminal, 'copy_clipboard_format') as copiar, \
     patch.object(app.Vte.Terminal, 'paste_clipboard') as pegar, \
     patch.object(app.Vte.Terminal, 'select_all') as seleccionar:
    ventana = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
    ventana.show_all()
    for tecla, accion in ((app.Gdk.KEY_C, copiar), (app.Gdk.KEY_V, pegar), (app.Gdk.KEY_A, seleccionar)):
        evento = app.Gdk.Event.new(app.Gdk.EventType.KEY_PRESS)
        evento.keyval = tecla
        evento.state = app.Gdk.ModifierType.CONTROL_MASK | app.Gdk.ModifierType.SHIFT_MASK
        assert ventana.terminal.emit('key-press-event', evento)
        accion.assert_called_once()

    with tempfile.TemporaryDirectory() as directorio, \
         patch.object(app.GLib, 'get_user_config_dir', return_value=directorio), \
         patch.object(ventana, '_mensaje') as mensaje:
        config = Path(directorio) / 'fastfetch/config.jsonc'
        config.parent.mkdir()
        config.write_text('// Configuración anterior\n', encoding='utf-8')
        menu = ventana.btn_comandos_terminal.get_popover().get_child()
        elementos = menu.get_children()
        assert [getattr(item, 'get_label', lambda: None)() for item in elementos[:-1]] == [
            'Limpiar', None, 'Fastfetch', 'Fastfetch', 'Aplicar diseño de Fastfetch',
            'Restaurar diseño anterior de Fastfetch', None, 'Sistema',
            'Abrir archivos como administrador', 'Análisis del arranque', 'Htop', 'Btop',
        ]
        separador, aplicar, restaurar = elementos[1], elementos[4], elementos[5]
        assert isinstance(elementos[6], Gtk.Separator)
        assert isinstance(separador, Gtk.Separator)
        assert aplicar.get_label() == 'Aplicar diseño de Fastfetch'
        assert restaurar.get_label() == 'Restaurar diseño anterior de Fastfetch'
        aplicar.clicked()
        assert config.read_bytes() == Path(app.FASTFETCH_LAYOUT).read_bytes()
        (copia,) = config.parent.glob('config.jsonc.*.bak')
        assert copia.read_text(encoding='utf-8') == '// Configuración anterior\n'
        assert str(copia) in mensaje.call_args.args[-1]
        ventana._aplicar_diseno_fastfetch(None)
        assert list(config.parent.glob('*.bak')) == [copia]
        restaurar.clicked()
        assert config.read_text(encoding='utf-8') == '// Configuración anterior\n'
        assert copia.exists()
        config.unlink()
        ventana._aplicar_diseno_fastfetch(None)
        ventana._restaurar_diseno_fastfetch(None)
        assert not config.exists()
        ventana._aplicar_diseno_fastfetch(None)
        config.write_text('// Diseño editado\n', encoding='utf-8')
        ventana._restaurar_diseno_fastfetch(None)
        assert config.read_text(encoding='utf-8') == '// Diseño editado\n'
    ventana.destroy()

for formato in ('appimage', 'flatpak', 'deb'):
    with patch.object(app, 'formato_actualizacion', return_value=formato), \
         patch.object(app, 'version_app', return_value='2.10.15'), \
         patch.object(app.threading, 'Thread') as worker, \
         patch.object(app.core_host_integration, 'prepare_host') as prepare:
        window = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False,
                                      'reloj_inicial_sincronizado': True})
        window.distribucion = 'ubuntu'
        with patch.object(window, '_consultar_estados_tareas') as status:
            window._preparar_anfitrion_al_iniciar()
            if formato == 'deb':
                worker.assert_not_called()
                prepare.assert_not_called()
                status.assert_called_once_with(inicial=True)
            else:
                worker.assert_called_once()
                worker.call_args.kwargs['target']()
                prepare.assert_called_once_with(formato, '2.10.15')
                settle()
                status.assert_called_once_with(inicial=True)
        window.destroy()

for sincronizado in (True, False):
    window = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
    window.distribucion = 'debian'
    with patch.object(app, 'formato_actualizacion', return_value='deb'), \
         patch.object(app.threading, 'Thread') as worker, \
         patch.object(app.core_clock, 'sincronizar', return_value=sincronizado), \
         patch.object(app, 'guardar_preferencias') as save, \
         patch.object(window, '_consultar_estados_tareas') as status:
        window._preparar_anfitrion_al_iniciar()
        assert window.sincronizando_reloj and not window.btn_iniciar.get_sensitive()
        assert not window.pagina_software.get_sensitive()
        status.assert_not_called()
        worker.call_args.kwargs['target']()
        settle()
        status.assert_called_once_with(inicial=True)
        assert not window.sincronizando_reloj and window.pagina_software.get_sensitive()
        assert window.aviso_reloj_inicial is (not sincronizado)
        if sincronizado:
            assert save.call_args.args[0]['reloj_inicial_sincronizado'] is True
            worker.reset_mock()
            window._preparar_anfitrion_al_iniciar()
            worker.assert_not_called()
        else:
            save.assert_not_called()
    window.destroy()

preferencias = {'idioma': 'es', 'tema': 'claro', 'modo_simple': False}
paquete_instalado = app.paquete_instalado
for flatpak, snap in ((False, False), (True, False), (False, True), (True, True)):
    with patch.object(app, 'es_flatpak', return_value=False), \
         patch.object(app.shutil, 'which', return_value='/usr/bin/flatpak' if flatpak else None), \
         patch.object(app, 'paquete_instalado',
                      side_effect=lambda nombre: snap if nombre == 'snapd' else paquete_instalado(nombre)):
        ventana = app.VentanaPrincipal(preferencias)
        ventana.show_all()
        for tarea, instalada in (('flatpak-update', flatpak), ('snap-update', snap)):
            assert (tarea in ventana.switches) is instalada
            if instalada:
                assert ventana.filas[tarea].get_parent() is ventana.grupos_tareas[0].get_child()
        assert ventana.botones_preset["flatpak"].get_visible() is flatpak
        assert ('flatpak-setup' in ventana.switches) is not flatpak
        estandar = ventana.botones_preset["estandar"]
        assert estandar.get_style_context().has_class("suggested-action")
        seleccion_inicial = ventana._pasos_seleccionados()
        assert "autopurge" not in seleccion_inicial
        ventana.botones_preset["completo"].clicked()
        assert set(ventana._pasos_seleccionados()) == set(seleccion_inicial) | {"autopurge"}
        if flatpak:
            ventana.botones_preset["flatpak"].clicked()
            assert ventana._pasos_seleccionados() == ["flatpak-update"]
        estandar.clicked()
        assert ventana._pasos_seleccionados() == seleccion_inicial
        ventana.destroy()

for language in ('es', 'en', 'fr', 'zh'):
    with patch.object(app.shutil, 'which', return_value='/usr/bin/flatpak'):
        w = app.VentanaPrincipal({'idioma': language, 'tema': 'claro', 'modo_simple': False})
    w.show_all()
    settle()
    assert w.notebook.get_n_pages() == 5
    assert w.notebook.page_num(w.pagina_terminal) == -1
    assert w.btn_terminal_cabecera.get_tooltip_text() == app.traducir('Terminal')
    assert w.btn_terminal_cabecera.get_image().get_icon_name()[0] == 'utilities-terminal-symbolic'
    firmware = w.grupos_tareas[-1]
    assert firmware.get_accessible().get_name() == app.traducir('Firmware')
    assert firmware.get_child().get_ancestor(Gtk.Notebook) is w.notebook
    assert not firmware.get_expanded()
    assert w.notebook.get_nth_page(4) == w.grub_pagina
    assert w.notebook.get_tab_label_text(w.grub_pagina) == app.traducir('Inicio')
    assert w.grub_pagina.get_style_context().has_class("aio-page")
    grub_card = w.grub_formulario.get_ancestor(Gtk.Frame)
    assert grub_card.get_style_context().has_class("aio-card")
    assert not w.grub_mensaje.get_visible()
    assert not w.grub_formulario.get_sensitive()
    if language == 'es':
        grub_status = {
            'entries': [{'id': 'test-debian', 'title': 'Debian GNU/Linux'}],
            'settings': {'GRUB_DEFAULT': 'test-debian', 'GRUB_TIMEOUT': '8',
                         'GRUB_TIMEOUT_STYLE': 'menu'},
            'revision': 'test-revision',
        }
        w._grub_finalizado('status', grub_status, None)
        assert w.grub_formulario.get_sensitive()
        assert w.grub_entrada.get_active_id() == 'test-debian'
        assert w.grub_tiempo.get_text() == '8'
        assert w.grub_estilo.get_active_id() == 'menu'
        assert w.grub_restaurar.get_sensitive()
        w.grub_tiempo.set_text('1000')
        with patch.object(w, '_mensaje') as message:
            w._accion_grub(None, 'apply')
            assert 'Tiempo de espera no válido' in message.call_args.args
        with patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
             patch.object(app.threading, 'Thread') as thread:
            w.grub_tiempo.set_text('12')
            w._accion_grub(None, 'apply')
            assert app.json.loads(thread.call_args.kwargs['args'][0][1]) == {
                'revision': 'test-revision',
                'settings': {**grub_status['settings'], 'GRUB_TIMEOUT': '12'},
            }
            assert not w.grub_pagina.get_sensitive()
            thread.return_value.start.assert_called_once()
        w._grub_finalizado('apply', grub_status, None)
        assert w.grub_pagina.get_sensitive()
        inherited = {**grub_status, 'effective': grub_status['settings'], 'settings': {}}
        w._grub_finalizado('status', inherited, None)
        assert w.grub_entrada.get_active_id() == 'test-debian'
        assert w.grub_tiempo.get_text() == '8'
        assert w.grub_estilo.get_active_id() == 'menu'
        assert not w.grub_restaurar.get_sensitive()
        with patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
             patch.object(app.threading, 'Thread') as thread:
            w._accion_grub(None, 'apply')
            thread.assert_not_called()
            w.grub_tiempo.set_text('12')
            w._accion_grub(None, 'apply')
            assert app.json.loads(thread.call_args.kwargs['args'][0][1])['settings'] == {'GRUB_TIMEOUT': '12'}
        w._grub_finalizado('apply', grub_status, None)
    assert [w.notebook.get_tab_label_text(page) for page in w.notebook.get_children()] == [
        app.traducir(name) for name in
        ('Configuración y mantenimiento', 'Gestor de software', 'Apps recomendadas', 'Backup', 'Inicio')
    ]
    if language == 'es':
        column = w.pagina_software.view.get_column(0)
        indicator, package_name = column.get_cells()
        model = Gtk.ListStore(str, str, str, str, str)
        for status, expected in (
            ('Instalado', '✓'), ('Actualizable', '✓'), ('Disponible', ''), ('Activo', ''),
        ):
            row = model.append(('Paquete de prueba', 'prueba', '1.0', status, ''))
            column.cell_set_cell_data(model, row, False, False)
            assert indicator.get_property('text') == expected
            assert package_name.get_property('text') == 'Paquete de prueba'
        gestor = w.pagina_software
        backend = sys.modules['software_manager.backend']
        apt_record = ('Package: prueba\nVersion: 2.0\nArchitecture: amd64\n'
                      'Description: Herramienta de prueba\n Descripción larga\n'
                      'Depends: base (>= 1),\n alternativa | otra\nInstalled-Size: 128\n')
        with patch.object(backend, 'run', return_value=apt_record) as run:
            gestor.view.get_selection().select_iter(
                gestor.store.append(('prueba', 'prueba:amd64', '2.0', 'Disponible', 'amd64')))
            texto = gestor.details_view.get_buffer()
            limite = time.monotonic() + 2
            while gestor.details_request is not None or gestor.details_timer:
                assert time.monotonic() < limite, 'No se cargó la ficha del paquete'
                settle()
            ficha = texto.get_text(*texto.get_bounds(), False)
            assert 'Herramienta de prueba' in ficha
            assert 'Dependencias: base (>= 1), alternativa | otra' in ficha
            run.assert_called_once_with(
                ['/usr/bin/apt-cache', 'show', '--', 'prueba:amd64=2.0'], timeout=8)
        with patch.object(backend, 'run', side_effect=[
                'Package: prueba\nVersion: 1.0\nArchitecture: amd64\n'
                'Description: Herramienta de prueba\n',
                'Candidate: 2.0\n']) as run:
            metadata = backend.deb_details('prueba:amd64', '1.0', 'amd64', updatable=True)
        assert metadata.get('Versión disponible') == '2.0'
        assert run.call_args_list[1].args[0] == [
            '/usr/bin/apt-cache', 'policy', '--', 'prueba']
        gestor.store.clear()
        flatpak_info = ('Ejemplo - Editor de notas\n  sin conexión\n\n'
                        '     ID: org.example.Editor\nRuntime: org.gnome.Platform/x86_64/48\n'
                        '   Arch: x86_64\nLicense: GPL-3.0-or-later\n')
        ref = 'app/org.example.Editor/x86_64/stable'
        with patch.object(backend, 'run', return_value=flatpak_info) as run:
            metadata = backend.flatpak_details('user', 'flathub', ref, installed=False)
            run.assert_called_once_with(
                ['/usr/bin/flatpak', '--user', 'remote-info', '--', 'flathub', ref], timeout=12)
        gestor.render_details(metadata, ('Ejemplo', ref, '', 'Disponible', 'flathub'), 1)
        texto = gestor.details_view.get_buffer()
        assert 'Editor de notas sin conexión' in texto.get_text(*texto.get_bounds(), False)
        assert 'Entorno de ejecución requerido: org.gnome.Platform/x86_64/48' in texto.get_text(
            *texto.get_bounds(), False)
        instalado = f'Ejemplo\t{ref}\t1.0\tflathub\n'
        otra_ref = 'app/org.example.Other/x86_64/stable'
        cat = f'Ejemplo\t{ref}\t2.0\nOtra\t{otra_ref}\t1.0\n'
        with patch.object(backend, 'remotes', return_value=[
            ('flathub', '', ''), ('otro', '', ''), ('pausado', '', 'disabled'),
        ]), patch.object(backend, 'run', side_effect=[instalado, cat, ref + '\n', cat]) as run:
            filas, errores, _actualizables = backend.flatpaks('user')
            assert not errores
            assert {(fila[1], fila[4]): fila[3] for fila in filas} == {
                (ref, 'flathub'): 'Actualizable', (otra_ref, 'flathub'): 'Disponible',
                (ref, 'otro'): 'Disponible', (otra_ref, 'otro'): 'Disponible',
            }
            assert run.call_args_list[2].args[0] == [
                '/usr/bin/flatpak', '--user', 'remote-ls', '--app', '--updates', '--all',
                '--arch=*', '--columns=ref,version', '--', 'flathub',
            ]
        with patch.object(backend, 'remotes', return_value=[('flathub', '', '')]), \
             patch.object(backend, 'run', side_effect=[instalado, cat, RuntimeError('sin conexión')]):
            parciales, errores, _actualizables = backend.flatpaks('system')
            assert errores == ['flathub — sin conexión']
            assert next(fila for fila in parciales if fila[1] == ref)[3] == 'Instalado'
        with patch.object(gestor, 'load'):
            gestor.page.set_active(1)
            assert gestor.filters.get_visible()
            gestor.rows, gestor.catalogue_errors = filas, []
            gestor.filters.set_active(3)
            settle()
            assert len(gestor.store) == 1 and gestor.store[0][1] == ref
            gestor.rows = parciales
            gestor.filter_rows()
            assert gestor.status.get_text() == 'No hay actualizaciones disponibles.'
            gestor.catalogue_errors = errores
            gestor.filter_rows()
            assert 'No se pudieron consultar todos los remotos' in gestor.status.get_text()
            gestor.catalogue_errors = []
            gestor.filters.set_active(0)
            gestor.page.set_active(2)
            assert not gestor.filters.get_visible()
            gestor.page.set_active(0)
            assert gestor.filters.get_visible()
            gestor.rows = []
            settle()
    assert set(w.backup_buttons) == {
        'timeshift', 'deja-dup', 'backup', 'restore', 'folder',
        'desktop-backup', 'desktop-restore',
    }
    assert w.backup_buttons['backup'].get_label() == app.traducir('Copiar repositorios APT')
    assert w.backup_buttons['restore'].get_label() == app.traducir('Restaurar repositorios APT')
    for app_id in app.APLICACIONES_BACKUP:
        button = w.backup_buttons[app_id]
        icon, text, action = button.get_parent().get_children()
        assert action is button
        assert icon.get_storage_type() == Gtk.ImageType.PIXBUF
        pixbuf = icon.get_pixbuf()
        assert max(pixbuf.get_width(), pixbuf.get_height()) == 48
        name, description = text.get_children()
        assert name.get_text() == app.APLICACIONES_BACKUP[app_id]['name']
        assert description.get_text() == app.traducir(app.APLICACIONES_BACKUP[app_id]['description'])
    w.notebook.set_current_page(3)
    w.resize(600, 900)
    settle()
    assert w.get_size()[0] <= 601, (language, w.get_size())
    assert all(button.get_mapped() for button in w.backup_buttons.values())
    w.notebook.set_current_page(2)
    settle()
    assert w.get_size()[0] <= 601, (language, w.get_size())
    assert all(button.get_mapped() for button in w.recommended_buttons.values())
    assert len(w.recommended_grid.get_children()) == 30
    first = w.recommended_grid.get_child_at_index(0)
    second = w.recommended_grid.get_child_at_index(1)
    assert first.get_allocation().x == second.get_allocation().x
    w.resize(1160, 900)
    settle()
    assert first.get_allocation().y == second.get_allocation().y
    assert first.get_allocation().x < second.get_allocation().x
    expected_names = ['Audacity', 'Bitwarden', 'Brave', 'btop', 'Celluloid', 'Deluge', 'Feishin', 'Flameshot', 'Gear Lever', 'Ghostty', 'GIMP',
                      'Google Chrome', 'GParted', 'Gradia', 'HandBrake', 'Heroic Games Launcher', 'HPLIP (HP Toolbox)', 'htop', 'Kdenlive', 'Kitty', 'ONLYOFFICE Desktop Editors', 'Plex', 'qBittorrent', 'RetroArch', 'Spotify', 'Steam', 'Switcheroo', 'Video Downloader', 'VLC', 'Zoom Workplace']
    assert [item['name'] for item in app.APPS_RECOMENDADAS] == expected_names
    for index, name in enumerate(expected_names):
        card = w.recommended_grid.get_child_at_index(index).get_child()
        assert card.get_style_context().has_class("aio-card")
        contents = card.get_child().get_children()
        header = contents[0].get_children()
        assert isinstance(header[0], Gtk.Image)
        assert header[1].get_text() == name
        image = header[0]
        if 'bundled_icon' in app.APPS_RECOMENDADAS[index]:
            assert image.get_storage_type() == Gtk.ImageType.PIXBUF
            pixbuf = image.get_pixbuf()
            assert max(pixbuf.get_width(), pixbuf.get_height()) == 48
        else:
            assert image.get_storage_type() == Gtk.ImageType.ICON_NAME
            assert image.get_pixel_size() == 48
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
        ('audacity', 'deb'), ('btop', 'deb'), ('celluloid', 'deb'), ('deluge', 'deb'), ('flameshot', 'deb'), ('gimp', 'deb'), ('gparted', 'deb'), ('handbrake', 'deb'),
        ('hplip-gui', 'deb'), ('htop', 'deb'), ('kdenlive', 'deb'), ('kitty', 'deb'), ('qbittorrent', 'deb'), ('retroarch', 'deb'), ('vlc', 'deb')
    }
    assert ('feishin', 'flatpak') in w.recommended_buttons
    assert ('steam', 'deb-download') in w.recommended_buttons
    assert ('heroic', 'deb-download') in w.recommended_buttons
    assert ('feishin', 'deb-download') in w.recommended_buttons
    assert ('brave', 'flatpak') in w.recommended_buttons
    assert ('brave', 'deb-download') in w.recommended_buttons
    assert ('gearlever', 'flatpak') in w.recommended_buttons
    assert ('plex', 'flatpak') in w.recommended_buttons
    assert ('google-chrome', 'deb-download') in w.recommended_buttons
    assert ('zoom', 'deb-download') in w.recommended_buttons
    assert ('onlyoffice', 'deb-download') in w.recommended_buttons
    for app_id, flatpak_id in (
        ('audacity', 'org.audacityteam.Audacity'),
        ('bitwarden', 'com.bitwarden.desktop'),
        ('flameshot', 'org.flameshot.Flameshot'),
        ('gradia', 'be.alexandervanhee.gradia'),
        ('onlyoffice', 'org.onlyoffice.desktopeditors'),
        ('heroic', 'com.heroicgameslauncher.hgl'),
        ('kdenlive', 'org.kde.kdenlive'),
        ('retroarch', 'org.libretro.RetroArch'),
        ('steam', 'com.valvesoftware.Steam'),
        ('deluge', 'org.deluge_torrent.deluge'),
        ('google-chrome', 'com.google.Chrome'),
        ('qbittorrent', 'org.qbittorrent.qBittorrent'),
        ('zoom', 'us.zoom.Zoom'),
    ):
        assert (app_id, 'flatpak') in w.recommended_buttons
        assert {'type': 'flatpak', 'app_id': flatpak_id} in w.canales_recomendados[app_id]
    assert {tipo for app_id, tipo in w.recommended_buttons if app_id == 'ghostty'} == {
        canal['type'] for canal in app.canales_ghostty(app.datos_distribucion_anfitrion())
    }
    w.notebook.set_current_page(0)
    settle()
    if language != 'es':
        assert app.traducir('Operación en curso') != 'Operación en curso'
    assert w.ventana_detalles_sistema is None
    assert not w.expansor_consola.get_expanded()
    w.expansor_consola.set_expanded(True)
    settle()
    assert w.marco_consola.get_allocated_height() >= 200
    assert w.btn_iniciar.get_mapped()
    w.expansor_consola.set_expanded(False)
    assert all(not grupo.get_expanded() for grupo in w.grupos_tareas)
    assert not w.seleccion_detalle.get_expanded()
    assert not w.chk_sin_contrasena.get_ancestor(Gtk.Expander).get_expanded()
    assert all(isinstance(check, Gtk.CheckButton) for check, _ in w.switches.values())
    assert isinstance(w.chk_sin_contrasena, Gtk.Switch)
    assert not any(t in w._pasos_seleccionados() for t in ('backports-kernel-mesa', 'revertir-backports', 'nvidia-driver', 'ubuntu-hwe'))
    w.botones_preset["flatpak"].clicked()
    assert w._pasos_seleccionados() == ['flatpak-update']
    assert w.btn_iniciar.get_label() == app.traducir('Ejecutar 1 tarea')
    if language == 'es':
        with patch.object(w, 'is_active', return_value=True), \
             patch.object(w, 'get_focus', return_value=None), \
             patch.object(w, '_iniciar') as start, \
             patch.object(w, '_iniciar_terminal'):
            for page in range(w.notebook.get_n_pages()):
                w.notebook.set_current_page(page)
                for key in (app.Gdk.KEY_Return, app.Gdk.KEY_KP_Enter):
                    event = SimpleNamespace(keyval=key, state=0)
                    start.reset_mock()
                    assert w._al_pulsar_tecla(w, event) is (page == 0)
                    assert start.call_count == (1 if page == 0 else 0)
            w.notebook.set_current_page(0)
            event = SimpleNamespace(keyval=app.Gdk.KEY_Return,
                                    state=app.Gdk.ModifierType.CONTROL_MASK)
            start.reset_mock()
            assert not w._al_pulsar_tecla(w, event)
            start.assert_not_called()
        w._actualizar_sensibilidad()
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
    w.botones_preset["estandar"].clicked()
    assert 'autoremove' not in w._pasos_seleccionados()
    assert not w.switches['autoremove'][0].get_active()
    assert not w.switches['autopurge'][0].get_active()
    w.switches['autoremove'][0].set_active(True)
    w.switches['autopurge'][0].set_active(True)
    assert 'autopurge' in w._pasos_seleccionados()
    assert 'autoremove' not in w._pasos_seleccionados()
    w.switches['autoremove'][0].set_active(True)
    assert 'autoremove' in w._pasos_seleccionados()
    assert 'autopurge' not in w._pasos_seleccionados()
    w.botones_preset["estandar"].clicked()
    assert 'upgrade' in w._pasos_seleccionados()

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
    w._procesar('[-] Aviso de un paso que se completó')
    w._procesar('##RESULT:upgrade:0')
    assert w.resultados_tareas['upgrade'][1] == 'Completada'
    w._procesar('##STEP:2:2:Limpiar paquetes')
    w._procesar('E: Fallo en la limpieza')
    w._procesar('##RESULT:autoclean:1')
    assert w.errores_tareas == {'autoclean': 'E: Fallo en la limpieza'}
    if language == 'es':
        manual = {"fecha": "2026-11-19T10:00:00+00:00", "tareas": ["upgrade"],
                  "resultado": "correcto", "detalles": {"upgrade": {"estado": "Completada"}}}
        scheduled = {"started": "2026-11-20T09:00:00+00:00", "status": "error",
                     "tasks": {"autoclean": "error"},
                     "errors": {"autoclean": "E: Fallo en la limpieza"}}

        def revisar_historial(dialogo):
            hijos = dialogo.get_content_area().get_children()
            selector = next(hijo for hijo in hijos if isinstance(hijo, Gtk.ComboBoxText))
            panel = next(hijo for hijo in hijos if isinstance(hijo, Gtk.ScrolledWindow))
            limite = time.monotonic() + 3
            while len(selector.get_model()) < 2 and time.monotonic() < limite:
                settle()
            assert len(selector.get_model()) == 2
            buffer = panel.get_child().get_buffer()
            selector.set_active(0)
            assert "Programada" in selector.get_active_text()
            assert "E: Fallo en la limpieza" in buffer.get_text(*buffer.get_bounds(), False)
            selector.set_active(1)
            assert "Manual" in selector.get_active_text()
            assert "Completada" in buffer.get_text(*buffer.get_bounds(), False)
            return Gtk.ResponseType.CLOSE

        with patch.object(app, 'leer_historial', return_value=[manual]), \
             patch.object(app.core_host_integration, 'read_scheduler_report',
                          return_value={"history": [scheduled]}), \
             patch.object(Gtk.Dialog, 'run', revisar_historial):
            w._mostrar_historial(None)

        for tareas, esperada, alcance in (
                ({"autoclean": "error"}, "autoclean", False),
                ({"upgrade": "success", "flatpak-update": "error",
                  "rebootcheck": "not-run"}, "flatpak-update", True)):
            ejecucion = {**scheduled, "tasks": tareas}
            fallo_programado = app.core_history.registros_programados({"history": [ejecucion]})[0]
            with patch.object(Gtk.Dialog, 'run', return_value=Gtk.ResponseType.OK), \
                 patch.object(w, '_tareas_disponibles_para_reintento', return_value=set(tareas)), \
                 patch.object(w, '_comprobar_mantenimiento') as comprobar:
                w._reintentar_mantenimiento(fallo_programado)
            comprobar.assert_called_once_with(
                [esperada], reintento_de={'fecha': scheduled['started'], 'origen': 'Programada'},
                flatpak_sistema=alcance,
            )

        huella = 'a' * 64
        cambios = app.base64.b64encode(b'Purg old-package [1]').decode()
        peticion = f'##CLEANUP-REVIEW:--purge:{huella}:{cambios}'
        with patch.object(w, 'proceso', Mock()) as proceso:
            canal = proceso.get_stdin_pipe.return_value
            with patch.object(Gtk.Dialog, 'run', return_value=Gtk.ResponseType.OK):
                w._procesar(peticion)
            canal.write_all.assert_called_once_with((huella + '\n').encode(), None)
            canal.reset_mock()
            with patch.object(Gtk.Dialog, 'run', return_value=Gtk.ResponseType.CANCEL):
                w._procesar(peticion)
            canal.write_all.assert_called_once_with(b'omitir\n', None)
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
    for tarea, package in (('autoremove', 'old-kernel'), ('upgrade', 'unsafe-package')):
        warning = f'Aviso: la simulación de {tarea if tarea == "autoremove" else "upgrade"} propone eliminar paquetes: {package}'
        w.en_curso = True
        with patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
             patch.object(w, '_continuar_mantenimiento') as continue_maintenance:
            w._terminar_preflight([tarea], app.core_preflight.Report(False, [warning]), None)
        continue_maintenance.assert_called_once_with([tarea], upgrade_plan=None, autoremove_plan=None)
    w.en_curso = True
    with patch.object(w, '_mensaje') as blocked_message, \
         patch.object(w, '_continuar_mantenimiento') as continue_maintenance:
        w._terminar_preflight(['upgrade'], app.core_preflight.Report(True, [warning]), None)
    blocked_message.assert_called_once()
    continue_maintenance.assert_not_called()
    if language == 'es':
        def comprobar_scroll(dialogo):
            dialogo.show_all()
            settle()
            scroll = next(widget for widget in dialogo.get_content_area().get_children()
                          if isinstance(widget, Gtk.ScrolledWindow))
            assert scroll.get_allocated_height() > dialogo.get_allocated_height() // 2
            ajuste = scroll.get_vadjustment()
            assert ajuste.get_upper() > ajuste.get_page_size()
            ajuste.set_value(ajuste.get_upper() - ajuste.get_page_size())
            assert ajuste.get_value() > 0
            buf = scroll.get_child().get_buffer()
            assert buf.get_text(*buf.get_bounds(), True).endswith('Paquete 261')
            for respuesta in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.OK):
                assert dialogo.get_widget_for_response(respuesta).get_mapped()
            return Gtk.ResponseType.CANCEL

        w.en_curso = True
        informe = app.core_preflight.Report(False, ['Resultado de la simulación'],
                                           [f'Paquete {n}' for n in range(1, 262)])
        with patch.object(Gtk.MessageDialog, 'run', comprobar_scroll):
            w._terminar_preflight(['upgrade'], informe, None)
        assert not w.en_curso
    w.en_curso = False

    for width in (1160, 700, 600, 1161, 1400):
        w.resize(width, 900)
        esperar_disposicion(w, width)
        actual = w.get_size()[0]
        assert actual <= width + 1, (language, width, actual)
        panels = w.paneles_principales
        if actual < 900:
            assert panels.get_orientation() == Gtk.Orientation.VERTICAL, (language, width, actual)
        else:
            assert panels.get_orientation() == Gtk.Orientation.HORIZONTAL, (language, width, actual)
            left, right = w.panel_izquierdo, w.panel_derecho
            assert left.get_allocated_width() > right.get_allocated_width(), (
                language, width, actual, left.get_allocated_width(), right.get_allocated_width())
            lx = left.translate_coordinates(w, 0, 0)[0]
            rx = right.translate_coordinates(w, 0, 0)[0]
            assert panels.get_handle_window().is_visible()
            assert lx + left.get_allocated_width() < rx
        if os.environ.get('AIO_UI_SCREENSHOTS') and width in (600, 1160) and language == 'es':
            directory = Path(os.environ['AIO_UI_SCREENSHOTS'])
            directory.mkdir(parents=True, exist_ok=True)
            window = w.get_window()
            shot = app.Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
            shot.savev(str(directory / f'ui-{width}.png'), 'png', [], [])
    if language == 'es':
        panels.set_position(730)
        esperar_disposicion(w, 1400)
        ancho_izq = left.get_allocated_width()
        ancho_der = right.get_allocated_width()
        assert abs(ancho_izq - 730) <= 1
        ratio = ancho_izq / (ancho_izq + ancho_der)
        w.resize(1520, 900)
        esperar_disposicion(w, 1520)
        assert left.get_allocated_width() > ancho_izq
        assert right.get_allocated_width() > ancho_der
        assert abs(panels.get_position() / (left.get_allocated_width() + right.get_allocated_width()) - ratio) < 0.005
        w.seleccion_detalle.set_expanded(True)
        w.grupos_tareas[0].set_expanded(True)
        w.resize(700, 900)
        esperar_disposicion(w, 700)
        assert w.seleccion_detalle.get_expanded() and w.grupos_tareas[0].get_expanded()
        w.seleccion_detalle.set_expanded(False)
        w.resize(1520, 900)
        esperar_disposicion(w, 1520)
        assert not w.seleccion_detalle.get_expanded()
        assert w.grupos_tareas[0].get_expanded()
        w.grupos_tareas[0].set_expanded(False)
        assert abs(panels.get_position() / (left.get_allocated_width() + right.get_allocated_width()) - ratio) < 0.005
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

# Al abrir la pestaña de apps recomendadas se marcan solas las ya instaladas.
wrec = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
wrec.show_all()
settle()
with patch.object(app.VentanaPrincipal, '_comprobar_deb_recomendada', staticmethod(lambda paquete: paquete == 'btop')), \
     patch.object(app.VentanaPrincipal, '_flatpaks_recomendadas_instaladas', staticmethod(lambda: set())):
    assert not wrec.recommended_indicators[('btop', 'deb')].get_visible()
    wrec.notebook.set_current_page(wrec.notebook.page_num(wrec.pagina_recomendadas))
    limite = time.monotonic() + 5
    while not wrec.recommended_indicators[('btop', 'deb')].get_visible() and time.monotonic() < limite:
        settle()
    assert wrec.recommended_indicators[('btop', 'deb')].get_visible()
    assert not wrec.recommended_indicators[('htop', 'deb')].get_visible()
wrec.destroy()

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
with patch.object(w, 'flatpak_presente', True), \
     patch.object(w, '_comprobar_deb_recomendada',
                  side_effect=lambda package: package in {'gimp', 'google-chrome-stable'}), \
     patch.object(w, '_flatpaks_recomendadas_instaladas', return_value={video_id}), \
     patch.object(app.threading, 'Thread', ImmediateThread):
    w._cambiar_pestana_recomendadas(None, w.pagina_recomendadas, 3)
    settle()
    assert w.recommended_indicators[('gimp', 'deb')].get_visible()
    assert not w.recommended_indicators[('gimp', 'flatpak')].get_visible()
    assert w.recommended_indicators[('gimp', 'deb')].get_text() == '✓ ' + app.traducir('Instalado')
    assert w.recommended_indicators[('google-chrome', 'deb-download')].get_visible()
    assert w.recommended_indicators[('video-downloader', 'flatpak')].get_visible()
    assert not w.recommended_buttons[('google-chrome', 'deb-download')].get_sensitive()
    with patch.object(app.Gio.AppInfo, 'launch_default_for_uri') as open_url:
        w._accion_app_recomendada(None, 'google-chrome', 'deb-download')
        open_url.assert_not_called()

with patch.object(w, 'flatpak_presente', True), \
     patch.object(w, '_comprobar_deb_recomendada', return_value=False), \
     patch.object(w, '_flatpaks_recomendadas_instaladas', side_effect=RuntimeError('test error')), \
     patch.object(app.threading, 'Thread', ImmediateThread):
    w._cambiar_pestana_recomendadas(None, w.pagina_recomendadas, 3)
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
    refresh.assert_called_once_with(w.notebook, w.pagina_recomendadas, 2)
w.notebook.set_current_page(0)

# Selección múltiple: puede mezclar formatos, cambiar de formato y reintentar los fallos.
w.recommended_multi.set_active(True)
assert not w.recommended_install.get_sensitive()
assert not w.recommended_buttons[('google-chrome', 'deb-download')].get_sensitive()
for key in (('deluge', 'deb'), ('deluge', 'flatpak'), ('gparted', 'deb')):
    w.recommended_buttons[key].clicked()
def resultados_recomendados():
    return {item['id'] for item, tarjeta in zip(app.APPS_RECOMENDADAS, w.recommended_grid.get_children())
            if tarjeta.get_child_visible()}

w.recommended_search.set_text('  KDEN  ')
assert resultados_recomendados() == {'kdenlive'}
w.recommended_search.set_text('juegos')
assert {'steam', 'heroic', 'retroarch'} <= resultados_recomendados()
w.recommended_category.set_active_id('Juegos')
assert resultados_recomendados() == {'steam', 'heroic', 'retroarch'}
w.recommended_search.set_text('steam')
assert resultados_recomendados() == {'steam'}
w.recommended_category.set_active_id('Multimedia')
assert not resultados_recomendados()
w.recommended_category.set_active(0)
w.recommended_search.set_text('nucleos libretro')
assert resultados_recomendados() == {'retroarch'}
w.recommended_search.set_text('sin-coincidencias-xyz')
assert not resultados_recomendados()
assert w.recommended_install.get_sensitive()
assert w.recommended_selection == {'deluge': 'flatpak', 'gparted': 'deb'}
w.recommended_search.set_text('')
assert len(resultados_recomendados()) == len(app.APPS_RECOMENDADAS)
assert w.recommended_install.get_label() == app.traducir('Instalar selección (%d)') % 2
assert w.recommended_buttons[('deluge', 'flatpak')].get_label().startswith('✓ ')
assert not w.recommended_buttons[('deluge', 'deb')].get_label().startswith('✓ ')

def revisar_seleccion(dialogo):
    scroll = next(widget for widget in dialogo.get_content_area().get_children()
                  if isinstance(widget, Gtk.ScrolledWindow))
    filas = scroll.get_child().get_child().get_children()
    assert [[widget.get_text() for widget in fila.get_children() if isinstance(widget, Gtk.Label)]
            for fila in filas] == [['Deluge', 'Flatpak'], ['GParted', 'DEB (APT)']]
    filas[1].get_children()[-1].clicked()
    assert w.recommended_selection == {'deluge': 'flatpak'}
    return Gtk.ResponseType.CLOSE

with patch.object(Gtk.Dialog, 'run', revisar_seleccion):
    w.recommended_review.clicked()
w.recommended_buttons[('gparted', 'deb')].clicked()

with patch.object(app.threading, 'Thread', ImmediateThread), \
     patch.object(w, '_ejecutar_instalacion_recomendada', side_effect=['falló Deluge', None, None]) as install, \
     patch.object(w, '_mensaje') as message:
    w.recommended_install.clicked()
    settle()
    assert [(x.args[0]['id'], x.args[1]['type']) for x in install.call_args_list] == [
        ('deluge', 'flatpak'), ('gparted', 'deb'),
    ]
    assert w.recommended_selection == {'deluge': 'flatpak'}
    assert w.recommended_indicators[('gparted', 'deb')].get_visible()
    assert 'falló Deluge' in message.call_args.args[2]
    assert w.recommended_retry.get_visible()
    w.recommended_buttons[('audacity', 'deb')].clicked()
    w.recommended_retry.clicked()
    settle()
    assert install.call_count == 3
    assert install.call_args.args[0]['id'] == 'deluge'
    assert w.recommended_selection == {'audacity': 'deb'}
    assert w.recommended_indicators[('deluge', 'flatpak')].get_visible()
    assert not w.recommended_retry.get_visible()
w.recommended_multi.set_active(False)

# El archivo conserva los formatos y requiere aplicar la revisión explícitamente.
seleccion_portable = {'deluge': 'flatpak', 'gparted': 'deb',
                      'google-chrome': 'deb-download', 'app-antigua': 'flatpak'}
codec = app.core_recommended_list
assert codec.importar(codec.exportar(seleccion_portable)) == seleccion_portable
for invalido in (b'{}', b'[' * (codec.LIMITE + 1), b'\xff',
                 codec.exportar({'../fuera': 'deb'})):
    try:
        codec.importar(invalido)
    except ValueError:
        pass
    else:
        raise AssertionError("Se aceptó una lista inválida")

# La exportación comprueba de nuevo el inventario incluso con selección vacía.
archivo_exportado = Mock()
inventario = {('deluge', 'flatpak'): True, ('gimp', 'deb'): True,
              ('google-chrome', 'deb-download'): True, ('vlc', 'deb'): False}
assert w.recommended_export.get_sensitive()
with patch.object(w, '_consultar_estado_recomendadas',
                  side_effect=lambda guardar: guardar(inventario, [])):
    w._exportar_lista_recomendada(archivo_exportado)
    assert codec.importar(archivo_exportado.replace_contents.call_args.args[0]) == {
        'deluge': 'flatpak', 'gimp': 'deb', 'google-chrome': 'deb-download'}
    w.recommended_selection = {'deluge': 'deb', 'gparted': 'deb'}
    w._exportar_lista_recomendada(archivo_exportado)
    assert codec.importar(archivo_exportado.replace_contents.call_args.args[0]) == {
        'deluge': 'deb', 'gparted': 'deb', 'gimp': 'deb', 'google-chrome': 'deb-download'}
    w.recommended_selection.clear()

estado_portable = {('deluge', 'flatpak'): True, ('gparted', 'deb'): False}
w._recomendadas_comprobadas(w.recommended_scan_generation, estado_portable, [])

def revisar_importacion(dialogo):
    scroll = next(widget for widget in dialogo.get_content_area().get_children()
                  if isinstance(widget, Gtk.ScrolledWindow))
    buffer = scroll.get_child().get_buffer()
    texto = buffer.get_text(*buffer.get_bounds(), False)
    assert 'Deluge · Flatpak · Ya instalada' in texto
    assert 'GParted · DEB (APT) · Pendiente de instalar' in texto
    assert 'Google Chrome · DEB (web oficial) · Descarga desde la web oficial' in texto
    assert texto.count('Formato no disponible') == 1
    assert not w.recommended_selection
    return Gtk.ResponseType.OK

def consultar_importacion(mostrar):
    generacion_importada = w.recommended_scan_generation
    # Recuperar el foco inicia otra consulta mientras se abre el diálogo.
    w.recommended_scan_generation += 1
    w._recomendadas_comprobadas(generacion_importada, estado_portable, [], mostrar)

with patch.object(w, '_consultar_estado_recomendadas', side_effect=consultar_importacion), \
     patch.object(Gtk.Dialog, 'run', revisar_importacion), \
     patch.object(w, '_ejecutar_instalacion_recomendada') as instalar:
    w._revisar_lista_importada(seleccion_portable)
    instalar.assert_not_called()
assert w.recommended_multi.get_active()
assert w.recommended_export.get_sensitive()
assert w.recommended_selection == {'deluge': 'flatpak', 'gparted': 'deb'}
assert [(a['id'], c['type']) for a, c in w._lote_recomendadas()] == [('gparted', 'deb')]
w.recommended_multi.set_active(False)

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
w._escribir('error registrado en modo simple', 'error')
settle()
assert not w.expansor_consola.get_visible() and not w.expansor_consola.get_expanded()
assert not w.log.get_mapped()
inicio, fin = w.buf.get_bounds()
assert 'error registrado en modo simple' in w.buf.get_text(inicio, fin, True)
w.destroy()

# El refresco precede al diagnóstico y un fallo no se presenta como lectura actual,
# y todo ocurre dentro de la ventana «Salud del sistema», sin otra ventana.
for refresh_error in (None, 'Autorización cancelada'):
    calls = []
    def refresh(command):
        calls.append('refresh')
        assert command == ['test-refresh']
        return refresh_error, (0, '', '')
    def diagnose(audit):
        assert audit == (0, '', '')
        calls.append('diagnose')
        return [{'name': 'Actualizaciones pendientes', 'status': 'ok',
                 'detail': '0 actualizaciones disponibles según los índices APT locales.', 'advice': ''}]
    def app_update(*args):
        calls.append('app')
        return {'status': 'current', 'detail': 'Al día'}
    from aio_core import constants as core_constants, updates as core_updates
    with patch.object(app.core_diagnostics, 'refresh_apt_indices', side_effect=refresh), \
         patch.object(app.core_diagnostics, 'run_diagnostics', side_effect=diagnose), \
         patch.object(core_updates, 'estado_actualizacion_app', side_effect=app_update), \
         patch.object(core_constants, 'formato_actualizacion', return_value='deb'), \
         patch.object(core_constants, 'version_app', return_value='2.7.7'), \
         patch.object(core_constants, 'helper_mantenimiento', return_value='helper'), \
         patch.object(core_constants, 'comando_pkexec', return_value=['test-refresh']), \
         patch.object(app, 'helper_mantenimiento', return_value='helper'), \
         patch.object(app, 'comando_pkexec', return_value=['test-refresh']), \
         patch.object(w.pagina_salud, '_ofrecer_solucion', return_value=False):
        w.pagina_salud.formato = 'deb'
        w._abrir_diagnostico()
        deadline = time.monotonic() + 8
        while (len(calls) < 3 or w.pagina_salud.loading) and time.monotonic() < deadline:
            settle()
            time.sleep(0.01)
        assert w.ventana_salud is not None and w.ventana_salud.get_visible()
        assert w.notebook.page_num(w.pagina_salud) == -1
        assert not w.pagina_salud.loading
        assert calls == ['refresh', 'diagnose', 'app'], calls
        results = w.pagina_salud.resultados
        pending = next(item for item in results if item['name'] == 'Actualizaciones pendientes')
        version = next(item for item in results if item['name'] == 'Versión de AiO Debian GUI')
        assert pending['status'] == ('unknown' if refresh_error else 'ok')
        assert version['status'] == ('unknown' if refresh_error else 'ok')
        assert w.pagina_salud.cards['Versión de AiO Debian GUI']['status_label'].get_text() == (
            'Sin comprobar' if refresh_error else 'Correcto')
        assert not [d for d in Gtk.Window.list_toplevels()
                    if isinstance(d, Gtk.Dialog) and d.get_visible()]
# El diagnóstico se ejecuta dentro de la ventana «Salud del sistema»: barra de
# progreso, semáforo por apartado y botón de solución, sin abrir otra ventana.
salud = w.pagina_salud
salud._on_diagnostics_done([
    {'name': 'Espacio en /', 'status': 'ok', 'detail': '100 GiB libres', 'advice': ''},
    {'name': 'Estado de dpkg', 'status': 'critical', 'detail': 'paquete incompleto',
     'advice': 'Revisa los paquetes incompletos.'},
    {'name': 'Índices de APT', 'status': 'warning', 'detail': 'hace 9 días', 'advice': ''},
], None)
settle()
salud._marcar_acciones([
    {'name': 'Estado de dpkg', 'status': 'critical', 'detail': '', 'advice': ''},
    {'name': 'Índices de APT', 'status': 'warning', 'detail': '', 'advice': ''},
])
salud._pintar_resultado({'name': 'Estado de dpkg', 'status': 'critical',
                         'detail': 'paquete incompleto', 'advice': 'Revisa.',
                         'action': 'command', 'command': ('pkexec', 'dpkg', '--configure', '-a'),
                         'command_label': 'Completar paquetes'})
salud._pintar_resultado({'name': 'Índices de APT', 'status': 'warning',
                         'detail': 'hace 9 días', 'advice': '', 'action': 'maintenance'})
settle()
assert salud.cards['Estado de dpkg']['status_label'].get_text() == 'No superado'
assert salud.cards['Espacio en /']['status_label'].get_text() == 'Correcto'
botones = [b.get_label() for b in salud.cards['Estado de dpkg']['actions'].get_children()]
assert botones == ['Completar paquetes'], botones
assert [b.get_label() for b in salud.cards['Índices de APT']['actions'].get_children()] == ['Abrir mantenimiento']
assert not salud.cards['Espacio en /']['actions'].get_visible()
assert salud.progress.get_fraction() == 1 / 3
assert 'Correctos: 1' in salud.status_label.get_text()
assert not [d for d in Gtk.Window.list_toplevels()
            if isinstance(d, Gtk.Dialog) and d.get_visible()]

# El botón de la tarjeta lanza la solución concreta y repite el diagnóstico.
lanzados = []
with patch.object(salud, '_ejecutar_comando', side_effect=lanzados.append):
    for boton in salud.cards['Estado de dpkg']['actions'].get_children():
        boton.clicked()
assert lanzados == [('pkexec', 'dpkg', '--configure', '-a')], lanzados


w.destroy()

# Un problema que bloquea el diagnóstico abre solo la ventana con su solución.
wsol = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
wsol.show_all()
settle()
salud = wsol.pagina_salud
_hd.HealthDashboard._ofrecer_solucion = _ofrecer_real
problema = salud._elegir_problema([
    {'name': 'Espacio en /', 'status': 'ok'},
    {'name': 'Actualizaciones pendientes', 'status': 'warning', 'action': 'maintenance'},
    {'name': 'Reinicio pendiente', 'status': 'warning', 'action': 'command', 'command': ('x',)},
])
assert problema['name'] == 'Actualizaciones pendientes'
assert salud._elegir_problema([{'name': 'Espacio en /', 'status': 'ok'}]) is None
salud._ofrecer_solucion([{'name': 'Actualizaciones pendientes', 'status': 'warning',
                          'detail': '12 actualizaciones', 'advice': '', 'action': 'maintenance'}])
settle()
dlg = salud.dialogo_solucion
assert dlg is not None and dlg.get_visible()
botones = [dlg.get_widget_for_response(r).get_label() for r in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.OK)]
assert botones == ['Ahora no', 'Ejecutar mantenimiento estándar'], botones
with patch.object(wsol, '_iniciar') as iniciar:
    dlg.response(Gtk.ResponseType.OK)
    settle()
    iniciar.assert_called_once()
assert salud.dialogo_solucion is None
wsol.destroy()
_hd.HealthDashboard._ofrecer_solucion = lambda self, results: False

# El botón de «Información del sistema» abre la ventana de salud, sin pestaña propia.
w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
w.show_all()
settle()
assert w.notebook.page_num(w.pagina_salud) == -1
assert w.ventana_salud is None
assert w.btn_salud_sistema.get_label() == app.traducir('Salud del sistema')
with patch.object(w.pagina_salud, 'refresh') as refrescar:
    w.btn_salud_sistema.clicked()
    settle()
    refrescar.assert_called_once()
assert w.ventana_salud.get_visible() and w.ventana_salud.get_transient_for() == w
assert w.pagina_salud.get_parent() == w.ventana_salud
w.ventana_salud.hide()
w.btn_salud_sistema.clicked()
settle()
assert w.ventana_salud.get_visible()
w.destroy()

# La guía ofrece una instalación gráfica con confirmación.
with patch.object(app, 'formato_actualizacion', return_value='flatpak'):
    w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
    w.show_all()
    settle()
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
    assert not any(isinstance(widget, Gtk.TextView) for widget in widgets)
    buttons = {widget.get_label(): widget for widget in widgets if isinstance(widget, Gtk.Button)}
    with patch.object(app.core_host_integration, 'install_host', create=True) as install, \
         patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.CANCEL):
        buttons['Instalar integración automáticamente'].clicked()
        install.assert_not_called()
        assert not w.programando
    with patch.object(app.core_host_integration, 'install_host', create=True) as install, \
         patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK):
        buttons['Instalar integración automáticamente'].clicked()
        deadline = time.monotonic() + 5
        while w.programando and time.monotonic() < deadline:
            settle()
        assert not w.programando
        install.assert_called_once_with('flatpak', os.environ.get('APPIMAGE'))
    with patch.object(app.core_host_integration, 'install_host', create=True,
                      side_effect=RuntimeError('autorización rechazada')), \
         patch.object(w, '_integracion_instalada', wraps=w._integracion_instalada) as finish, \
         patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK):
        w._abrir_guia_integracion()
        dialog = next(d for d in Gtk.Window.list_toplevels()
                      if isinstance(d, Gtk.Dialog) and d.get_title() == 'Guía de integración del anfitrión')
        w._instalar_integracion(None, dialog, None)
        deadline = time.monotonic() + 5
        while w.programando and time.monotonic() < deadline:
            settle()
        assert not w.programando
        assert finish.call_args.args == (None, 'autorización rechazada')
    w.destroy()

    # La terminal abre Bash sin ejecutar Fastfetch y conserva los accesos manuales.
    with tempfile.TemporaryDirectory() as directory:
        fastfetch = Path(directory) / 'fastfetch'
        fastfetch.write_text(
            '#!/bin/sh\n'
            'printf "run\\n" >> "' + directory + '/fastfetch-runs"\n'
            'if [ "$*" = "--pipe false" ]; then\n'
            '    printf "\\033[36mAIO_FASTFETCH_TEST\\033[0m\\n"\n'
            'else\n'
            '    printf "AIO_FASTFETCH_TEST\\n"\n'
            'fi\n'
        )
        fastfetch.chmod(0o755)
        btop = Path(directory) / 'btop'
        btop_marker = Path(directory) / 'btop-ran'
        btop.write_text(f'#!/bin/sh\n[ -t 0 ] && echo yes > "{btop_marker}"\nread -r salir\n')
        btop.chmod(0o755)
        htop = Path(directory) / 'htop'
        htop.write_bytes(btop.read_bytes())
        htop.chmod(0o755)
        analyze = Path(directory) / 'systemd-analyze'
        analyze.write_text('#!/bin/sh\n[ "$*" = "--no-pager time" ] && echo AIO_BOOT_TEST\n')
        analyze.chmod(0o755)
        nautilus = Path(directory) / 'nautilus'
        nautilus.write_text('#!/bin/sh\nprintf "%s" "$1" > "' + directory + '/nautilus-arg"\n')
        nautilus.chmod(0o755)
        with patch.dict(os.environ, {'PATH': directory + os.pathsep + os.environ['PATH']}):
            w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
            w.show_all()
            w._escribir('AIO_LOG_BEFORE_OPEN\n')
            with patch.object(w, '_terminal_iniciada', wraps=w._terminal_iniciada) as started:
                w.btn_ver_terminal.clicked()
                deadline = time.monotonic() + 8
                while not started.called and time.monotonic() < deadline:
                    settle()
                assert started.called and started.call_args.args[2] is None
            assert w.notebook.get_current_page() == w.notebook.page_num(w.pagina_terminal)

            def terminal_contains(text):
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    settle()
                    stream = app.Gio.MemoryOutputStream.new_resizable()
                    w.terminal.write_contents_sync(stream, app.Vte.WriteFlags.DEFAULT, None)
                    stream.close(None)
                    if text in stream.steal_as_bytes().get_data().decode('utf-8'):
                        return True
                return False

            def wait_button(name):
                deadline = time.monotonic() + 8
                while not w.terminal_buttons[name].get_sensitive() and time.monotonic() < deadline:
                    settle()
                assert w.terminal_buttons[name].get_sensitive()

            w.terminal.feed_child(b"printf '%s%s\\n' AIO_SHELL_ READY\n")
            assert terminal_contains('AIO_SHELL_READY')
            assert not (Path(directory) / 'fastfetch-runs').exists()
            assert terminal_contains('AIO_LOG_BEFORE_OPEN')
            w._escribir('AIO_LOG_LIVE\n', 'error')
            assert terminal_contains('AIO_LOG_LIVE')
            w._escribir('\x1b[2JAIO_LOG_SAFE\n')
            assert terminal_contains('AIO_LOG_BEFORE_OPEN')
            assert terminal_contains('AIO_LOG_SAFE')
            pty = w.terminal.get_pty()
            w.terminal.feed_child(b"AIO_DOCK_STATE=preserved\n")
            w.boton_separar_terminal.clicked()
            settle()
            detached = w.ventana_terminal
            assert detached.get_mapped()
            assert w.terminal.get_toplevel() == detached
            assert w.terminal.get_pty() == pty
            assert w.boton_mostrar_terminal.get_mapped()
            assert terminal_contains('AIO_LOG_SAFE')
            with patch.object(detached, 'present', wraps=detached.present) as present:
                w.notebook.set_current_page(0)
                w.btn_ver_terminal.clicked()
                present.assert_called_once_with()
                assert w.notebook.get_current_page() == 0
                w.notebook.set_current_page(w.notebook.page_num(w.pagina_terminal))
                w.boton_mostrar_terminal.clicked()
                assert present.call_count == 2
            w.terminal.feed_child(b'printf "%s%s\\n" AIO_DETACHED_ "$AIO_DOCK_STATE"\n')
            assert terminal_contains('AIO_DETACHED_preserved')
            assert list(w.terminal_buttons) == ['clear', 'fastfetch', 'nautilus', 'arranque', 'htop', 'btop']
            assert not w.btn_comandos_terminal.get_label()
            assert w.btn_comandos_terminal.get_image().get_icon_name()[0] == 'view-list-symbolic'
            assert w.btn_comandos_terminal.get_image().get_icon_name()[0] != w.btn_terminal_cabecera.get_image().get_icon_name()[0]
            assert w.btn_comandos_terminal.get_accessible().get_name() == 'Comandos'
            assert w.btn_comandos_terminal.get_tooltip_text() == 'Comandos'
            assert w.btn_comandos_terminal.get_toplevel() == detached
            command_menu = w.btn_comandos_terminal.get_popover()
            assert all(button.get_ancestor(Gtk.Popover) == command_menu
                       for button in (*w.terminal_buttons.values(), w.terminal_restart))
            assert w.boton_separar_terminal.get_parent() == w.btn_comandos_terminal.get_parent()
            assert all(not isinstance(button, Gtk.Button) or button.get_label() != 'Copiar'
                       for button in command_menu.get_child().get_children())
            w.btn_comandos_terminal.set_active(True)
            settle()
            assert command_menu.get_mapped()
            w.terminal_buttons['btop'].clicked()
            deadline = time.monotonic() + 8
            while not btop_marker.exists() and time.monotonic() < deadline:
                settle()
            assert btop_marker.read_text().strip() == 'yes'
            deadline = time.monotonic() + 2
            while command_menu.get_mapped() and time.monotonic() < deadline:
                settle()
            assert not command_menu.get_mapped()
            assert w.terminal.get_pty() == pty
            visor_btop = w.terminal_monitor
            pty_btop = visor_btop.get_pty()
            assert pty_btop is not None
            assert visor_btop.get_toplevel() == detached
            assert w.vistas_terminal.get_visible_child().get_child() == visor_btop
            w.boton_separar_terminal.clicked()
            settle()
            assert visor_btop.get_toplevel() == w
            assert w.vistas_terminal.get_visible_child().get_child() == visor_btop
            w.boton_separar_terminal.clicked()
            settle()
            detached = w.ventana_terminal
            assert visor_btop.get_toplevel() == detached
            for width, height in ((640, 420), (1020, 680)):
                detached.resize(width, height)
                settle()
                assert detached.get_size() == (width, height)
                assert 0 < visor_btop.get_allocated_width() < width
                assert 0 < visor_btop.get_allocated_height() < height
                assert visor_btop.get_pty() == pty_btop
            visor_btop.feed_child(b'q\n')
            deadline = time.monotonic() + 8
            while w.terminal_monitor is not None and time.monotonic() < deadline:
                settle()
            assert w.terminal_monitor is None
            assert w.vistas_terminal.get_visible_child_name() == 'bash'
            assert w.terminal.get_pty() == pty

            assert w.terminal_buttons['btop'].get_label() == 'Btop'
            assert w.terminal_buttons['htop'].get_label() == 'Htop'
            assert w.terminal_buttons['arranque'].get_label() == 'Análisis del arranque'
            btop_marker.unlink()
            w.terminal_buttons['htop'].clicked()
            deadline = time.monotonic() + 8
            while not btop_marker.exists() and time.monotonic() < deadline:
                settle()
            assert btop_marker.exists()
            assert w.vistas_terminal.get_visible_child_name() == 'htop'
            w.terminal_monitor.feed_child(b'q\n')
            deadline = time.monotonic() + 8
            while w.terminal_monitor is not None and time.monotonic() < deadline:
                settle()
            assert w.vistas_terminal.get_visible_child_name() == 'bash'
            w.terminal_buttons['arranque'].clicked()
            wait_button('arranque')
            assert terminal_contains('AIO_BOOT_TEST')

            btop.unlink()
            (Path(directory) / 'sh').symlink_to('/bin/sh')
            with patch.dict(os.environ, {'PATH': directory}), \
                 patch.object(Gtk.MessageDialog, 'run', return_value=Gtk.ResponseType.OK), \
                 patch.object(w, '_instalar_app_recomendada') as install:
                w.terminal_buttons['btop'].clicked()
                deadline = time.monotonic() + 8
                while not install.called and time.monotonic() < deadline:
                    settle()
                install.assert_called_once()
                application, channel, callback = install.call_args.args
                assert application['id'] == 'btop'
                assert channel['type'] == 'deb'
                assert callback == w._monitor_instalado
            w._monitor_instalado(application, channel, 'error simulado')
            assert 'No se pudo instalar btop.' in w.terminal_status.get_text()
            with patch.object(w, '_abrir_monitor') as open_btop:
                w._monitor_instalado(application, channel, None)
                open_btop.assert_called_once_with('btop')
            limpiar_rapido = w.btn_comandos_terminal.get_parent().get_children()[1]
            assert limpiar_rapido.get_image().get_icon_name()[0] == 'edit-clear-symbolic'
            assert limpiar_rapido.get_accessible().get_name() == 'Limpiar'
            limpiar_rapido.clicked()
            wait_button('clear')
            assert not w.terminal_status.get_text()
            stream = app.Gio.MemoryOutputStream.new_resizable()
            w.terminal.write_contents_sync(stream, app.Vte.WriteFlags.DEFAULT, None)
            stream.close(None)
            assert b'AIO_FASTFETCH_TEST' not in stream.steal_as_bytes().get_data()
            w.terminal.feed_child(b"printf '%s%s\\n' AIO_PENDING_")
            w._escribir('AIO_LOG_DURING_INPUT\n')
            assert terminal_contains('AIO_LOG_DURING_INPUT')
            with patch.object(w.terminal, 'feed', wraps=w.terminal.feed) as feed:
                w.terminal_buttons['fastfetch'].clicked()
                wait_button('fastfetch')
                assert any(b'\x1b[36mAIO_FASTFETCH_TEST\x1b[0m' in llamada.args[0]
                           for llamada in feed.call_args_list)
            assert terminal_contains('AIO_FASTFETCH_TEST')
            assert (Path(directory) / 'fastfetch-runs').read_text() == 'run\n'
            w.terminal.feed_child(b'INPUT_OK\n')
            assert terminal_contains('AIO_PENDING_INPUT_OK')
            w.terminal_buttons['nautilus'].clicked()
            wait_button('nautilus')
            deadline = time.monotonic() + 8
            while not (Path(directory) / 'nautilus-arg').exists() and time.monotonic() < deadline:
                settle()
            assert (Path(directory) / 'nautilus-arg').read_text() == 'admin:/'
            with patch.dict(os.environ, {'PATH': '/nonexistent'}):
                w.terminal_buttons['fastfetch'].clicked()
                wait_button('fastfetch')
                assert 'No se pudo ejecutar fastfetch.' in w.terminal_status.get_text()
            process = Mock(returncode=0)
            process.communicate.return_value = (None, b'')
            with patch.object(app, 'es_flatpak', return_value=True), \
                 patch.object(app.subprocess, 'Popen', return_value=process) as popen:
                w.terminal_buttons['nautilus'].clicked()
                wait_button('nautilus')
                popen.assert_called_once_with(
                    ['flatpak-spawn', '--host', 'env', 'TERM=xterm-256color', 'nautilus', 'admin:/'],
                    stdout=app.subprocess.DEVNULL, stderr=app.subprocess.PIPE,
                )
            w.terminal.feed_child(b"printf '%s%s\\n' AIO_TERMINAL_ COMMAND_OK\n")
            assert terminal_contains('AIO_TERMINAL_COMMAND_OK')
            detached.close()
            settle()
            assert w.ventana_terminal is None
            assert not detached.get_visible()
            assert w.terminal.get_toplevel() == w
            assert w.terminal.get_pty() == pty
            assert terminal_contains('AIO_TERMINAL_COMMAND_OK')
            w.boton_separar_terminal.clicked()
            w.boton_separar_terminal.clicked()
            settle()
            assert w.ventana_terminal is None
            w.terminal.feed_child(b'printf "%s%s\\n" AIO_REATTACHED_ "$AIO_DOCK_STATE"\n')
            assert terminal_contains('AIO_REATTACHED_preserved')
            w.terminal.feed_child(b'exit\n')
            deadline = time.monotonic() + 8
            while w.terminal_started and time.monotonic() < deadline:
                settle()
            assert not w.terminal_started
            assert w.terminal_restart.get_visible()
            w._escribir('AIO_LOG_SESSION_ENDED\n')
            assert terminal_contains('AIO_LOG_SESSION_ENDED')
            with patch.object(w, '_terminal_iniciada', wraps=w._terminal_iniciada) as started:
                w.terminal_restart.clicked()
                deadline = time.monotonic() + 8
                while not started.called and time.monotonic() < deadline:
                    settle()
                assert started.called and w.terminal_started
                assert started.call_args.args[2] is None
            w.terminal.feed_child(b"printf '%s%s\\n' AIO_RESTART_ READY\n")
            assert terminal_contains('AIO_RESTART_READY')
            assert (Path(directory) / 'fastfetch-runs').read_text() == 'run\n'
            w.terminal.feed_child(b'exit\n')
            deadline = time.monotonic() + 8
            while w.terminal_started and time.monotonic() < deadline:
                settle()
            assert not w.terminal_started
            w.destroy()

with patch.dict(os.environ, {'PATH': '/nonexistent'}):
    w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
    w.show_all()
    with patch.object(w, '_terminal_iniciada', wraps=w._terminal_iniciada) as started:
        # La Terminal no tiene pestaña propia: el botón del encabezado la crea.
        assert w.notebook.page_num(w.pagina_terminal) == -1
        w.btn_terminal_cabecera.clicked()
        assert w.notebook.get_current_page() == w.notebook.page_num(w.pagina_terminal)
        assert w.notebook.get_tab_label_text(w.pagina_terminal) == app.traducir('Terminal')
        deadline = time.monotonic() + 8
        while not started.called and time.monotonic() < deadline:
            settle()
        assert started.called and started.call_args.args[2] is None
    w.terminal.feed_child(b"printf '%s%s\\n' AIO_MISSING_ FASTFETCH_OK\n")
    assert terminal_contains('AIO_MISSING_FASTFETCH_OK')
    w.terminal.feed_child(b'exit\n')
    deadline = time.monotonic() + 8
    while w.terminal_started and time.monotonic() < deadline:
            settle()
    assert not w.terminal_started
    w.destroy()

# La edición Flatpak abre la sesión en el anfitrión sin elevar privilegios.
fake_window = Mock()
fake_window.terminal_started = False
with patch.object(app, 'es_flatpak', return_value=True):
    app.VentanaPrincipal._iniciar_terminal(fake_window)
argv = fake_window.terminal.spawn_async.call_args.args[2]
assert argv == ['flatpak-spawn', '--host', 'script', '-qefc', '/bin/bash -i', '/dev/null']
error = Mock(message='spawn failed')
app.VentanaPrincipal._terminal_iniciada(fake_window, None, -1, error, None)
assert not fake_window.terminal_started
assert 'spawn failed' in fake_window.terminal_status.set_text.call_args.args[0]
fake_window.terminal_restart.show.assert_called()

print('GTK: selección, confirmación, exclusión Stable, diagnóstico, consola, resultados y adaptación en cuatro idiomas OK')
