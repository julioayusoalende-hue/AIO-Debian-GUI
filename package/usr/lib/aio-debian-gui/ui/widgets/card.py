"""Card widget for AIO Debian GUI."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from aio_core import traducir


class Card(Gtk.Frame):
    """Tarjeta estilo aio-card con título e icono."""

    def __init__(self, title, icon_name, spacing=12):
        super().__init__()
        self.get_style_context().add_class("aio-card")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        content.set_border_width(14)
        self.add(content)

        header = Gtk.Box(spacing=9)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        icon.get_style_context().add_class("aio-icon")
        header.pack_start(icon, False, False, 0)

        title_lbl = Gtk.Label(label=title, xalign=0)
        title_lbl.get_style_context().add_class("aio-heading")
        header.pack_start(title_lbl, True, True, 0)

        content.pack_start(header, False, False, 0)

        self.content_box = content

    def add_widget(self, widget, expand=False, fill=False, padding=0):
        self.content_box.pack_start(widget, expand, fill, padding)

    def get_content_box(self):
        return self.content_box


def create_card(title, icon_name, spacing=12):
    """Factory function que devuelve (frame, content_box)."""
    frame = Gtk.Frame()
    frame.get_style_context().add_class("aio-card")
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    content.set_border_width(14)
    frame.add(content)

    header = Gtk.Box(spacing=9)
    icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
    icon.get_style_context().add_class("aio-icon")
    header.pack_start(icon, False, False, 0)

    title_lbl = Gtk.Label(label=title, xalign=0)
    title_lbl.get_style_context().add_class("aio-heading")
    header.pack_start(title_lbl, True, True, 0)

    content.pack_start(header, False, False, 0)

    return frame, content