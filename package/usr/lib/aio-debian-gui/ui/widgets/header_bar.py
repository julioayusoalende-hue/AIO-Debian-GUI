"""Header bar widget for AIO Debian GUI."""

import os
import re
from gi.repository import Gtk, Gdk

from aio_core import (
    TRADUCCIONES, version_numerica, obtener_release_actualizacion,
    version_app, formato_actualizacion, novedades_version,
    logo_distribucion, identidad_distribucion, imagen_logo_distribucion, traducir
)


class HeaderBar(Gtk.HeaderBar):
    """Custom header bar with title, version, menu and terminal button."""

    def __init__(self, window, datos_anfitrion, preferencias, callbacks):
        super().__init__()
        self.window = window
        self.datos_anfitrion = datos_anfitrion
        self.preferencias = preferencias
        self.callbacks = callbacks

        self.set_show_close_button(True)
        self.set_custom_title(self._build_title())

        self.btn_menu = Gtk.MenuButton()
        self.btn_menu.add(Gtk.Image.new_from_icon_name(
            "open-menu-symbolic", Gtk.IconSize.BUTTON))
        self.btn_menu.set_tooltip_text(traducir("Menú de preferencias"))
        popover, menu = self._create_menu()
        self.btn_menu.set_popover(popover)
        self.pack_start(self.btn_menu)

        self.btn_terminal = Gtk.Button()
        self.btn_terminal.set_image(Gtk.Image.new_from_icon_name(
            "utilities-terminal-symbolic", Gtk.IconSize.BUTTON))
        self.btn_terminal.set_always_show_image(True)
        self.btn_terminal.set_tooltip_text(traducir("Terminal"))
        self.btn_terminal.connect("clicked", self.callbacks.get("on_terminal", lambda *_: None))
        self.pack_start(self.btn_terminal)

    def _create_menu(self):
        popover = Gtk.Popover.new(self.btn_menu)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu.set_border_width(8)
        popover.add(menu)

        btn_prefs = Gtk.Button(label=traducir("Preferencias"))
        btn_prefs.connect("clicked", self.callbacks.get("on_preferences", lambda *_: None))
        menu.pack_start(btn_prefs, False, False, 0)

        btn_history = Gtk.Button(label=traducir("Historial de mantenimiento"))
        btn_history.connect("clicked", self.callbacks.get("on_history", lambda *_: None))
        menu.pack_start(btn_history, False, False, 0)

        btn_schedule = Gtk.Button(label=traducir("Programar mantenimiento"))
        btn_schedule.connect("clicked", self.callbacks.get("on_schedule", lambda *_: None))
        menu.pack_start(btn_schedule, False, False, 0)

        fmt = formato_actualizacion()
        if fmt in ("flatpak", "appimage"):
            btn_guide = Gtk.Button(label=traducir("Guía de integración del anfitrión"))
            btn_guide.connect("clicked", self.callbacks.get("on_host_guide", lambda *_: None))
            menu.pack_start(btn_guide, False, False, 0)

        btn_update = Gtk.Button(label=traducir("Buscar actualizaciones"))
        btn_update.set_tooltip_text(traducir("Actualizar esta aplicación"))
        btn_update.connect("clicked", self.callbacks.get("on_update", lambda *_: None))
        menu.pack_start(btn_update, False, False, 0)

        btn_about = Gtk.Button(label=traducir("Acerca de AiO Debian"))
        btn_about.connect("clicked", self.callbacks.get("on_about", lambda *_: None))
        menu.pack_start(btn_about, False, False, 0)

        menu.show_all()
        return popover, menu

    def _build_title(self):
        titulo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                         valign=Gtk.Align.CENTER, margin_top=3, margin_bottom=3)

        principal = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        nombre = Gtk.Label(label="AiO Debian")
        nombre.get_style_context().add_class("aio-header-title")
        principal.pack_start(nombre, False, False, 0)

        principal.pack_start(self._version_button(), False, False, 0)

        self.channel_label = Gtk.Label(label="")
        self.channel_label.get_style_context().add_class("dim-label")
        self._update_channel_label()
        principal.pack_start(self.channel_label, False, False, 0)

        titulo.pack_start(principal, False, False, 0)

        sistema = Gtk.Box(spacing=5, halign=Gtk.Align.CENTER)
        distribucion = identidad_distribucion(self.datos_anfitrion)
        nombre_sistema = {"debian": "Debian", "ubuntu": "Ubuntu", "ayusos": "AyusOS Linux"}.get(
            distribucion, traducir("Sistema no compatible"))

        logo = imagen_logo_distribucion(self.datos_anfitrion, 16)
        if logo is not None:
            sistema.pack_start(logo, False, False, 0)

        version_sistema = self.datos_anfitrion.get("VERSION_ID")
        if distribucion == "ayusos" and self.datos_anfitrion.get("ID") == "debian":
            descripcion = self.datos_anfitrion.get("PRETTY_NAME", "")
            version_ayusos = re.match(r"AyusOS(?: Linux)?\s+(\d+(?:\.\d+)*)\b",
                                      descripcion, re.IGNORECASE)
            version_sistema = version_ayusos.group(1) if version_ayusos else None

        if distribucion in ("debian", "ubuntu", "ayusos") and version_sistema:
            nombre_sistema = f"{nombre_sistema} {version_sistema}"

        etiqueta_sistema = Gtk.Label(label=nombre_sistema)
        etiqueta_sistema.get_style_context().add_class("aio-header-system")
        sistema.pack_start(etiqueta_sistema, False, False, 0)
        titulo.pack_start(sistema, False, False, 0)

        return titulo

    def _version_button(self):
        version = version_app()
        base = re.split(r"[~-]", version, maxsplit=1)[0]
        texto = version if version_numerica(base) else traducir("Desarrollo")
        boton = Gtk.Button()
        boton.set_relief(Gtk.ReliefStyle.NONE)
        encabezado = traducir("Novedades de esta versión")
        boton.set_tooltip_text(encabezado)
        boton.get_accessible().set_name(f"{encabezado} · {texto}")
        numero = Gtk.Label(label=texto)
        numero.get_style_context().add_class("aio-header-version")
        boton.get_style_context().add_class("aio-header-version-button")
        boton.add(numero)
        boton.connect("clicked", self._on_version_clicked, version)
        return boton

    def _on_version_clicked(self, _boton, version):
        dialogo = Gtk.Dialog(title=traducir("Novedades de esta versión"),
                             transient_for=self.window, modal=True)
        dialogo.add_button(traducir("Cerrar"), Gtk.ResponseType.CLOSE)
        dialogo.connect("response", lambda d, _r: d.destroy())

        ventana = self.window.get_window()
        monitor = self.window.get_display().get_monitor_at_window(ventana) if ventana else None
        area = monitor.get_workarea() if monitor else None
        ancho = min(820, area.width * 9 // 10) if area else 820
        alto = min(560, area.height * 9 // 10) if area else 560
        dialogo.set_default_size(ancho, alto)

        notas = novedades_version(version) or traducir("No hay notas para esta versión.")
        detalle = Gtk.TextView(editable=False, cursor_visible=False)
        detalle.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        detalle.set_left_margin(16)
        detalle.set_right_margin(16)
        detalle.set_top_margin(12)
        detalle.set_bottom_margin(12)
        detalle.set_pixels_below_lines(5)
        detalle.get_buffer().set_text(notas)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.add(detalle)
        contenido = dialogo.get_content_area()
        contenido.set_border_width(12)
        contenido.pack_start(scroll, True, True, 0)
        dialogo.show_all()

    def _update_channel_label(self):
        canal = self.preferencias.get("canal_actualizaciones", "stable")
        texto = traducir("Testing" if canal == "testing" else "Estable")
        self.channel_label.set_text(texto if formato_actualizacion() == "deb" else "")

    def update_preferences(self, preferencias):
        self.preferencias = preferencias
        self._update_channel_label()