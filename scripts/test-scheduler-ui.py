#!/usr/bin/env python3
"""Configura la interfaz con un backend simulado, sin permisos ni timers reales."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

if not Gtk.init_check([])[0]:
    print('Sin pantalla: prueba GTK de programación omitida.')
    sys.exit(0)
loader = importlib.machinery.SourceFileLoader('scheduler_ui', 'package/usr/bin/aio-debian-gui')
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)

def wait_for(predicate):
    limit = time.monotonic() + 5
    while not predicate() and time.monotonic() < limit:
        while Gtk.events_pending(): Gtk.main_iteration()
        time.sleep(.005)
    assert predicate(), 'GTK timeout'

for language in ('es', 'en', 'fr', 'zh'):
    w = app.VentanaPrincipal({'idioma': language, 'tema': 'claro', 'modo_simple': False})
    w.show_all()
    backend = {'version': app.core_scheduler.VERSION, 'available': True, 'config': None,
               'last_result': None, 'timer_active': False, 'next_run': ''}
    commands = []
    def read_status(command, **kwargs):
        assert command[-1] == '--schedule-status'
        return SimpleNamespace(returncode=0, stdout=json.dumps(backend), stderr='')
    class Save:
        def __init__(self, command, **kwargs):
            commands.append(command)
            assert command[0] == 'pkexec' and command[1] == app.HELPER_SISTEMA
            if '--schedule-save' in command:
                config = json.loads(command[-1])
                app.core_scheduler.validate_config(config)
                backend['config'] = config
                backend['timer_active'] = config['enabled']
            else:
                assert command[-1] == '--schedule-remove'
                backend['config'] = None
                backend['timer_active'] = False
            read, write = os.pipe()
            os.write(write, b'Polkit notice\n##SCHEDULE:authorized\n')
            os.close(write)
            self.stdout = os.fdopen(read, 'rb', buffering=0)
            self.returncode = None
        def __enter__(self): return self
        def __exit__(self, *args): self.stdout.close()
        def poll(self): return self.returncode
        def communicate(self):
            self.returncode = 0
            return b'', None
    with patch.object(app.subprocess, 'run', side_effect=read_status), \
         patch.object(app.subprocess, 'Popen', side_effect=Save):
        w._abrir_programacion()
        dialog = w.ventana_programacion
        wait_for(lambda: w.programacion_widgets['guardar'].get_sensitive())
        widgets = w.programacion_widgets
        assert dialog.get_size()[0] <= 700 and dialog.get_size()[1] <= 720, (language, dialog.get_size())
        assert widgets['config'] is None
        assert not widgets['activo'].get_active()
        assert set(widgets['tareas']) == set(app.core_scheduler.TASKS)
        assert 'backports-kernel-mesa' not in widgets['tareas']
        with patch.object(app, 'formato_actualizacion', return_value='deb'):
            assert w._lanzador_programacion() == {'format': 'deb', 'path': ''}
        with patch.object(app, 'formato_actualizacion', return_value='appimage'), \
             patch.dict(app.os.environ, {'APPIMAGE': '/home/test/AiO.AppImage'}):
            assert w._lanzador_programacion() == {
                'format': 'appimage', 'path': '/home/test/AiO.AppImage'}
        widgets['frecuencia'].set_active_id('daily')
        assert not widgets['dia'].get_sensitive()
        widgets['frecuencia'].set_active_id('weekly')
        assert widgets['dia'].get_sensitive()
        widgets['dia'].set_active_id('2')
        widgets['hora'].set_value(3)
        widgets['minuto'].set_value(25)
        widgets['activo'].set_active(True)
        for task, check in widgets['tareas'].items(): check.set_active(task in ('upgrade', 'autoclean'))
        w._cambiar_programacion(dialog)
        assert w.programando and not w.btn_iniciar.get_sensitive()
        wait_for(lambda: not w.programando and widgets['guardar'].get_sensitive())
        assert backend['config'] == {'enabled':True,'frequency':'weekly','weekday':2,'hour':3,'minute':25,'tasks':['upgrade','autoclean'],'launcher':None}
        assert widgets['pausar'].get_sensitive()
        w._cambiar_programacion(dialog, pausar=True)
        wait_for(lambda: not w.programando and widgets['guardar'].get_sensitive())
        assert not backend['config']['enabled'] and not widgets['activo'].get_active()
        assert not widgets['pausar'].get_sensitive()
        before = len(commands)
        for check in widgets['tareas'].values(): check.set_active(False)
        with patch.object(w, '_mensaje') as message:
            w._cambiar_programacion(dialog)
            assert message.called and len(commands) == before
        # Actualizar los resultados no debe borrar un formulario aún no guardado.
        widgets['hora'].set_value(5)
        backend['last_result'] = {'status':'blocked','started':'2026-11-15T01:00:00+00:00',
            'detail':'APT/dpkg ocupado o no se pudo comprobar su bloqueo.', 'tasks':{'upgrade':'not-run'}}
        w._cargar_programacion(dialog, cargar_formulario=False)
        wait_for(lambda: widgets['actualizar'].get_sensitive())
        assert widgets['hora'].get_value_as_int() == 5
        assert app.traducir('Bloqueado') in widgets['resultados'].get_text()
        w._cambiar_programacion(dialog, eliminar=True)
        wait_for(lambda: not w.programando and widgets['guardar'].get_sensitive())
        assert backend['config'] is None and not widgets['eliminar'].get_sensitive()
        dialog.destroy()
        assert w.ventana_programacion is None
        # Una integración ausente o desactualizada no habilita escrituras.
        backend['available'] = False
        w._abrir_programacion()
        wait_for(lambda: w.programacion_widgets['actualizar'].get_sensitive())
        assert not w.programacion_widgets['guardar'].get_sensitive()
        assert not w.programacion_widgets['formulario'].get_sensitive()
        w.ventana_programacion.destroy()
    w.destroy()

# La guía es accesible desde la programación si la integración del anfitrión falla.
with patch.object(app, 'formato_actualizacion', return_value='flatpak'):
    w = app.VentanaPrincipal({'idioma': 'es', 'tema': 'claro', 'modo_simple': False})
    w.show_all()
    with patch.object(app.subprocess, 'run', return_value=SimpleNamespace(
            returncode=1, stdout='', stderr='asistente ausente')):
        w._abrir_programacion()
        wait_for(lambda: w.programacion_widgets['actualizar'].get_sensitive())
        button = w.programacion_widgets['integracion']
        assert button.get_visible() and button.get_sensitive()
        with patch.object(w, '_abrir_guia_integracion') as guide:
            button.clicked()
            guide.assert_called_once_with(parent=w.ventana_programacion)
        w.ventana_programacion.destroy()
    w.destroy()
print('GTK programación: carga, selección, hora, guardar, pausar, eliminar, validación, resultados e integración ausente en cuatro idiomas OK')
