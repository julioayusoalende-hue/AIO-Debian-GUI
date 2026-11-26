"""Extensión de integración AyusOS para aio-debian-gui."""

import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, GLib

from aio_core.constants import (
    autorizacion_sin_contrasena_activa,
    es_flatpak,
    traducir,
)
from .branding import (
    es_ayusos,
    get_ayusos_version,
    logo_cabecera,
)
from .pages import AyusOSPagesMixin
from .recovery import open_recovery
from .aio_core.ayusos_recovery import is_recovery_boot
from .aio_core.onboarding import launch_onboarding, should_launch_onboarding


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

    def install(self, window):
        """Añade métodos y pestañas AyusOS a la ventana principal."""
        if not es_ayusos():
            return
        for name, value in AyusOSPagesMixin.__dict__.items():
            if name.startswith("__") or not callable(value):
                continue
            setattr(window, name, value.__get__(window, type(window)))

        window._abrir_recuperacion = lambda: open_recovery(window)

        # El gestor de software también vive en la extensión. Se inserta en la
        # misma posición que ocupaba en el core para no cambiar la navegación.
        if not (es_flatpak() or os.environ.get("APPIMAGE") or os.environ.get("SNAP")):
            from .software_manager.manager import SoftwareManagerPage
            window.pagina_software = SoftwareManagerPage(
                window, traducir, autorizacion_sin_contrasena_activa
            )
            window.notebook.insert_page(
                window.pagina_software, Gtk.Label(label=traducir("Gestor de software")), 1
            )
            window.pagina_software.enable_drop(window, window._mostrar_gestor_software)

        pages = [
            (traducir("Actualización AyusOS"), window._pagina_ayusos_update),
            (traducir("Snapshots"), window._pagina_ayusos_snapshots),
            (traducir("Perfil Hardware"), window._pagina_ayusos_hardware),
            (traducir("Diagnósticos"), window._pagina_ayusos_diagnostics),
            (traducir("Apariencia"), window._pagina_ayusos_branding),
        ]
        for title, factory in pages:
            window.notebook.append_page(factory(), Gtk.Label(label=title))

        if is_recovery_boot():
            def mostrar_recuperacion():
                open_recovery(window)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(mostrar_recuperacion)

    def should_launch_onboarding(self):
        return False if is_recovery_boot() else should_launch_onboarding()

    def launch_onboarding(self, parent):
        return launch_onboarding(parent)
