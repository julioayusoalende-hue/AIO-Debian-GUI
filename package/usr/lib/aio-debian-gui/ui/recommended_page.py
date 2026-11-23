"""Recommended apps page."""

import os
import threading
import subprocess
import shutil

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from aio_core.recommended_list import exportar, importar

from aio_core import (
    traducir, APPS_RECOMENDADAS, RECOMMENDED_ICON_DIR,
    nombre_icono_recomendada, icono_recomendada,
    paquete_instalado, comando_host, es_flatpak,
)
from .widgets.card import Card


class RecommendedPage(Gtk.Box):
    """Pestaña Apps recomendadas."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.window = window
        self.translate = traducir

        self.apps_data = APPS_RECOMENDADAS
        self.filter_category = "Todas"
        self.filter_search = ""
        self.installed_cache = {}
        self.scan_generation = 0

        self._build_ui()
        self._scan_installed_async()

    def _build_ui(self):
        toolbar = Gtk.Box(spacing=8)
        self.pack_start(toolbar, False, False, 0)

        self.category_combo = Gtk.ComboBoxText()
        self.category_combo.append_text(self.translate("Todas"))
        categories = sorted(set(app["category"] for app in self.apps_data))
        for cat in categories:
            self.category_combo.append_text(self.translate(cat))
        self.category_combo.set_active(0)
        self.category_combo.connect("changed", self._on_category_changed)
        toolbar.pack_start(self.category_combo, False, False, 0)

        self.search_entry = Gtk.SearchEntry(placeholder_text=self.translate("Buscar por nombre o descripción…"))
        self.search_entry.connect("changed", self._on_search_changed)
        toolbar.pack_start(self.search_entry, True, True, 0)

        self.btn_install_selected = Gtk.Button(label=self.translate("Instalar seleccionadas"))
        self.btn_install_selected.get_style_context().add_class("suggested-action")
        self.btn_install_selected.connect("clicked", self._install_selected)
        self.btn_install_selected.set_sensitive(False)
        toolbar.pack_end(self.btn_install_selected, False, False, 0)

        self.btn_refresh = Gtk.Button(label=self.translate("Actualizar lista"))
        self.btn_refresh.connect("clicked", self._scan_installed_async)
        toolbar.pack_end(self.btn_refresh, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_overlay_scrolling(False)
        self.pack_start(scroller, True, True, 0)

        self.flowbox = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.MULTIPLE,
                                    column_spacing=12, row_spacing=12,
                                    max_children_per_line=30, min_children_per_line=1)
        self.flowbox.connect("selected-children-changed", self._on_selection_changed)
        scroller.add(self.flowbox)

        self.status_label = Gtk.Label(xalign=0, ellipsize=3)
        self.pack_end(self.status_label, False, False, 0)

        self._populate_flowbox()

    def _populate_flowbox(self):
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)

        for app in self.apps_data:
            if self._app_matches_filters(app):
                card = self._create_app_card(app)
                self.flowbox.add(card)

        self.flowbox.show_all()
        self._update_status()

    def _app_matches_filters(self, app):
        if self.filter_category != "Todas" and app["category"] != self.filter_category:
            return False
        if self.filter_search:
            query = self.filter_search.lower()
            searchable = f"{app['name']} {app['description']} {app['category']}".lower()
            if query not in searchable:
                return False
        return True

    def _create_app_card(self, app):
        frame = Gtk.Frame()
        frame.get_style_context().add_class("aio-card")
        frame.set_margin_top(4)
        frame.set_margin_bottom(4)
        frame.set_margin_start(4)
        frame.set_margin_end(4)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        frame.add(box)

        header = Gtk.Box(spacing=10)
        icon = icono_recomendada(app)
        header.pack_start(icon, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_lbl = Gtk.Label(label=app["name"], xalign=0)
        name_lbl.get_style_context().add_class("aio-heading")
        info.pack_start(name_lbl, False, False, 0)

        cat_lbl = Gtk.Label(label=self.translate(app["category"]), xalign=0)
        cat_lbl.get_style_context().add_class("dim-label")
        info.pack_start(cat_lbl, False, False, 0)

        header.pack_start(info, True, True, 0)

        check = Gtk.CheckButton()
        check.set_valign(Gtk.Align.CENTER)
        check.connect("toggled", self._on_card_toggled, app)
        header.pack_end(check, False, False, 0)

        box.pack_start(header, False, False, 0)

        desc_lbl = Gtk.Label(label=app["description"], xalign=0, wrap=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        desc_lbl.set_max_width_chars(40)
        box.pack_start(desc_lbl, False, False, 0)

        channels_box = Gtk.Box(spacing=6)
        for ch in app["channels"]:
            ch_type = ch["type"]
            if ch_type == "deb":
                btn = Gtk.Button(label=self.translate("DEB (APT)"))
                btn.connect("clicked", self._install_deb, app, ch)
            elif ch_type == "flatpak":
                btn = Gtk.Button(label=self.translate("Flatpak"))
                btn.connect("clicked", self._install_flatpak, app, ch)
            elif ch_type == "deb-download":
                btn = Gtk.Button(label=self.translate("Descargar .deb"))
                btn.connect("clicked", self._download_deb, app, ch)
            else:
                continue
            btn.set_size_request(100, -1)
            channels_box.pack_start(btn, False, False, 0)

        box.pack_start(channels_box, False, False, 0)

        frame.app_data = app
        frame.check = check
        frame.installed = self.installed_cache.get(app["id"], False)

        self._update_card_state(frame)

        return frame

    def _update_card_state(self, frame):
        app = frame.app_data
        installed = self.installed_cache.get(app["id"], False)
        frame.installed = installed

        if installed:
            frame.check.set_active(True)
            frame.check.set_sensitive(False)
            frame.check.set_tooltip_text(self.translate("Ya instalado"))
            for child in frame.get_children():
                self._set_children_sensitive(child, False)
        else:
            frame.check.set_active(False)
            frame.check.set_sensitive(True)
            frame.check.set_tooltip_text(None)
            for child in frame.get_children():
                self._set_children_sensitive(child, True)

    def _set_children_sensitive(self, widget, sensitive):
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                self._set_children_sensitive(child, sensitive)
        elif hasattr(widget, "set_sensitive"):
            widget.set_sensitive(sensitive)

    def _on_category_changed(self, combo):
        self.filter_category = combo.get_active_text() or "Todas"
        self._populate_flowbox()

    def _on_search_changed(self, entry):
        self.filter_search = entry.get_text().strip().lower()
        self._populate_flowbox()

    def _on_selection_changed(self, flowbox):
        selected = flowbox.get_selected_children()
        count = len(selected)
        self.btn_install_selected.set_sensitive(count > 0)
        self.btn_install_selected.set_label(self.translate("Instalar seleccionadas (%d)") % count)

    def _on_card_toggled(self, check, app):
        pass

    def _install_selected(self, _btn):
        selected = self.flowbox.get_selected_children()
        for frame in selected:
            app = frame.app_data
            if not self.installed_cache.get(app["id"], False):
                for ch in app["channels"]:
                    if ch["type"] == "deb":
                        self._install_deb(None, app, ch)
                        break
                else:
                    for ch in app["channels"]:
                        if ch["type"] == "flatpak":
                            self._install_flatpak(None, app, ch)
                            break

    def _install_deb(self, _btn, app, channel):
        self._run_install(self.translate("Instalando %s (DEB)…") % app["name"],
                          ["pkexec", "/usr/lib/aio-debian-gui/aio-debian-gui-helper",
                           "install", channel["package"]])

    def _install_flatpak(self, _btn, app, channel):
        scope = "system" if self.window.snapd_presente else "user"
        self._run_install(self.translate("Instalando %s (Flatpak)…") % app["name"],
                          ["/usr/bin/flatpak", f"--{scope}", "install", "-y", "--",
                           channel.get("remote", "flathub"), channel["app_id"]])

    def _download_deb(self, _btn, app, channel):
        import webbrowser
        webbrowser.open(channel["uri"])

    def _run_install(self, msg, cmd):
        self.status_label.set_text(msg)
        self.btn_refresh.set_sensitive(False)
        self.btn_install_selected.set_sensitive(False)

        def worker():
            try:
                subprocess.run(cmd, check=True, timeout=300,
                               capture_output=True, text=True,
                               env={**os.environ, "LC_ALL": "C.UTF-8"})
                GLib.idle_add(self._on_install_done, True, None)
            except subprocess.CalledProcessError as exc:
                GLib.idle_add(self._on_install_done, False, exc.stderr)
            except Exception as exc:
                GLib.idle_add(self._on_install_done, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_install_done(self, success, error):
        self.btn_refresh.set_sensitive(True)
        self._scan_installed_async()
        if success:
            self.status_label.set_text(self.translate("Instalación completada"))
        else:
            self.status_label.set_text(self.translate("Error en instalación"))
            if error:
                dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                           message_type=Gtk.MessageType.ERROR,
                                           buttons=Gtk.ButtonsType.CLOSE,
                                           text=self.translate("Error instalando aplicación"))
                dialog.format_secondary_text(error[:500])
                dialog.run()
                dialog.destroy()

    def _scan_installed_async(self, _btn=None):
        self.scan_generation += 1
        gen = self.scan_generation
        self.status_label.set_text(self.translate("Escaneando aplicaciones instaladas…"))
        self.btn_refresh.set_sensitive(False)

        def worker():
            installed = {}
            try:
                out = subprocess.run(comando_host("dpkg-query", "-W", "-f=${Package}\n"),
                                     capture_output=True, text=True, timeout=10).stdout
                for pkg in out.splitlines():
                    installed[pkg.strip()] = True
            except Exception:
                pass
            try:
                out = subprocess.run(comando_host("flatpak", "list", "--app", "--columns=name"),
                                     capture_output=True, text=True, timeout=10).stdout
                for name in out.splitlines():
                    installed[name.strip()] = True
            except Exception:
                pass

            if gen == self.scan_generation:
                GLib.idle_add(self._on_scan_done, installed)

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self, installed):
        self.installed_cache = installed
        for child in self.flowbox.get_children():
            if hasattr(child, "app_data"):
                self._update_card_state(child)
        self._update_status()
        self.btn_refresh.set_sensitive(True)

    def _update_status(self):
        total = len(self.apps_data)
        installed = sum(1 for app in self.apps_data if self.installed_cache.get(app["id"]))
        self.status_label.set_text(self.translate("%d aplicaciones, %d instaladas") % (total, installed))

    def on_preferences_changed(self, prefs):
        self.translate = lambda t: TRADUCCIONES.get(prefs["idioma"], {}).get(t, t)
        self.category_combo.set_active(0)
        self._populate_flowbox()

    def refresh_if_needed(self):
        if self.scan_generation == 0:
            self._scan_installed_async()

    def on_page_activated(self):
        self.refresh_if_needed()