"""Ventana independiente de recuperación para la extensión AyusOS."""

import json
import subprocess
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from aio_core.constants import (
    cabecera_mantenimiento,
    comando_host,
    etiqueta,
    tarjeta_mantenimiento,
    traducir,
)

RECOVERY_HELPER = "/usr/lib/aio-debian-gui/extensions/ayusos/ayusos-recovery"


def _parse_payload(stdout: str) -> dict:
    """Acepta la última línea JSON válida por si el sistema añade avisos."""
    for line in reversed((stdout or "").splitlines()):
        try:
            value = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return {}


def open_recovery(parent):
    """Abre o trae al frente la ventana de recuperación de la extensión."""
    window = getattr(parent, "recovery_window", None)
    if window is not None:
        window.present()
        return window
    window = RecoveryWindow(parent)
    parent.recovery_window = window

    def closed(_window):
        parent.recovery_window = None

    window.connect("destroy", closed)
    window.show_all()
    return window


class RecoveryWindow(Gtk.Window):
    """Herramientas de reparación sin añadir pestañas al Centro de Control."""

    def __init__(self, parent):
        super().__init__(title=traducir("Recuperación de AyusOS"))
        self.parent_window = parent
        self.set_transient_for(parent)
        self.set_default_size(760, 640)
        self.set_border_width(12)
        self.token = None
        self.busy = False
        self.buttons = {}

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.get_style_context().add_class("aio-page")
        self.add(root)

        titulo = etiqueta(traducir("Recuperación del sistema"))
        titulo.get_style_context().add_class("aio-section-title")
        titulo.set_xalign(0)
        root.pack_start(titulo, False, False, 0)
        root.pack_start(etiqueta(traducir(
            "Usa estas herramientas si el sistema no arranca correctamente. "
            "Las acciones privilegiadas solicitarán autorización de administrador."
        )), False, False, 0)

        self.status = etiqueta(traducir("Listo."))
        self.status.set_xalign(0)
        root.pack_start(self.status, False, False, 0)

        tarjeta, caja = tarjeta_mantenimiento(10)
        caja.pack_start(cabecera_mantenimiento(
            traducir("Acciones de recuperación"), "system-run-symbolic"
        ), False, False, 0)
        acciones = Gtk.Grid(column_spacing=8, row_spacing=8)
        self._action_button(acciones, "repair", traducir("Reparar APT/dpkg"), 0, 0)
        self._action_button(acciones, "grub", traducir("Regenerar GRUB"), 1, 0)
        self._action_button(acciones, "diagnostics", traducir("Ejecutar diagnóstico"), 0, 1)
        self._action_button(acciones, "terminal", traducir("Abrir terminal"), 1, 1)
        caja.pack_start(acciones, False, False, 0)
        root.pack_start(tarjeta, False, False, 0)

        tarjeta_snapshots, caja_snapshots = tarjeta_mantenimiento(10)
        caja_snapshots.pack_start(cabecera_mantenimiento(
            traducir("Restaurar Timeshift"), "drive-harddisk-symbolic"
        ), False, False, 0)
        self.snapshot_store = Gtk.ListStore(str, str, str)
        self.snapshot_view = Gtk.TreeView(model=self.snapshot_store)
        self.snapshot_view.set_headers_visible(True)
        for index, title in enumerate((
            traducir("ID"), traducir("Fecha"), traducir("Comentario")
        )):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_resizable(True)
            self.snapshot_view.append_column(column)
        scroll_snapshots = Gtk.ScrolledWindow()
        scroll_snapshots.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_snapshots.set_size_request(-1, 150)
        scroll_snapshots.add(self.snapshot_view)
        caja_snapshots.pack_start(scroll_snapshots, True, True, 0)
        botones_snapshots = Gtk.Box(spacing=8)
        self._action_button(
            botones_snapshots, "snapshots", traducir("Actualizar snapshots")
        )
        self.restore_button = Gtk.Button(label=traducir("Restaurar seleccionado"))
        self.restore_button.connect("clicked", self._restore_selected)
        botones_snapshots.pack_start(self.restore_button, False, False, 0)
        caja_snapshots.pack_start(botones_snapshots, False, False, 0)
        root.pack_start(tarjeta_snapshots, True, True, 0)

        tarjeta_diagnostico, caja_diagnostico = tarjeta_mantenimiento(10)
        caja_diagnostico.pack_start(cabecera_mantenimiento(
            traducir("Resultado del diagnóstico"), "dialog-information-symbolic"
        ), False, False, 0)
        self.diagnostics_store = Gtk.ListStore(str, str, str)
        self.diagnostics_view = Gtk.TreeView(model=self.diagnostics_store)
        self.diagnostics_view.set_headers_visible(True)
        for index, title in enumerate((
            traducir("Comprobación"), traducir("Estado"), traducir("Detalle")
        )):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_resizable(True)
            self.diagnostics_view.append_column(column)
        scroll_diagnostico = Gtk.ScrolledWindow()
        scroll_diagnostico.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_diagnostico.set_size_request(-1, 150)
        scroll_diagnostico.add(self.diagnostics_view)
        caja_diagnostico.pack_start(scroll_diagnostico, True, True, 0)
        root.pack_start(tarjeta_diagnostico, True, True, 0)

        self.output = Gtk.TextView(editable=False, cursor_visible=False)
        self.output.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.output.set_size_request(-1, 100)
        scroll_output = Gtk.ScrolledWindow()
        scroll_output.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_output.add(self.output)
        root.pack_start(scroll_output, False, True, 0)

        self.connect("delete-event", self._delete_event)

    def _action_button(self, container, action, label, column=0, row=0):
        button = Gtk.Button(label=label)
        if action in {"repair", "grub"}:
            button.get_style_context().add_class("suggested-action")
        if action == "terminal":
            button.connect("clicked", self._open_terminal)
        else:
            button.connect("clicked", self._run_action, action)
        self.buttons[action] = button
        if isinstance(container, Gtk.Grid):
            container.attach(button, column, row, 1, 1)
        else:
            container.pack_start(button, False, False, 0)
        return button

    def _set_actions_sensitive(self, sensitive):
        for button in self.buttons.values():
            button.set_sensitive(sensitive)
        self.restore_button.set_sensitive(sensitive)

    def _run_action(self, _button, action, snapshot_id=None):
        if self.busy:
            return
        token = self.parent_window._iniciar_operacion(traducir("Recuperación de AyusOS"))
        if token is None:
            self.status.set_text(traducir("Hay otra operación en curso."))
            return
        self.token = token
        self.busy = True
        self._set_actions_sensitive(False)
        self.status.set_text(traducir("Esperando autorización o ejecutando la acción…"))
        command = comando_host("pkexec", RECOVERY_HELPER, action)
        if snapshot_id:
            command.append(snapshot_id)

        def worker():
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=900,
                    stdin=subprocess.DEVNULL,
                )
                GLib.idle_add(
                    self._action_done,
                    action,
                    result.returncode,
                    result.stdout,
                    result.stderr,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                GLib.idle_add(self._action_done, action, 1, "", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _action_done(self, action, returncode, stdout, stderr):
        self.busy = False
        self.parent_window._finalizar_operacion(self.token)
        self.token = None
        self._set_actions_sensitive(True)
        payload = _parse_payload(stdout)
        success = returncode == 0 and bool(payload.get("success", False))
        message = payload.get("message") or stderr.strip() or stdout.strip()
        if message:
            self.output.get_buffer().set_text(message)
        if not success:
            self.status.set_text(traducir("Error: %s") % (
                message or traducir("la acción de recuperación falló")
            ))
            return GLib.SOURCE_REMOVE

        if action == "snapshots":
            self.snapshot_store.clear()
            for snapshot in payload.get("snapshots", []):
                self.snapshot_store.append([
                    str(snapshot.get("id", "")),
                    str(snapshot.get("date", "")),
                    str(snapshot.get("comment", "")),
                ])
            self.status.set_text(traducir("Snapshots actualizados."))
        elif action == "diagnostics":
            self.diagnostics_store.clear()
            diagnostics = payload.get("diagnostics", {})
            for name, data in diagnostics.items():
                if name.startswith("_"):
                    continue
                self.diagnostics_store.append([
                    name.replace("_", " "),
                    traducir("OK") if data.get("ok") else traducir("FALLO"),
                    str(data.get("message") or data.get("details") or ""),
                ])
            summary = diagnostics.get("_summary", {})
            self.status.set_text(traducir("Diagnóstico: %s/%s OK") % (
                summary.get("passed", 0), summary.get("total", 0)
            ))
        elif action == "restore":
            self.status.set_text(traducir(
                "Snapshot restaurado. Reinicia para aplicar los cambios."
            ))
        else:
            self.status.set_text(traducir("Acción completada correctamente."))
        return GLib.SOURCE_REMOVE

    def _restore_selected(self, _button):
        selection = self.snapshot_view.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            self.status.set_text(traducir("Selecciona un snapshot."))
            return
        snapshot_id = model.get_value(treeiter, 0)
        if not snapshot_id:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=traducir("¿Restaurar el snapshot %s?") % snapshot_id,
        )
        dialog.format_secondary_text(traducir(
            "Esta acción revierte el sistema al estado del snapshot y requiere reinicio."
        ))
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            self._run_action(None, "restore", snapshot_id)

    def _open_terminal(self, _button):
        try:
            subprocess.Popen(
                comando_host(
                    "gnome-terminal", "--title", traducir("Terminal de recuperación"),
                    "--", "/bin/bash",
                ),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            self.status.set_text(traducir("No se pudo abrir la terminal: %s") % exc)
        else:
            self.status.set_text(traducir("Terminal abierta como usuario normal."))

    def _delete_event(self, _window, _event):
        if self.busy:
            self.status.set_text(traducir("Espera a que termine la operación actual."))
            return True
        return False
