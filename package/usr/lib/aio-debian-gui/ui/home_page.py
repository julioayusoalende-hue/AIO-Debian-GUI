"""Home page - Inicio (GRUB settings)."""

import os
import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from aio_core import (
    traducir, GRUB_HELPER, comando_host, comando_pkexec,
    autorizacion_sin_contrasena_activa,
)
from .widgets.card import Card


class HomePage(Gtk.Box):
    """Pestaña Inicio - Configuración GRUB."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.window = window
        self.translate = traducir
        self.grub_data = None
        self.action_in_progress = False

        self._build_ui()
        self._load_grub_settings()

    def _build_ui(self):
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_overlay_scrolling(False)
        self.pack_start(scroller, True, True, 0)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_border_width(4)
        scroller.add(main_box)

        # --- Entrada predeterminada ---
        entry_frame, entry_box = Card("Entrada predeterminada de GRUB", "system-boot-symbolic")
        main_box.pack_start(entry_frame, False, False, 0)

        self.entry_combo = Gtk.ComboBoxText()
        self.entry_combo.set_sensitive(False)
        entry_box.pack_start(self.entry_combo, False, False, 0)

        entry_btns = Gtk.Box(spacing=6)
        self.btn_load_entry = Gtk.Button(label=self.translate("Cargar entradas"))
        self.btn_load_entry.connect("clicked", self._load_grub_settings)
        entry_btns.pack_start(self.btn_load_entry, False, False, 0)

        self.btn_apply_entry = Gtk.Button(label=self.translate("Aplicar"))
        self.btn_apply_entry.get_style_context().add_class("suggested-action")
        self.btn_apply_entry.connect("clicked", self._apply_grub_entry)
        self.btn_apply_entry.set_sensitive(False)
        entry_btns.pack_start(self.btn_apply_entry, False, False, 0)

        entry_box.pack_start(entry_btns, False, False, 0)

        # --- Tiempo de espera ---
        timeout_frame, timeout_box = Card("Tiempo de espera del menú GRUB", "appointment-symbolic")
        main_box.pack_start(timeout_frame, False, False, 0)

        timeout_row = Gtk.Box(spacing=10)
        timeout_box.pack_start(timeout_row, False, False, 0)

        lbl = Gtk.Label(label=self.translate("Segundos:"), xalign=0)
        timeout_row.pack_start(lbl, False, False, 0)

        self.timeout_spin = Gtk.SpinButton.new_with_range(0, 300, 1)
        self.timeout_spin.set_sensitive(False)
        self.timeout_spin.set_value(5)
        timeout_row.pack_start(self.timeout_spin, False, False, 0)

        self.btn_apply_timeout = Gtk.Button(label=self.translate("Aplicar"))
        self.btn_apply_timeout.connect("clicked", self._apply_grub_timeout)
        self.btn_apply_timeout.set_sensitive(False)
        timeout_row.pack_end(self.btn_apply_timeout, False, False, 0)

        # --- Visibilidad ---
        visibility_frame, visibility_box = Card("Visibilidad del menú GRUB", "view-reveal-symbolic")
        main_box.pack_start(visibility_frame, False, False, 0)

        self.visibility_combo = Gtk.ComboBoxText()
        for val, label in [("menu", self.translate("Menú visible")),
                           ("hidden", self.translate("Oculto (Shift para mostrar)")),
                           ("countdown", self.translate("Cuenta regresiva"))]:
            self.visibility_combo.append(val, label)
        self.visibility_combo.set_sensitive(False)
        visibility_box.pack_start(self.visibility_combo, False, False, 0)

        self.btn_apply_visibility = Gtk.Button(label=self.translate("Aplicar"))
        self.btn_apply_visibility.connect("clicked", self._apply_grub_visibility)
        self.btn_apply_visibility.set_sensitive(False)
        visibility_box.pack_start(self.btn_apply_visibility, False, False, 0)

        # --- Restaurar ---
        restore_frame, restore_box = Card("Restaurar configuración original", "edit-undo-symbolic")
        main_box.pack_start(restore_frame, False, False, 0)

        self.btn_restore = Gtk.Button(label=self.translate("Restaurar ajustes de fábrica"))
        self.btn_restore.connect("clicked", self._restore_grub)
        restore_box.pack_start(self.btn_restore, False, False, 0)

        self.status_label = Gtk.Label(xalign=0, ellipsize=3)
        self.pack_end(self.status_label, False, False, 0)

    def _load_grub_settings(self, _btn=None):
        if self.action_in_progress:
            return
        self._set_action_state(True)
        self.status_label.set_text(self.translate("Cargando configuración GRUB…"))

        def worker():
            try:
                output = subprocess.run(comando_host("cat", "/etc/default/grub"),
                                        capture_output=True, text=True, timeout=5).stdout

                grub = {}
                for line in output.splitlines():
                    if "=" in line and not line.startswith("#"):
                        key, val = line.split("=", 1)
                        grub[key.strip()] = val.strip().strip('"')

                try:
                    entries_out = subprocess.run(
                        comando_host("grub-mkconfig", "-o", "/dev/stdout"),
                        capture_output=True, text=True, timeout=10).stdout
                    entries = []
                    for line in entries_out.splitlines():
                        if "menuentry" in line and "{" in line:
                            import re
                            m = re.search(r'menuentry\s+[\'"]([^\'"]+)[\'"]', line)
                            if m:
                                entries.append(m.group(1))
                except Exception:
                    entries = []

                GLib.idle_add(self._on_grub_loaded, grub, entries)
            except Exception as exc:
                GLib.idle_add(self._on_grub_loaded, None, None, str(exc))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _on_grub_loaded(self, grub, entries, error=None):
        self._set_action_state(False)
        if error:
            self.status_label.set_text(self.translate("Error: ") + error)
            return

        self.grub_data = grub

        self.entry_combo.remove_all()
        if entries:
            for e in entries:
                self.entry_combo.append_text(e)
            current = grub.get("GRUB_DEFAULT", "0")
            try:
                idx = int(current)
                if 0 <= idx < len(entries):
                    self.entry_combo.set_active(idx)
            except ValueError:
                for i, e in enumerate(entries):
                    if e == current:
                        self.entry_combo.set_active(i)
                        break
            self.entry_combo.set_sensitive(True)
            self.btn_apply_entry.set_sensitive(True)
        else:
            self.entry_combo.append_text(self.translate("No se pudieron leer las entradas"))
            self.entry_combo.set_active(0)

        timeout = grub.get("GRUB_TIMEOUT", "5")
        try:
            self.timeout_spin.set_value(int(timeout))
        except ValueError:
            self.timeout_spin.set_value(5)
        self.timeout_spin.set_sensitive(True)
        self.btn_apply_timeout.set_sensitive(True)

        visibility = grub.get("GRUB_TIMEOUT_STYLE", "menu")
        for i in range(self.visibility_combo.get_active() + 1):
            if self.visibility_combo.get_id(i) == visibility:
                self.visibility_combo.set_active(i)
                break
        self.visibility_combo.set_sensitive(True)
        self.btn_apply_visibility.set_sensitive(True)

        self.status_label.set_text(self.translate("Configuración GRUB cargada"))

    def _apply_grub_entry(self, _btn):
        active = self.entry_combo.get_active_text()
        if not active:
            return
        self._set_grub_value("GRUB_DEFAULT", f'"{active}"')

    def _apply_grub_timeout(self, _btn):
        value = str(int(self.timeout_spin.get_value()))
        self._set_grub_value("GRUB_TIMEOUT", value)

    def _apply_grub_visibility(self, _btn):
        value = self.visibility_combo.get_active_id()
        if value:
            self._set_grub_value("GRUB_TIMEOUT_STYLE", value)

    def _set_grub_value(self, key, value):
        if self.action_in_progress:
            return
        self._set_action_state(True)
        self.status_label.set_text(self.translate("Aplicando cambios GRUB…"))

        def worker():
            try:
                if autorizacion_sin_contrasena_activa():
                    cmd = comando_host("pkexec", "/usr/lib/aio-debian-gui/aio-grub-settings",
                                       "set", key, value)
                else:
                    cmd = comando_pkexec("/usr/lib/aio-debian-gui/aio-grub-settings", "es",
                                         "set", key, value)
                subprocess.run(cmd, check=True, timeout=30,
                               capture_output=True, text=True,
                               env={**os.environ, "LC_ALL": "C.UTF-8"})
                GLib.idle_add(self._on_grub_applied, True, self.translate("GRUB actualizado"))
            except Exception as exc:
                GLib.idle_add(self._on_grub_applied, False, str(exc))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _on_grub_applied(self, success, msg):
        self._set_action_state(False)
        if success:
            self.status_label.set_text(self.translate("✓ ") + msg)
            self._load_grub_settings()
        else:
            self.status_label.set_text(self.translate("✗ Error: ") + msg)

    def _restore_grub(self, _btn):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=self.translate("Restaurar GRUB a valores de fábrica"))
        dialog.format_secondary_text(self.translate(
            "Se restaurará /etc/default/grub a la configuración por defecto del sistema. ¿Continuar?"))
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        if dialog.run() != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        dialog.destroy()

        self._set_action_state(True)
        self.status_label.set_text(self.translate("Restaurando GRUB…"))

        def worker():
            try:
                if autorizacion_sin_contrasena_activa():
                    cmd = comando_host("pkexec", "/usr/lib/aio-debian-gui/aio-grub-settings", "restore")
                else:
                    cmd = comando_pkexec("/usr/lib/aio-debian-gui/aio-grub-settings", "es", "restore")
                subprocess.run(cmd, check=True, timeout=30,
                               capture_output=True, text=True,
                               env={**os.environ, "LC_ALL": "C.UTF-8"})
                GLib.idle_add(self._on_grub_applied, True, self.translate("GRUB restaurado"))
            except Exception as exc:
                GLib.idle_add(self._on_grub_applied, False, str(exc))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _set_action_state(self, in_progress):
        self.action_in_progress = in_progress
        sensitive = not in_progress
        self.btn_load_entry.set_sensitive(sensitive)
        self.btn_restore.set_sensitive(sensitive)
        self.window._update_sensitivity()

    def on_preferences_changed(self, prefs):
        self.translate = lambda t: TRADUCCIONES.get(prefs["idioma"], {}).get(t, t)