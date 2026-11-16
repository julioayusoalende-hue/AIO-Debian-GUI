#!/usr/bin/env python3
"""Comprobar el seguimiento del tema GTK sin depender del escritorio activo."""
import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath("package/usr/lib/aio-debian-gui"))
from aio_core.gtk_appearance import GLib, MonitorTemaSistema


monitor = MonitorTemaSistema.__new__(MonitorTemaSistema)
monitor.modo = "sistema"
monitor._creando = False
monitor.gtk = Mock()
monitor.gtk.get_property.return_value = "Adwaita-dark"
monitor.gnome = Mock()
monitor.gnome.get_string.return_value = "prefer-light"
monitor.portal = Mock()
monitor.portal.call_sync.return_value = GLib.Variant("(v)", (GLib.Variant("u", 1),))

# El portal prevalece sobre GNOME y el nombre del tema GTK.
monitor.cambiar_modo("sistema")
monitor.gtk.set_property.assert_called_with("gtk-application-prefer-dark-theme", True)

# Sin preferencia del portal, se usa GNOME y después el tema GTK.
monitor.portal.call_sync.return_value = GLib.Variant("(v)", (GLib.Variant("u", 0),))
monitor._cambio_sistema()
monitor.gtk.set_property.assert_called_with("gtk-application-prefer-dark-theme", False)
monitor.gnome.get_string.return_value = "default"
monitor._cambio_sistema()
monitor.gtk.set_property.assert_called_with("gtk-application-prefer-dark-theme", True)

# Las notificaciones del sistema no deben cambiar un tema seleccionado manualmente.
monitor.cambiar_modo("claro")
monitor.gtk.set_property.assert_called_with("gtk-application-prefer-dark-theme", False)
monitor.gtk.set_property.reset_mock()
monitor._cambio_sistema()
monitor._cambio_portal(None, None, "SettingChanged",
                       GLib.Variant("(ssv)", ("org.freedesktop.appearance", "color-scheme",
                                             GLib.Variant("u", 1))))
monitor.gtk.set_property.assert_not_called()

monitor.cambiar_modo("sistema")
monitor.portal.call_sync.return_value = GLib.Variant("(v)", (GLib.Variant("u", 2),))
monitor._cambio_portal(None, None, "SettingChanged",
                       GLib.Variant("(ssv)", ("org.freedesktop.appearance", "color-scheme",
                                             GLib.Variant("u", 2))))
monitor.gtk.set_property.assert_called_with("gtk-application-prefer-dark-theme", False)
print("✔ tema GTK: portal, respaldos, cambios de sistema y modo manual")
