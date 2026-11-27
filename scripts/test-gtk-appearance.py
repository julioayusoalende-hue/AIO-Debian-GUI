#!/usr/bin/env python3
"""Comprobar el seguimiento del tema GTK sin depender del escritorio activo."""
import os
import runpy
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath("package/usr/lib/aio-debian-gui"))
from aio_core.gtk_appearance import GLib, Gtk, MonitorTemaSistema

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

# Renderizar la página y una tarjeta con los mismos selectores de la app.
# El color de los fondos debe cambiar a la vez que el texto.
if Gtk.init_check([])[0]:
    app = runpy.run_path("package/usr/bin/aio-debian-gui", run_name="aio_theme_test")
    provider = Gtk.CssProvider()
    provider.load_from_data(app["ESTILO_APLICACION"].encode())
    window = Gtk.OffscreenWindow()
    window.set_default_size(300, 160)
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    page.get_style_context().add_class("aio-page")
    card, content = app["tarjeta_mantenimiento"](12)
    label = Gtk.Label(label="Tareas")
    content.add(label)
    card.set_margin_start(16)
    card.set_margin_end(16)
    card.set_margin_top(16)
    card.set_margin_bottom(16)
    page.pack_start(card, True, True, 0)
    window.add(page)
    screen = window.get_screen()
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    settings = window.get_settings()
    settings.set_property("gtk-theme-name", "Adwaita")

    def luminance(rgb):
        channels = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return sum(c * weight for c, weight in zip(channels, (0.2126, 0.7152, 0.0722)))

    try:
        for dark in (False, True, False):
            settings.set_property("gtk-application-prefer-dark-theme", dark)
            window.show_all()
            # Esperar al siguiente cuadro de la ventana offscreen.
            redraw = GLib.MainLoop()
            GLib.timeout_add(120, redraw.quit)
            redraw.run()
            pixbuf = window.get_pixbuf()
            pixels = pixbuf.get_pixels()
            foreground = label.get_style_context().get_color(Gtk.StateFlags.NORMAL)
            text = luminance((foreground.red, foreground.green, foreground.blue))
            for x, y in ((4, 40), (30, 50)):
                offset = y * pixbuf.get_rowstride() + x * pixbuf.get_n_channels()
                background = luminance([c / 255 for c in pixels[offset:offset + 3]])
                assert (background < 0.25) == dark, (dark, x, y, background)
                assert (max(text, background) + 0.05) / (min(text, background) + 0.05) >= 4.5
    finally:
        window.destroy()
        Gtk.StyleContext.remove_provider_for_screen(screen, provider)

    print("✔ tema GTK: contraste del fondo y las tarjetas al alternar claro y oscuro")
