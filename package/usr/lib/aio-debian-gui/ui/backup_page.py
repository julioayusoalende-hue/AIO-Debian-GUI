"""Backup page."""

import os
import threading
import subprocess
import shutil
import json

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from aio_core.desktop_backup import (
    detect, restore, version as desktop_version, user_dirs,
    read as desktop_read, snapshot as desktop_snapshot, save as desktop_save, LABELS
)

from aio_core import (
    traducir, APLICACIONES_BACKUP, BACKUP_ICON_DIR,
    comando_host, paquete_instalado, HELPER_SISTEMA,
    APT_BACKUP_HELPER, APT_BACKUP_FILENAME, APT_BACKUP_LIMIT,
    autorizacion_sin_contrasena_activa, comando_pkexec,
)
from .widgets.card import Card


class BackupPage(Gtk.Box):
    """Pestaña Backup."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.window = window
        self.translate = traducir
        self.action_in_progress = False

        self._build_ui()

    def _build_ui(self):
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_overlay_scrolling(False)
        self.pack_start(scroller, True, True, 0)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_border_width(4)
        scroller.add(main_box)

        # --- Repositorios APT ---
        repo_frame, repo_box = Card("Repositorios APT", "package-x-generic-symbolic")
        main_box.pack_start(repo_frame, False, False, 0)

        btn_backup_repos = Gtk.Button(label=self.translate("Copiar repositorios"))
        btn_backup_repos.connect("clicked", self._backup_repos)
        repo_box.pack_start(btn_backup_repos, False, False, 0)

        btn_restore_repos = Gtk.Button(label=self.translate("Restaurar repositorios"))
        btn_restore_repos.connect("clicked", self._restore_repos)
        repo_box.pack_start(btn_restore_repos, False, False, 0)

        # --- Ajustes de escritorio ---
        desktop_frame, desktop_box = Card("Ajustes de escritorio", "preferences-desktop-symbolic")
        main_box.pack_start(desktop_frame, False, False, 0)

        self.desktop_env = self._detect_desktop()

        if self.desktop_env == "gnome":
            btn_backup_desk = Gtk.Button(label=self.translate("Copiar ajustes de GNOME"))
            btn_backup_desk.connect("clicked", self._backup_gnome)
            desktop_box.pack_start(btn_backup_desk, False, False, 0)

            btn_restore_desk = Gtk.Button(label=self.translate("Restaurar ajustes de GNOME"))
            btn_restore_desk.connect("clicked", self._restore_gnome)
            desktop_box.pack_start(btn_restore_desk, False, False, 0)
        elif self.desktop_env == "kde":
            btn_backup_desk = Gtk.Button(label=self.translate("Copiar ajustes de KDE Plasma"))
            btn_backup_desk.connect("clicked", self._backup_kde)
            desktop_box.pack_start(btn_backup_desk, False, False, 0)

            btn_restore_desk = Gtk.Button(label=self.translate("Restaurar ajustes de KDE Plasma"))
            btn_restore_desk.connect("clicked", self._restore_kde)
            desktop_box.pack_start(btn_restore_desk, False, False, 0)
        else:
            lbl = Gtk.Label(label=self.translate("Escritorio no detectado o no soportado"))
            lbl.get_style_context().add_class("dim-label")
            desktop_box.pack_start(lbl, False, False, 0)

        # --- Aplicaciones de respaldo ---
        apps_frame, apps_box = Card("Aplicaciones de respaldo", "drive-harddisk-symbolic")
        main_box.pack_start(apps_frame, False, False, 0)

        for app_id, app_info in APLICACIONES_BACKUP.items():
            row = Gtk.Box(spacing=10, margin_top=6, margin_bottom=6)
            icon = Gtk.Image.new_from_icon_name(app_info["icon"], Gtk.IconSize.BUTTON)
            icon.set_pixel_size(32)
            row.pack_start(icon, False, False, 0)

            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            name = Gtk.Label(label=app_info["name"], xalign=0)
            name.get_style_context().add_class("aio-task-name")
            info.pack_start(name, False, False, 0)

            desc = Gtk.Label(label=app_info["description"], xalign=0, wrap=True)
            desc.get_style_context().add_class("dim-label")
            desc.set_line_wrap(True)
            info.pack_start(desc, False, False, 0)

            row.pack_start(info, True, True, 0)

            btn = Gtk.Button(label=self.translate("Instalar" if not paquete_instalado(app_info["package"]) else "Abrir"))
            btn.connect("clicked", self._launch_backup_app, app_info)
            row.pack_end(btn, False, False, 0)

            apps_box.pack_start(row, False, False, 0)

        self.status_label = Gtk.Label(xalign=0, ellipsize=3)
        self.pack_end(self.status_label, False, False, 0)

    def _detect_desktop(self):
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "gnome" in desktop or "unity" in desktop:
            return "gnome"
        if "kde" in desktop or "plasma" in desktop:
            return "kde"
        return "unknown"

    def _set_action_state(self, in_progress):
        self.action_in_progress = in_progress
        self.window._update_sensitivity()

    def _backup_repos(self, _btn):
        if self.action_in_progress:
            return
        self._set_action_state(True)
        self.status_label.set_text(self.translate("Copiando repositorios APT…"))

        def worker():
            try:
                if autorizacion_sin_contrasena_activa():
                    cmd = comando_host("pkexec", HELPER_SISTEMA, "apt-backup")
                else:
                    cmd = comando_pkexec(APT_BACKUP_HELPER, "es", "backup")
                subprocess.run(cmd, check=True, timeout=30,
                               capture_output=True, text=True,
                               env={**os.environ, "LC_ALL": "C.UTF-8"})
                GLib.idle_add(self._on_action_done, True, self.translate("Repositorios copiados"))
            except Exception as exc:
                GLib.idle_add(self._on_action_done, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _restore_repos(self, _btn):
        if self.action_in_progress:
            return
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=self.translate("Restaurar repositorios APT"))
        dialog.format_secondary_text(self.translate(
            "Se sobrescribirán los repositorios actuales con la copia guardada. ¿Continuar?"))
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        if dialog.run() != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        dialog.destroy()

        self._set_action_state(True)
        self.status_label.set_text(self.translate("Restaurando repositorios APT…"))

        def worker():
            try:
                if autorizacion_sin_contrasena_activa():
                    cmd = comando_host("pkexec", HELPER_SISTEMA, "apt-restore")
                else:
                    cmd = comando_pkexec(APT_BACKUP_HELPER, "es", "restore")
                subprocess.run(cmd, check=True, timeout=30,
                               capture_output=True, text=True,
                               env={**os.environ, "LC_ALL": "C.UTF-8"})
                GLib.idle_add(self._on_action_done, True, self.translate("Repositorios restaurados"))
            except Exception as exc:
                GLib.idle_add(self._on_action_done, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _backup_gnome(self, _btn):
        self._run_backup("gnome")

    def _restore_gnome(self, _btn):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=self.translate("Restaurar ajustes de GNOME"))
        dialog.format_secondary_text(self.translate(
            "Se restaurarán los ajustes, extensiones y paneles. Se hará una copia previa. ¿Continuar?"))
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        if dialog.run() != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        dialog.destroy()
        self._run_restore("gnome")

    def _backup_kde(self, _btn):
        self._run_backup("plasma")

    def _restore_kde(self, _btn):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=self.translate("Restaurar ajustes de KDE Plasma"))
        dialog.format_secondary_text(self.translate(
            "Se restaurarán los ajustes, widgets y paneles. Se hará una copia previa. ¿Continuar?"))
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        if dialog.run() != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        dialog.destroy()
        self._run_restore("plasma")

    def _run_backup(self, desktop):
        self._set_action_state(True)
        self.status_label.set_text(self.translate("Copiando ajustes de %s…") % LABELS.get(desktop, desktop))

        def worker():
            try:
                dirs = user_dirs()
                files = desktop_snapshot(desktop, dirs)
                release = desktop_version(desktop)
                # Guardar en archivo temporal
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                    tmp_path = tmp.name
                desktop_save(Path(tmp_path), desktop, release, files)
                # Mover a ubicación final
                final_path = Path.home() / f".aio-backup-{desktop}-{release}.zip"
                import shutil
                shutil.move(tmp_path, final_path)
                GLib.idle_add(self._on_action_done, True, self.translate("Ajustes de %s copiados") % LABELS.get(desktop, desktop))
            except Exception as exc:
                GLib.idle_add(self._on_action_done, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _run_restore(self, desktop):
        self._set_action_state(True)
        self.status_label.set_text(self.translate("Restaurando ajustes de %s…") % LABELS.get(desktop, desktop))

        def worker():
            try:
                # Buscar archivo de backup más reciente
                backups = list(Path.home().glob(f".aio-backup-{desktop}-*.zip"))
                if not backups:
                    raise FileNotFoundError("No hay copia de seguridad para %s" % desktop)
                latest = max(backups, key=lambda p: p.stat().st_mtime)
                
                dirs = user_dirs()
                release, files = desktop_read(latest, desktop)
                
                # Hacer backup previo antes de restaurar
                prev_files = desktop_snapshot(desktop, dirs)
                prev_release = desktop_version(desktop)
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                    prev_path = tmp.name
                desktop_save(Path(prev_path), desktop, prev_release, prev_files)
                
                # Restaurar
                desktop_restore(desktop, release, files, dirs)
                
                GLib.idle_add(self._on_action_done, True, self.translate("Ajustes de %s restaurados") % LABELS.get(desktop, desktop))
            except Exception as exc:
                GLib.idle_add(self._on_action_done, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _launch_backup_app(self, _btn, app_info):
        if paquete_instalado(app_info["package"]):
            subprocess.Popen([app_info["command"]])
        else:
            dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                       message_type=Gtk.MessageType.QUESTION,
                                       buttons=Gtk.ButtonsType.OK_CANCEL,
                                       text=app_info["prompt"])
            if dialog.run() == Gtk.ResponseType.OK:
                self._install_app(app_info["package"])
            dialog.destroy()

    def _install_app(self, package):
        self._set_action_state(True)
        self.status_label.set_text(self.translate("Instalando %s…") % package)

        def worker():
            try:
                if autorizacion_sin_contrasena_activa():
                    cmd = comando_host("pkexec", HELPER_SISTEMA, "install", package)
                else:
                    cmd = comando_pkexec(HELPER_SISTEMA, "es", "install", package)
                subprocess.run(cmd, check=True, timeout=120,
                               capture_output=True, text=True,
                               env={**os.environ, "LC_ALL": "C.UTF-8"})
                GLib.idle_add(self._on_action_done, True, self.translate("%s instalado") % package)
            except Exception as exc:
                GLib.idle_add(self._on_action_done, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_action_done(self, success, msg):
        self._set_action_state(False)
        if success:
            self.status_label.set_text(self.translate("✓ ") + msg)
        else:
            self.status_label.set_text(self.translate("✗ Error: ") + msg)
            dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                       message_type=Gtk.MessageType.ERROR,
                                       buttons=Gtk.ButtonsType.CLOSE,
                                       text=self.translate("Error"))
            dialog.format_secondary_text(msg[:500])
            dialog.run()
            dialog.destroy()

    def on_preferences_changed(self, prefs):
        self.translate = lambda t: TRADUCCIONES.get(prefs["idioma"], {}).get(t, t)