"""About dialog."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from aio_core import traducir, version_app, HOMEPAGE


class AboutDialog(Gtk.Dialog):
    """Diálogo Acerca de."""

    def __init__(self, parent):
        super().__init__(title=traducir("Acerca de AiO Debian"), transient_for=parent, modal=True)
        self.add_button(traducir("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(400, 300)

        content = self.get_content_area()
        content.set_spacing(12)
        content.set_border_width(16)

        header = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name("aio-debian-gui", Gtk.IconSize.DIALOG)
        icon.set_pixel_size(64)
        header.pack_start(icon, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        name = Gtk.Label(label="AiO Debian")
        name.get_style_context().add_class("aio-header-title")
        info.pack_start(name, False, False, 0)

        version_lbl = Gtk.Label(label=self.translate("Versión %s") % version_app())
        version_lbl.get_style_context().add_class("aio-header-version")
        info.pack_start(version_lbl, False, False, 0)

        tagline = Gtk.Label(label=self.translate("Tu sistema al día. El control, en tus manos."))
        tagline.get_style_context().add_class("dim-label")
        info.pack_start(tagline, False, False, 0)

        header.pack_start(info, False, False, 0)
        content.pack_start(header, False, False, 0)

        content.pack_start(Gtk.Separator(), False, False, 0)

        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        links = [
            (self.translate("GitHub"), HOMEPAGE),
            (self.translate("Licencia"), "https://www.gnu.org/licenses/gpl-3.0.html"),
        ]

        for label, url in links:
            link_btn = Gtk.LinkButton(uri=url, label=label)
            details.pack_start(link_btn, False, False, 0)

        copyright_lbl = Gtk.Label(label=self.translate("Copyright © 2026 Julio Ayuso"))
        copyright_lbl.get_style_context().add_class("dim-label")
        details.pack_start(copyright_lbl, False, False, 0)

        license_lbl = Gtk.Label(label=self.translate("GNU GPL v3 o posterior"))
        license_lbl.get_style_context().add_class("dim-label")
        details.pack_start(license_lbl, False, False, 0)

        content.pack_start(details, False, False, 0)

        self.show_all()