"""Identidad visual y detección de AyusOS para la extensión."""

import re
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk

from aio_core.constants import datos_distribucion_anfitrion, traducir
from .aio_core.ayusos_config import get_effective_config

LOGO = Path("/usr/share/ayusos-control-center/ayusos-logo.png")
NOMBRE_AYUSOS = re.compile(r"^AyusOS(?: Linux)?\b", re.IGNORECASE)


def es_ayusos() -> bool:
    datos = datos_distribucion_anfitrion()
    return (
        datos.get("ID") in ("ayusos", "debian")
        and (
            any(NOMBRE_AYUSOS.match(datos.get(c, "")) for c in ("NAME", "PRETTY_NAME"))
            or datos.get("LOGO") in ("ayusos", "ayusos-logo")
        )
    )


def get_ayusos_version() -> str:
    for path in (Path("/etc/ayusos-release"), Path("/usr/lib/ayusos/version")):
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        match = re.search(r'^AYUSOS_VERSION=["\']?([^"\'\n]+)', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        match = re.search(r"AyusOS(?: Linux)?\s+([0-9]+(?:\.[0-9]+)*)", content, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def get_ayusos_codename() -> str:
    return datos_distribucion_anfitrion().get("VERSION_CODENAME", "trixie")


def logo_cabecera(tamano: int = 48):
    if not LOGO.is_file():
        return None
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(LOGO), tamano, tamano, True)
    except GLib.Error:
        return None
    image = Gtk.Image.new_from_pixbuf(pixbuf)
    image.get_accessible().set_name(traducir("Logotipo de AyusOS Linux"))
    image.set_tooltip_text(traducir("Logotipo de AyusOS Linux"))
    return image


def color_acento_ayusos() -> str:
    if not es_ayusos():
        return "#279457"
    colores = {
        "ayusos": "#279457", "blue": "#3584e4", "green": "#279457",
        "orange": "#e67e22", "purple": "#8e44ad", "red": "#e74c3c",
        "teal": "#16a085",
    }
    return colores.get(get_effective_config().appearance.accent, "#279457")


def titulo_aplicacion() -> str:
    return traducir("Centro de Control de AyusOS") if es_ayusos() else "AiO Debian"


def icono_aplicacion() -> str:
    return "ayusos-control-center" if es_ayusos() else "aio-debian-gui"
