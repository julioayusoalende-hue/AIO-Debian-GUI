"""Maintenance page - Configuración y mantenimiento."""

import threading
import subprocess
import os
import json
import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, Pango

from aio_core import diagnostics as core_diagnostics
from aio_core import preflight as core_preflight
from aio_core import scheduler as core_scheduler
from aio_core.firmware import FirmwareSection

from aio_core import (
    traducir, traducir_detalle_diagnostico, PASOS, GRUPOS, ESTILO_APLICACION,
    cabecera_mantenimiento, tarjeta_mantenimiento, etiqueta, HELPER_SISTEMA,
    comando_host, comando_pkexec, helper_disponible, helper_admite_tarea,
    autorizacion_sin_contrasena_activa, helper_admite_autorizacion_sin_contrasena,
    version_app, formato_actualizacion, datos_distribucion_anfitrion,
    distribucion_anfitrion, identidad_distribucion,
)

from .widgets.card import Card
from .widgets.task_list import TaskList
from .widgets.queue_widget import QueueWidget


class MaintenancePage(Gtk.Box):
    """Pestaña Configuración y mantenimiento."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.window = window
        self.translate = traducir

        # Estado
        self.tasks_data = {}
        self.task_states = {}
        self.selected_tasks = set()
        self.running = False
        self.process = None
        self.output_buffer = []
        self.firmware_section_expanded = False

        # UI
        self._build_ui()
        self._load_task_states()

    def _build_ui(self):
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_overlay_scrolling(False)
        self.pack_start(scroller, True, True, 0)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_border_width(4)
        scroller.add(main_box)

        # --- Sección: Tareas de mantenimiento ---
        self.tasks_frame, self.tasks_box = Card("Tareas de mantenimiento", "preferences-system-symbolic")
        main_box.pack_start(self.tasks_frame, False, False, 0)

        self.task_list = TaskList(PASOS, GRUPOS, self.translate)
        self.task_list.connect("selection-changed", self._on_task_selection_changed)
        self.tasks_box.pack_start(self.task_list, True, True, 0)

        self.btn_run = Gtk.Button(label=self.translate("Ejecutar mantenimiento (0)"))
        self.btn_run.get_style_context().add_class("suggested-action")
        self.btn_run.connect("clicked", self._on_run_maintenance)
        self.tasks_box.pack_start(self.btn_run, False, False, 0)

        # --- Sección: Firmware ---
        self.firmware_frame, self.firmware_box = Card("Actualizaciones de firmware", "drive-removable-media-symbolic")
        main_box.pack_start(self.firmware_frame, False, False, 0)

        self.firmware_section = FirmwareSection(self.window, self.translate)
        self.firmware_box.pack_start(self.firmware_section, True, True, 0)

        # --- Sección: Diagnóstico ---
        diag_frame, diag_box = Card("Diagnóstico preventivo", "dialog-information-symbolic")
        main_box.pack_start(diag_frame, False, False, 0)

        self.btn_diagnostics = Gtk.Button(label=self.translate("Ejecutar diagnóstico"))
        self.btn_diagnostics.connect("clicked", self._run_diagnostics)
        diag_box.pack_start(self.btn_diagnostics, False, False, 0)

        self.diagnostics_status = Gtk.Label(xalign=0)
        self.diagnostics_status.set_text(self.translate("No comprobado"))
        diag_box.pack_start(self.diagnostics_status, False, False, 0)

        # --- Consola de salida ---
        console_frame, console_box = Card("Salida de la consola", "utilities-terminal-symbolic")
        main_box.pack_start(console_frame, True, True, 0)

        self.console = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                     wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=8, right_margin=8)
        self.console.set_top_margin(6)
        self.console.set_bottom_margin(6)
        console_scroll = Gtk.ScrolledWindow()
        console_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        console_scroll.add(self.console)
        console_box.pack_start(console_scroll, True, True, 0)

        # Status bar
        self.status_label = Gtk.Label(xalign=0, ellipsize=3)
        self.pack_end(self.status_label, False, False, 0)

    def _load_task_states(self):
        def worker():
            estados = {}
            distro = self.window.distribucion

            for task_id, _, _, _, grupo in PASOS:
                disponible = True
                if task_id == "backports-kernel-mesa" and distro != "debian":
                    disponible = False
                elif task_id == "revertir-backports" and distro != "debian":
                    disponible = False
                elif task_id == "nvidia-driver" and distro != "debian":
                    disponible = False
                elif task_id == "ubuntu-hwe" and distro != "ubuntu":
                    disponible = False
                elif task_id == "flatpak-setup" and self.window.flatpak_presente:
                    disponible = False
                elif task_id == "snap-update" and not self.window.snapd_presente:
                    disponible = False
                elif task_id == "flatpak-update" and not self.window.flatpak_presente:
                    disponible = False
                elif task_id == "gnome-plugin" and not self.window.gnome_presente:
                    disponible = False
                elif task_id == "ext-manager" and not self.window.gnome_presente:
                    disponible = False

                if disponible:
                    helper = helper_disponible(HELPER_SISTEMA)
                    if helper and not helper_admite_tarea(HELPER_SISTEMA, task_id):
                        disponible = False

                estados[task_id] = disponible

            GLib.idle_add(self._on_task_states_loaded, estados)

        threading.Thread(target=worker, daemon=True).start()

    def _on_task_states_loaded(self, estados):
        self.task_states = estados
        self.task_list.set_task_states(estados)
        self._update_run_button()

    def query_task_states(self, initial=False):
        self._load_task_states()

    def _on_task_selection_changed(self, task_list, selected):
        self.selected_tasks = selected
        self._update_run_button()

    def _update_run_button(self):
        count = len(self.selected_tasks)
        self.btn_run.set_label(self.translate("Ejecutar mantenimiento (%d)") % count)
        self.btn_run.set_sensitive(count > 0 and not self.running)

    def _on_run_maintenance(self, _btn):
        if self.running or not self.selected_tasks:
            return

        checks = core_preflight.run_all(comando_host)
        if not checks["ok"]:
            self._show_preflight_dialog(checks)
            return

        tasks_desc = []
        for task_id in self.selected_tasks:
            for tid, titulo, _, _, _ in PASOS:
                if tid == task_id:
                    tasks_desc.append(titulo)
                    break
        msg = self.translate("¿Ejecutar las siguientes tareas?\n\n") + "\n".join(f"• {t}" for t in tasks_desc)

        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL, text=msg)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        if dialog.run() != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        dialog.destroy()

        self._execute_maintenance()

    def _execute_maintenance(self):
        self.running = True
        self.task_list.set_sensitive(False)
        self.btn_run.set_sensitive(False)
        self.status_label.set_text(self.translate("Ejecutando mantenimiento…"))
        self._clear_console()

        tasks = list(self.selected_tasks)
        passwordless = autorizacion_sin_contrasena_activa()

        def worker():
            try:
                if passwordless:
                    cmd = comando_host("pkexec", HELPER_SISTEMA, "maintenance", *tasks)
                else:
                    cmd = comando_pkexec(HELPER_SISTEMA, "es", "maintenance", *tasks)

                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace",
                                        env={**os.environ, "LC_ALL": "C.UTF-8"})
                self.process = proc

                for line in proc.stdout:
                    GLib.idle_add(self._append_console, line.rstrip())

                proc.wait()
                GLib.idle_add(self._on_maintenance_finished, proc.returncode, tasks)

            except Exception as exc:
                GLib.idle_add(self._on_maintenance_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_maintenance_finished(self, returncode, tasks):
        self.running = False
        self.process = None
        self.task_list.set_sensitive(True)
        self._update_run_button()

        if returncode == 0:
            self._append_console(self.translate("\n✓ Mantenimiento completado correctamente"))
            self.status_label.set_text(self.translate("Mantenimiento completado"))
            from aio_core import guardar_registro_mantenimiento
            guardar_registro_mantenimiento(tasks, "ok", False, version=version_app())
        else:
            self._append_console(self.translate("\n✗ El mantenimiento terminó con errores"))
            self.status_label.set_text(self.translate("Mantenimiento finalizado con errores"))
            from aio_core import guardar_registro_mantenimiento
            guardar_registro_mantenimiento(tasks, "error", False, version=version_app())

        self.query_task_states()

    def _on_maintenance_error(self, error):
        self.running = False
        self.process = None
        self.task_list.set_sensitive(True)
        self._update_run_button()
        self._append_console(self.translate("\n✗ Error: ") + error)
        self.status_label.set_text(self.translate("Error en mantenimiento"))

    def _show_preflight_dialog(self, checks):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=self.translate("Comprobaciones de seguridad"))
        details = "\n".join(f"• {w}" for w in checks.get("warnings", []))
        if checks.get("errors"):
            details += "\n\n" + "\n".join(f"• {e}" for e in checks["errors"])
        dialog.format_secondary_text(details)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.run()
        dialog.destroy()

    def _run_diagnostics(self, _btn):
        from .diagnostics_dialog import DiagnosticsDialog
        dialog = DiagnosticsDialog(self.window)
        dialog.show_all()

    def _append_console(self, text):
        buffer = self.console.get_buffer()
        end_iter = buffer.get_end_iter()
        buffer.insert(end_iter, text + "\n")
        mark = buffer.create_mark(None, end_iter, False)
        self.console.scroll_to_mark(mark, 0.0, False, 0.0, 0.0)

    def _clear_console(self):
        buffer = self.console.get_buffer()
        buffer.set_text("")

    def write_log(self, text, tipo="info"):
        prefix = {"info": "", "aviso": "[!] ", "error": "[✗] "}.get(tipo, "")
        self._append_console(prefix + text)

    def on_preferences_changed(self, prefs):
        self.translate = lambda t: TRADUCCIONES.get(prefs["idioma"], {}).get(t, t)
        self.task_list.refresh_translations(self.translate)
        self.btn_run.set_label(self.translate("Ejecutar mantenimiento (%d)") % len(self.selected_tasks))
        self.btn_firmware_toggle.set_label(self.translate("Buscar actualizaciones de firmware")
                                           if not self.firmware_section_expanded
                                           else self.translate("Ocultar firmware"))
        self.btn_diagnostics.set_label(self.translate("Ejecutar diagnóstico"))

    def on_page_activated(self):
        pass