"""Interfaz GTK de programación de mantenimiento."""

import datetime
import json
import os
import subprocess
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from aio_core import scheduler as core_scheduler


class ControladorProgramacion:
    def __init__(self, ventana):
        self.ventana = ventana
        self.ventana_programacion = None

    def abrir(self):
        contexto = self.ventana._contexto_programacion()
        traducir, etiqueta = contexto["traducir"], contexto["etiqueta"]
        PASOS, formato_actualizacion = contexto["pasos"], contexto["formato"]
        if self.ventana.en_curso or self.ventana.programando or self.ventana.comprobando_actualizacion:
            return
        self.ventana.menu_popover.popdown()
        if self.ventana_programacion is not None:
            self.ventana_programacion.present()
            return
        dialogo = Gtk.Dialog(title=traducir("Programar mantenimiento"), transient_for=self.ventana, modal=True)
        dialogo.set_default_size(620, 660)
        dialogo.add_button(traducir("Cerrar"), Gtk.ResponseType.CLOSE)
        dialogo.connect("response", lambda d, _r: d.destroy() if not self.ventana.programando else None)
        dialogo.connect("delete-event", lambda *_a: self.ventana.programando)
        dialogo.connect("destroy", self._programacion_cerrada)
        self.ventana_programacion = dialogo
        area = dialogo.get_content_area()
        area.set_border_width(14)
        area.set_spacing(10)
        aviso = etiqueta("El mantenimiento se ejecutará con la aplicación cerrada. Guardar la programación requiere autorización de administrador.")
        aviso.set_max_width_chars(65)
        area.pack_start(aviso, False, False, 0)
        estado = etiqueta("Cargando programación…")
        area.pack_start(estado, False, False, 0)
        formulario = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scroll_formulario = Gtk.ScrolledWindow()
        scroll_formulario.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_formulario.set_min_content_height(140)
        scroll_formulario.add(formulario)
        area.pack_start(scroll_formulario, True, True, 0)
        activo = Gtk.CheckButton(label=traducir("Activar mantenimiento automático"))
        formulario.pack_start(activo, False, False, 0)
        horario = Gtk.Grid(column_spacing=12, row_spacing=8)
        frecuencia = Gtk.ComboBoxText()
        for key, title in (("daily", "Cada día"), ("weekly", "Cada semana"), ("monthly", "Cada mes (día 1)")):
            frecuencia.append(key, traducir(title))
        dia = Gtk.ComboBoxText()
        for key, title in enumerate(("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")):
            dia.append(str(key), traducir(title))
        hora = Gtk.SpinButton.new_with_range(0, 23, 1)
        minuto = Gtk.SpinButton.new_with_range(0, 59, 1)
        for spin in (hora, minuto):
            spin.set_numeric(True)
            spin.connect("output", self._hora_programacion)
        horas = Gtk.Box(spacing=4)
        horas.pack_start(hora, False, False, 0)
        horas.pack_start(Gtk.Label(label=":"), False, False, 0)
        horas.pack_start(minuto, False, False, 0)
        horario.attach(etiqueta("Frecuencia"), 0, 0, 1, 1)
        horario.attach(frecuencia, 1, 0, 1, 1)
        horario.attach(etiqueta("Día de la semana"), 0, 1, 1, 1)
        horario.attach(dia, 1, 1, 1, 1)
        horario.attach(etiqueta("Hora local"), 0, 2, 1, 1)
        horario.attach(horas, 1, 2, 1, 1)
        frecuencia.connect("changed", lambda c: dia.set_sensitive(c.get_active_id() == "weekly"))
        formulario.pack_start(horario, False, False, 0)
        formulario.pack_start(etiqueta("Tareas del mantenimiento automático"), False, False, 0)
        tareas = {}
        nombres = {p[0]: p[1] for p in PASOS}
        for tarea in core_scheduler.TASKS:
            check = Gtk.CheckButton(label=traducir(nombres[tarea]))
            formulario.pack_start(check, False, False, 0)
            tareas[tarea] = check
            if tarea == "snap-update" and not getattr(self.ventana, "snapd_presente", False):
                check.set_no_show_all(True)
                check.hide()
        detalle = etiqueta("Si el equipo estaba apagado, se recupera la ejecución pendiente al encender. No se reinicia automáticamente. Eliminaciones de paquetes, kernel, controladores y repositorios se gestionan manualmente.", dim=True)
        detalle.set_max_width_chars(65)
        formulario.pack_start(detalle, False, False, 0)
        resultados = etiqueta("")
        resultados.set_selectable(True)
        resultados.set_max_width_chars(65)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(90)
        scroll.add(resultados)
        area.pack_start(scroll, True, True, 0)
        acciones = Gtk.Grid(column_spacing=8, row_spacing=6, column_homogeneous=True)
        guardar = Gtk.Button(label=traducir("Guardar programación"))
        guardar.get_style_context().add_class("suggested-action")
        pausar = Gtk.Button(label=traducir("Pausar"))
        eliminar = Gtk.Button(label=traducir("Eliminar programación"))
        actualizar = Gtk.Button(label=traducir("Actualizar estado"))
        for i, boton in enumerate((guardar, pausar, eliminar, actualizar)):
            boton.get_child().set_line_wrap(True)
            boton.get_child().set_max_width_chars(24)
            acciones.attach(boton, i % 2, i // 2, 1, 1)
        area.pack_start(acciones, False, False, 0)
        integracion = Gtk.Button(label=traducir("Guía de integración del anfitrión"))
        integracion.connect("clicked", lambda _b: self.ventana._abrir_guia_integracion(parent=dialogo))
        area.pack_start(integracion, False, False, 0)
        self.programacion_widgets = dict(activo=activo, frecuencia=frecuencia, dia=dia,
            hora=hora, minuto=minuto, tareas=tareas, estado=estado, resultados=resultados,
            formulario=formulario, guardar=guardar, pausar=pausar, eliminar=eliminar,
            actualizar=actualizar, integracion=integracion, disponible=False, config=None)
        guardar.connect("clicked", lambda _b: self._cambiar_programacion(dialogo))
        pausar.connect("clicked", lambda _b: self._cambiar_programacion(dialogo, pausar=True))
        eliminar.connect("clicked", lambda _b: self._cambiar_programacion(dialogo, eliminar=True))
        actualizar.connect("clicked", lambda _b: self._cargar_programacion(dialogo, cargar_formulario=False))
        dialogo.show_all()
        integracion.set_visible(formato_actualizacion() in ("flatpak", "appimage"))
        self._cargar_programacion(dialogo)

    @staticmethod
    def _hora_programacion(spin):
        spin.set_text("%02d" % spin.get_value_as_int())
        return True

    def _programacion_cerrada(self, dialogo):
        if self.ventana_programacion is dialogo:
            self.ventana_programacion = None

    def _cargar_programacion(self, dialogo, cargar_formulario=True):
        contexto = self.ventana._contexto_programacion()
        comando_host, HELPER_SISTEMA = contexto["comando_host"], contexto["helper"]
        if self.ventana.programando:
            return
        w = self.programacion_widgets
        for nombre in ("guardar", "pausar", "eliminar", "actualizar"):
            w[nombre].set_sensitive(False)
        def consultar():
            try:
                proc = subprocess.run(comando_host(HELPER_SISTEMA, "--schedule-status"),
                    capture_output=True, text=True, timeout=20)
                if proc.returncode:
                    raise RuntimeError((proc.stderr or proc.stdout)[-500:])
                datos = json.loads(proc.stdout)
                if not isinstance(datos, dict):
                    raise ValueError("invalid report")
                if datos.get('config') is not None:
                    core_scheduler.validate_config(datos['config'])
                error = None
            except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
                datos, error = {}, str(exc)
            GLib.idle_add(self._programacion_cargada, dialogo, datos, error, cargar_formulario)
        threading.Thread(target=consultar, daemon=True).start()

    def _programacion_cargada(self, dialogo, datos, error, cargar_formulario=True):
        contexto = self.ventana._contexto_programacion()
        traducir, PASOS = contexto["traducir"], contexto["pasos"]
        if self.ventana_programacion is not dialogo or self.ventana.programando:
            return GLib.SOURCE_REMOVE
        w = self.programacion_widgets
        disponible = not error and datos.get("available", False) and core_scheduler.compatible_host(datos)
        w['disponible'] = disponible
        w['config'] = datos.get('config')
        config = datos.get('config') or core_scheduler.DEFAULT
        if cargar_formulario:
            w['activo'].set_active(config['enabled'])
            w['frecuencia'].set_active_id(config['frequency'])
            w['dia'].set_active_id(str(config['weekday']))
            w['hora'].set_value(config['hour'])
            w['minuto'].set_value(config['minute'])
            for tarea, check in w['tareas'].items():
                check.set_active(tarea in config['tasks'])
        for nombre in ('formulario', 'guardar'):
            w[nombre].set_sensitive(bool(disponible))
        w['pausar'].set_sensitive(bool(disponible and datos.get('config') and config['enabled']))
        w['eliminar'].set_sensitive(bool(disponible and datos.get('config')))
        w['actualizar'].set_sensitive(True)
        w['integracion'].set_sensitive(not disponible)
        if not disponible:
            texto = traducir("Instala o actualiza la integración de AiO en el anfitrión y utiliza systemd para habilitar la programación. Consulta el README.")
        elif datos.get('timer_active'):
            texto = traducir("Programación activa") + " · " + traducir("Próxima ejecución: %s") % (datos.get('next_run') or traducir("No disponible"))
        else:
            estado = ("Programación pausada" if not config['enabled'] else "Programación no activa") if datos.get('config') else "Sin programación"
            texto = traducir(estado)
        w['estado'].set_text(texto)
        ultimo = datos.get('last_result')
        if ultimo:
            estados = {'success': 'Completada', 'error': 'Error', 'blocked': 'Bloqueado',
                       'skipped': 'Omitido', 'running': 'En curso', 'interrupted': 'Interrumpido', 'not-run': 'No ejecutada'}
            try:
                fecha = datetime.datetime.fromisoformat(ultimo['started']).astimezone().strftime('%Y-%m-%d %H:%M')
            except (ValueError, KeyError):
                fecha = traducir('No disponible')
            texto = traducir('Última ejecución: %s · %s') % (fecha, traducir(estados.get(ultimo['status'], 'No comprobado')))
            if ultimo.get('detail'):
                texto += "\n" + traducir(ultimo['detail'])
            if ultimo.get('reboot_required'):
                texto += "\n" + traducir("Se recomienda reiniciar para aplicar los cambios críticos.")
            nombres = {p[0]: traducir(p[1]) for p in PASOS}
            for tarea, estado in ultimo.get('tasks', {}).items():
                texto += "\n• " + nombres.get(tarea, tarea) + ": " + traducir(estados.get(estado, 'No comprobado'))
            w['resultados'].set_text(texto)
        else:
            w['resultados'].set_text(traducir('Todavía no hay ejecuciones programadas.'))
        return GLib.SOURCE_REMOVE

    def _cambiar_programacion(self, dialogo, eliminar=False, pausar=False):
        contexto = self.ventana._contexto_programacion()
        traducir = contexto["traducir"]
        comando_pkexec, HELPER_SISTEMA = contexto["comando_pkexec"], contexto["helper"]
        if self.ventana.programando or not self.programacion_widgets['disponible']:
            return
        w = self.programacion_widgets
        try:
            if eliminar:
                argumentos = ['--schedule-remove']
            else:
                config = ({**w['config'], 'enabled': False} if pausar else {
                    'enabled': w['activo'].get_active(), 'frequency': w['frecuencia'].get_active_id(),
                    'weekday': int(w['dia'].get_active_id()), 'hour': w['hora'].get_value_as_int(),
                    'minute': w['minuto'].get_value_as_int(),
                    'tasks': [t for t, c in w['tareas'].items() if c.get_active()]})
                if not pausar:
                    config['launcher'] = self._lanzador_programacion()
                config = core_scheduler.validate_config(config)
                argumentos = ['--schedule-save', json.dumps(config)]
        except (ValueError, TypeError):
            self.ventana._mensaje(Gtk.MessageType.ERROR, "Programar mantenimiento", "Selecciona al menos una tarea programable, sin duplicados.")
            return
        self.ventana.programando = True
        self.ventana._actualizar_sensibilidad()
        for nombre in ('formulario', 'guardar', 'pausar', 'eliminar', 'actualizar', 'integracion'):
            w[nombre].set_sensitive(False)
        dialogo.set_response_sensitive(Gtk.ResponseType.CLOSE, False)
        w['estado'].set_text(traducir('Esperando autorización de administrador…'))
        def aplicar():
            import select
            import time
            try:
                comando = comando_pkexec(HELPER_SISTEMA, 'C.UTF-8', *argumentos)
                with subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0) as proc:
                    salida = b''
                    limite = time.monotonic() + 90
                    while proc.poll() is None:
                        restante = limite - time.monotonic()
                        if restante <= 0 or not select.select([proc.stdout], [], [], max(0, restante))[0]:
                            proc.kill()
                            proc.wait()
                            raise RuntimeError(traducir('Espera de autorización agotada.'))
                        bloque = os.read(proc.stdout.fileno(), 4096)
                        salida += bloque
                        if b'##SCHEDULE:authorized\n' in salida:
                            break
                        if not bloque:
                            break
                    resto, _ = proc.communicate()
                    salida += resto
                    if proc.returncode:
                        detalle = "\n".join(traducir(linea) for linea in salida.decode('utf-8', errors='replace').splitlines() if not linea.startswith('##'))
                        raise RuntimeError(detalle[-1500:] or traducir('No se obtuvo autorización de administrador.'))
                error = None
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                error = str(exc)
            GLib.idle_add(self._programacion_guardada, dialogo, error)
        threading.Thread(target=aplicar, daemon=True).start()

    def _lanzador_programacion(self):
        formato = self.ventana._contexto_programacion()["formato"]()
        if formato in ("deb", "flatpak"):
            return {"format": formato, "path": ""}
        appimage = os.environ.get("APPIMAGE")
        if formato == "appimage" and appimage and os.path.isabs(appimage):
            return {"format": formato, "path": appimage}
        return None

    def _programacion_guardada(self, dialogo, error):
        traducir = self.ventana._contexto_programacion()["traducir"]
        self.ventana.programando = False
        self.ventana._actualizar_sensibilidad()
        if self.ventana_programacion is not dialogo:
            return GLib.SOURCE_REMOVE
        dialogo.set_response_sensitive(Gtk.ResponseType.CLOSE, True)
        if error:
            mensaje = Gtk.MessageDialog(transient_for=dialogo, modal=True,
                message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                text=traducir('No se pudo guardar la programación.'))
            mensaje.format_secondary_text(error)
            mensaje.run()
            mensaje.destroy()
        self._cargar_programacion(dialogo)
        return GLib.SOURCE_REMOVE

