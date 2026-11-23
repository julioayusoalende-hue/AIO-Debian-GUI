"""Software page wrapper for EnhancedSoftwareManagerPage."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

# Usar el manager mejorado (ya copiado a software_manager/)
from software_manager.manager import EnhancedSoftwareManagerPage
from aio_core import traducir, autorizacion_sin_contrasena_activa


class SoftwarePage(Gtk.Box):
    """Wrapper para EnhancedSoftwareManagerPage con integración en la ventana principal."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.translate = traducir

        # Instanciar el gestor de software mejorado
        self.manager = EnhancedSoftwareManagerPage(
            window, traducir, autorizacion_sin_contrasena_activa
        )
        self.pack_start(self.manager, True, True, 0)

        # Conectar señales para actualizar estado global
        self.manager.connect("notify::busy", self._on_busy_changed)

    def _on_busy_changed(self, manager, _pspec):
        self.window._update_sensitivity()

    def set_sensitive(self, sensitive):
        self.manager.set_sensitive(sensitive)

    def on_page_activated(self):
        """Se llama al activar la pestaña."""
        if hasattr(self.manager, "load") and not self.manager.loaded:
            self.manager.load()

    def refresh(self):
        if hasattr(self.manager, "load"):
            self.manager.load(force=True)

    def focus_search(self):
        if hasattr(self.manager, "search_entry"):
            self.manager.search_entry.grab_focus()