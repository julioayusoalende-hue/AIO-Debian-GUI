"""Seguimiento del tema de escritorio para la interfaz GTK 3."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

from aio_core import appearance as core_appearance


class MonitorTemaSistema:
    """Observa el portal de apariencia y, como respaldo, GNOME/tema GTK."""

    def __init__(self):
        self.modo = "sistema"
        self.portal = None
        self.gnome = None
        self.gtk = Gtk.Settings.get_default()
        self._creando = True
        try:
            self.portal = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None, "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.Settings", None,
            )
            if self.portal.get_name_owner():
                self.portal.connect("g-signal", self._cambio_portal)
            else:
                self.portal = None
        except GLib.Error:
            self.portal = None
        schema = Gio.SettingsSchemaSource.get_default()
        if schema and schema.lookup("org.gnome.desktop.interface", True):
            try:
                self.gnome = Gio.Settings.new("org.gnome.desktop.interface")
                self.gnome.connect("changed::color-scheme", self._cambio_sistema)
            except GLib.Error:
                self.gnome = None
        if self.gtk is not None:
            self.gtk.connect("notify::gtk-theme-name", self._cambio_sistema)
        self._creando = False

    @staticmethod
    def _valor_portal(variant):
        # Read devuelve (v) y el propio valor puede llegar envuelto otra vez.
        while isinstance(variant, GLib.Variant):
            variant = variant.unpack()
            if isinstance(variant, tuple) and len(variant) == 1:
                variant = variant[0]
        return core_appearance.preferencia_portal(variant)

    def _tema_detectado(self):
        if self.portal is not None:
            try:
                dato = self.portal.call_sync(
                    "Read", GLib.Variant(
                        "(ss)", ("org.freedesktop.appearance", "color-scheme")
                    ), Gio.DBusCallFlags.NONE, 1500, None,
                )
                tema = self._valor_portal(dato)
                if tema:
                    return tema
            except (GLib.Error, TypeError, ValueError):
                pass
        if self.gnome is not None:
            tema = core_appearance.preferencia_gnome(
                self.gnome.get_string("color-scheme")
            )
            if tema:
                return tema
        if self.gtk is not None:
            return core_appearance.tema_de_nombre(
                self.gtk.get_property("gtk-theme-name")
            )
        return "claro"

    def _aplicar(self):
        if self.gtk is not None:
            tema = self._tema_detectado() if self.modo == "sistema" else self.modo
            self.gtk.set_property(
                "gtk-application-prefer-dark-theme", tema == "oscuro"
            )

    def _cambio_sistema(self, *_args):
        if not self._creando and self.modo == "sistema":
            self._aplicar()

    def _cambio_portal(self, _proxy, _sender, nombre, parametros):
        if nombre == "SettingChanged" and self.modo == "sistema":
            try:
                espacio, clave, _valor = parametros.unpack()
                if espacio == "org.freedesktop.appearance" and clave == "color-scheme":
                    self._aplicar()
            except (TypeError, ValueError):
                pass

    def cambiar_modo(self, modo):
        self.modo = modo
        self._aplicar()


_monitor_tema = None


def aplicar_tema(tema):
    global _monitor_tema
    if _monitor_tema is None:
        _monitor_tema = MonitorTemaSistema()
    _monitor_tema.cambiar_modo(tema)


