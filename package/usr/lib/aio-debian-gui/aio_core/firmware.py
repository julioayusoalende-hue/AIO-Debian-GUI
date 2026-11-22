"""Consulta e instalación interactiva de firmware a través de fwupd."""

import json
import os
from pathlib import Path
import re
import subprocess
from threading import Thread

from gi.repository import GLib, Gtk, Vte


FWUPDMGR = "/usr/bin/fwupdmgr"


class FirmwarePage(Gtk.Box):
    def __init__(self, parent, translate):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.parent = parent
        self.tr = translate
        self.set_border_width(14)
        self.closed = False
        self.connect("destroy", self._on_destroy)

        label = Gtk.Label(xalign=0, wrap=True, label=translate(
            "Consulta actualizaciones para los dispositivos compatibles con fwupd."))
        self.pack_start(label, False, False, 0)
        self.check = Gtk.Button(label=translate("Buscar actualizaciones de firmware"))
        self.check.set_halign(Gtk.Align.START)
        self.check.connect("clicked", self._check)
        self.pack_start(self.check, False, False, 0)

        self.devices = Gtk.ComboBoxText()
        self.devices.get_accessible().set_name(translate("Dispositivo"))
        self.devices.connect("changed", self._selection_changed)
        self.pack_start(self.devices, False, False, 0)
        self.install = Gtk.Button(label=translate("Actualizar dispositivo…"))
        self.install.set_halign(Gtk.Align.START)
        self.install.set_sensitive(False)
        self.install.connect("clicked", self._confirm)
        self.pack_start(self.install, False, False, 0)

        self.status = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.pack_start(self.status, False, False, 0)
        if not os.access(FWUPDMGR, os.X_OK):
            self.check.set_sensitive(False)
            self.status.set_text(translate("Instala el paquete fwupd para consultar el firmware."))

    def _on_destroy(self, _widget):
        self.closed = True

    def _selection_changed(self, _widget):
        self.install.set_sensitive(self.devices.get_active_id() is not None)

    def _check(self, _button):
        self.devices.remove_all()
        self.check.set_sensitive(False)
        self.status.set_text(self.tr("Buscando actualizaciones de firmware…"))
        Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            refresh = subprocess.run([FWUPDMGR, "refresh"], capture_output=True, text=True,
                                     stdin=subprocess.DEVNULL, timeout=90)
            if refresh.returncode not in (0, 2):
                refresh.check_returncode()
            result = subprocess.run([FWUPDMGR, "get-updates", "--json"], capture_output=True,
                                    text=True, stdin=subprocess.DEVNULL, timeout=60)
            if result.returncode not in (0, 2):
                result.check_returncode()
            devices = []
            payload = {} if result.returncode == 2 and not result.stdout.strip() else json.loads(result.stdout)
            for device in payload.get("Devices", []):
                device_id = device.get("DeviceId", "")
                releases = device.get("Releases") or []
                if not re.fullmatch(r"[0-9a-f]{40}", device_id) or not releases:
                    continue
                name = device.get("Name") or device_id
                version = releases[0].get("Version")
                devices.append((device_id, f"{name} → {version}" if version else name))
        except (OSError, subprocess.SubprocessError, ValueError, AttributeError, TypeError) as error:
            detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
            GLib.idle_add(self._show_updates, [], detail)
        else:
            GLib.idle_add(self._show_updates, devices, None)

    def _show_updates(self, devices, error):
        if self.closed:
            return
        for device_id, label in devices:
            self.devices.append(device_id, label)
        if devices:
            self.devices.set_active(0)
        self.check.set_sensitive(True)
        if error:
            self.status.set_text(self.tr("No se pudo consultar el firmware.") + "\n" + error)
        elif devices:
            self.status.set_text(self.tr("Selecciona un dispositivo para revisar su actualización."))
        else:
            self.status.set_text(self.tr("No hay actualizaciones de firmware disponibles."))

    def _confirm(self, _button):
        device_id = self.devices.get_active_id()
        if not device_id:
            return
        if Path("/run/live/medium").is_dir() or "boot=live" in Path("/proc/cmdline").read_text().split():
            self.status.set_text(self.tr("Actualiza el firmware desde el sistema instalado."))
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.parent, modal=True, message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.CANCEL,
            text=self.tr("¿Actualizar el firmware de %s?") % self.devices.get_active_text())
        dialog.format_secondary_text(self.tr(
            "Mantén el equipo conectado a la corriente. Puede ser necesario reiniciar."))
        dialog.add_button(self.tr("Continuar"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        confirmed = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if confirmed:
            self._open_update(device_id)

    def _open_update(self, device_id):
        # fwupd conserva su propia autorización y sus preguntas interactivas.
        window = Gtk.Window(title=self.tr("Actualizar firmware"), transient_for=self.parent,
                            modal=True, destroy_with_parent=True, default_width=760, default_height=420)
        terminal = Vte.Terminal()
        window.add(terminal)
        running = True
        window.connect("delete-event", lambda *_args: running)
        window.show_all()
        terminal.grab_focus()

        def finished(_terminal, status):
            nonlocal running
            running = False
            self.devices.remove_all()
            if status == 0:
                self.status.set_text(self.tr("Consulta el resultado. El firmware puede requerir reiniciar."))
            else:
                self.status.set_text(self.tr("La actualización no se completó. Consulta el resultado."))
            terminal.feed(("\r\n" + self.tr("Ya puedes cerrar esta ventana.") + "\r\n").encode())

        def started(_terminal, _pid, error, _data):
            if error is not None:
                finished(terminal, 1)
                terminal.feed((error.message + "\r\n").encode())

        terminal.connect("child-exited", finished)
        terminal.spawn_async(
            Vte.PtyFlags.DEFAULT, None, [FWUPDMGR, "update", device_id, "--no-reboot-check"],
            None, GLib.SpawnFlags.DEFAULT, None, None, -1, None, started, None)
