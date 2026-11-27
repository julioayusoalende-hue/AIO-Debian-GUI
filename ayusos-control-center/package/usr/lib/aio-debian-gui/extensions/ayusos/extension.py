"""Extensión de integración AyusOS para aio-debian-gui."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from aio_core.constants import traducir
from gi.repository import GLib, Gtk

from .aio_core.ayusos_recovery import is_recovery_boot
from .aio_core.onboarding import launch_onboarding, should_launch_onboarding
from .branding import (
    es_ayusos,
    get_ayusos_version,
    logo_cabecera,
)
from .pages import AyusOSPagesMixin
from .recovery import open_recovery

# IDs de aplicaciones que forman parte de la instalación estándar de AyusOS.
# Estos coinciden con los IDs en APPS_RECOMENDADAS del core.
AYUSOS_APPS = {
    "audacity", "bitwarden", "brave", "btop", "celluloid", "deluge",
    "feishin", "flameshot", "gimp", "gnome-boxes", "gnome-calendar",
    "gnome-clocks", "gnome-disk-utility", "gnome-text-editor", "gnome-tweaks",
    "google-chrome", "handbrake", "htop", "inkscape", "kdenlive", "krita",
    "libreoffice", "loupe", "neofetch", "obs-studio", "onlyoffice", "peek",
    "pipewire", "signal", "thunderbird", "timeshift", "transmission", "vscode",
    "vlc", "wireguard", "youtube-dl", "zoom",
}


class Extension:
    name = "ayusos"

    def is_active(self):
        return es_ayusos()

    def app_title(self):
        return traducir("Centro de Control de AyusOS") if es_ayusos() else None

    def app_icon(self):
        return "ayusos-control-center" if es_ayusos() else None

    def header_logo(self, size):
        return logo_cabecera(size) if es_ayusos() else None

    def system_name(self, datos):
        return traducir("AyusOS Linux") if es_ayusos() else None

    def system_version(self, datos):
        if not es_ayusos():
            return None
        return get_ayusos_version() or datos.get("VERSION_ID")

    def ayusos_apps(self):
        """Devuelve el conjunto de IDs de aplicaciones incluidas en AyusOS."""
        return AYUSOS_APPS

    def install(self, window):
        """Añade métodos y pestañas AyusOS a la ventana principal."""
        if not es_ayusos():
            return
        for name, value in AyusOSPagesMixin.__dict__.items():
            if name.startswith("__") or not callable(value):
                continue
            setattr(window, name, value.__get__(window, type(window)))

        # Botón "Abrir recuperación" del diagnóstico.
        window._abrir_recuperacion = lambda: open_recovery(window)

        pages = [
            (traducir("Actualización AyusOS"), window._pagina_ayusos_update),
            (traducir("Snapshots"), window._pagina_ayusos_snapshots),
            (traducir("Perfil Hardware"), window._pagina_ayusos_hardware),
            (traducir("Diagnósticos AyusOS"), window._pagina_ayusos_diagnostics),
            (traducir("Branding AyusOS"), window._pagina_ayusos_branding),
            (traducir("Identidad"), window._pagina_ayusos_identity),
        ]
        for title, factory in pages:
            window.notebook.append_page(factory(), Gtk.Label(label=title))

        # Añadir filtro "Perfil AyusOS" a la página de Apps recomendadas
        self._añadir_filtro_ayusos(window)

        # Soporte de modo recuperación
        if is_recovery_boot():
            def mostrar_recuperacion():
                open_recovery(window)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(mostrar_recuperacion)

    def _añadir_filtro_ayusos(self, window):
        """Añade un botón para filtrar apps del perfil AyusOS."""
        if not all(hasattr(window, name) for name in ("recommended_category", "recommended_grid", "recommended_empty")):
            return
        # Buscar el contenedor de filtros (search + category)
        filtro_box = window.recommended_category.get_parent()
        if not filtro_box or not isinstance(filtro_box, Gtk.Box):
            return
        # Añadir combo de perfil
        perfil_combo = Gtk.ComboBoxText()
        perfil_combo.append("", traducir("Todos los perfiles"))
        perfil_combo.append("ayusos", traducir("Perfil AyusOS"))
        perfil_combo.set_active_id("")
        perfil_combo.get_accessible().set_name(traducir("Perfil de aplicaciones"))
        perfil_combo.connect("changed", self._on_perfil_changed, window)
        filtro_box.pack_start(perfil_combo, False, False, 0)
        filtro_box.show_all()
        window.ayusos_perfil_combo = perfil_combo

    def _on_perfil_changed(self, combo, window):
        app_ids = self.ayusos_apps()
        window.recommended_extra_filter = app_ids.__contains__ if combo.get_active_id() == "ayusos" else None
        window._filtrar_recomendadas(window.recommended_search, window.recommended_empty)

    def should_launch_onboarding(self):
        return False if is_recovery_boot() else should_launch_onboarding()

    def launch_onboarding(self, parent):
        return launch_onboarding(parent)

    def is_recovery_boot(self):
        return is_recovery_boot()
