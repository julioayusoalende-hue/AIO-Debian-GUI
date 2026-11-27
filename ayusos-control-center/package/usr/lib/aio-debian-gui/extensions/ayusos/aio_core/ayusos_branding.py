"""Branding y apariencia de AyusOS: temas, acentos, fondos, plymouth."""

import configparser
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from aio_core.constants import comando_host

from ..branding import es_ayusos
from .ayusos_config import AYUSOS_ACCENT, VALID_THEMES, get_effective_config

THEMES_DIR = Path("/usr/share/themes")
AYUSOS_THEME_DIR = Path("/usr/share/themes/AyusOS")
WALLPAPERS_DIR = Path("/usr/share/backgrounds/ayusos")
PLYMOUTH_DIR = Path("/usr/share/plymouth/themes")
PLYMOUTH_CONF = Path("/etc/plymouth/plymouthd.conf")


ACENTOS = {
    "ayusos": {"gtk": "#e74c3c", "shell": "#e74c3c", "name": "AyusOS Rojo"},
    "blue": {"gtk": "#3584e4", "shell": "#3584e4", "name": "Azul"},
    "green": {"gtk": "#279457", "shell": "#279457", "name": "Verde"},
    "orange": {"gtk": "#e67e22", "shell": "#e67e22", "name": "Naranja"},
    "purple": {"gtk": "#8e44ad", "shell": "#8e44ad", "name": "Púrpura"},
    "red": {"gtk": "#e74c3c", "shell": "#e74c3c", "name": "Rojo"},
    "teal": {"gtk": "#16a085", "shell": "#16a085", "name": "Verde Azulado"},
}


def get_available_wallpapers() -> list[dict[str, str]]:
    """Lista fondos de pantalla disponibles."""
    walls = []
    if WALLPAPERS_DIR.exists():
        for f in sorted(WALLPAPERS_DIR.glob("*.jpg")) + sorted(WALLPAPERS_DIR.glob("*.png")):
            name = f.stem.replace("ayusos-", "").replace("-", " ").title()
            walls.append({"id": f.stem, "name": name, "path": str(f)})
    return walls


def get_current_wallpaper() -> str | None:
    """Fondo actual del usuario (GNOME)."""
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"],
            capture_output=True, text=True, timeout=5
        )
        uri = result.stdout.strip().strip("'")
        if uri.startswith("file://"):
            return uri[7:]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def set_wallpaper(path: str, mode: str = "both") -> bool:
    """Establece fondo de pantalla. mode: light, dark, both."""
    try:
        uri = f"file://{path}"
        if mode in ("light", "both"):
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
                check=True, timeout=5
            )
        if mode in ("dark", "both"):
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
                check=True, timeout=5
            )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def set_theme_variant(variant: str) -> bool:
    """Establece variante de tema GTK: light, dark, system."""
    if variant not in VALID_THEMES:
        return False
    scheme = {"system": "default", "light": "prefer-light", "dark": "prefer-dark"}[variant]
    return _set_interface_setting("color-scheme", scheme)


def _set_interface_setting(key: str, value: str) -> bool:
    try:
        subprocess.run(
            comando_host("gsettings", "set", "org.gnome.desktop.interface", key, value),
            check=True, timeout=5,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def set_accent_color(accent_id: str) -> bool:
    """Aplica el acento de GNOME en la sesión actual."""
    if accent_id not in ACENTOS:
        return False
    return _set_interface_setting("accent-color", AYUSOS_ACCENT if accent_id == "ayusos" else accent_id)


def available_plymouth_themes() -> list[str]:
    themes = []
    for descriptor in PLYMOUTH_DIR.glob("*/*.plymouth"):
        name = descriptor.parent.name
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) and descriptor.stem == name and descriptor.is_file():
            themes.append(name)
    return sorted(themes)


def get_plymouth_theme() -> str | None:
    try:
        result = subprocess.run(
            comando_host("/usr/sbin/plymouth-set-default-theme"),
            capture_output=True, text=True, timeout=5, check=True,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _write_plymouth_config(contents: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=PLYMOUTH_CONF.parent,
                                     prefix=".plymouth-", delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(contents)
            stream.close()
            temp.chmod(0o644)
            temp.replace(PLYMOUTH_CONF)
        finally:
            temp.unlink(missing_ok=True)


def set_plymouth_theme(theme: str = "ayusos") -> bool:
    """Cambia el tema instalado y comprueba la regeneración del initramfs."""
    if os.geteuid() != 0 or theme not in available_plymouth_themes():
        return False
    try:
        previous = PLYMOUTH_CONF.read_text()
    except FileNotFoundError:
        previous = None
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read_string(previous or "")
    if not config.has_section("Daemon"):
        config.add_section("Daemon")
    config.set("Daemon", "Theme", theme)
    from io import StringIO
    contents = StringIO()
    config.write(contents, space_around_delimiters=False)
    PLYMOUTH_CONF.parent.mkdir(parents=True, exist_ok=True)
    _write_plymouth_config(contents.getvalue())
    try:
        subprocess.run(["/usr/sbin/update-initramfs", "-u"], check=True, timeout=300,
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        if previous is None:
            PLYMOUTH_CONF.unlink(missing_ok=True)
        else:
            _write_plymouth_config(previous)
        raise
    return True


def apply_full_branding(theme=None, accent=None) -> bool:
    """Aplica branding completo según config."""
    if not es_ayusos():
        return False

    config = get_effective_config()

    theme = theme or config.appearance.theme
    accent = accent or config.appearance.accent
    if not set_theme_variant(theme) or not set_accent_color(accent):
        return False

    walls = get_available_wallpapers()
    mode = config.appearance.wallpaper_mode
    light = next((w["path"] for w in walls if w["id"] == "ayusos-claro"), None)
    dark = next((w["path"] for w in walls if w["id"] == "ayusos-oscuro"), None)
    if mode == "light":
        return not light or set_wallpaper(light, "both")
    if mode == "dark":
        return not dark or set_wallpaper(dark, "both")
    if mode == "auto":
        return (not light or set_wallpaper(light, "light")) and (not dark or set_wallpaper(dark, "dark"))
    return True


def _get_interface_setting(key: str) -> str:
    try:
        result = subprocess.run(
            comando_host("gsettings", "get", "org.gnome.desktop.interface", key),
            capture_output=True, text=True, check=True, timeout=5,
        )
        return result.stdout.strip().strip("'")
    except (OSError, subprocess.SubprocessError):
        return ""


def get_branding_status() -> dict:
    """Estado actual de branding para UI."""
    config = get_effective_config()
    theme = {"prefer-dark": "dark", "prefer-light": "light", "default": "system"}.get(
        _get_interface_setting("color-scheme"), config.appearance.theme,
    )
    accent = _get_interface_setting("accent-color")
    if accent == AYUSOS_ACCENT:
        accent = "ayusos"
    if accent not in ACENTOS:
        accent = config.appearance.accent
    return {
        "theme": theme,
        "accent": accent,
        "accent_name": ACENTOS.get(accent, {}).get("name", accent),
        "wallpaper_mode": config.appearance.wallpaper_mode,
        "current_wallpaper": get_current_wallpaper(),
        "available_wallpapers": get_available_wallpapers(),
        "plymouth_theme": get_plymouth_theme(),
        "available_accents": [{"id": k, "name": v["name"], "color": v["gtk"]} for k, v in ACENTOS.items()],
    }


# CLI para helper
def cli_branding_status() -> str:
    return json.dumps(get_branding_status())


def cli_set_theme(variant: str) -> str:
    ok = set_theme_variant(variant)
    return json.dumps({"success": ok})


def cli_set_accent(accent_id: str) -> str:
    ok = set_accent_color(accent_id)
    return json.dumps({"success": ok})


def cli_set_wallpaper(path: str, mode: str = "both") -> str:
    ok = set_wallpaper(path, mode)
    return json.dumps({"success": ok})


def cli_apply_all(theme=None, accent=None) -> str:
    ok = apply_full_branding(theme, accent)
    return json.dumps({"success": ok})


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: ayusos_branding.py status|theme|accent|wallpaper|apply", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "status":
        print(cli_branding_status())
    elif cmd == "theme":
        if len(sys.argv) < 3:
            print("Falta variante", file=sys.stderr)
            sys.exit(1)
        print(cli_set_theme(sys.argv[2]))
    elif cmd == "accent":
        if len(sys.argv) < 3:
            print("Falta acento", file=sys.stderr)
            sys.exit(1)
        print(cli_set_accent(sys.argv[2]))
    elif cmd == "wallpaper":
        if len(sys.argv) < 3:
            print("Falta ruta", file=sys.stderr)
            sys.exit(1)
        mode = sys.argv[3] if len(sys.argv) > 3 else "both"
        print(cli_set_wallpaper(sys.argv[2], mode))
    elif cmd == "apply":
        print(cli_apply_all())
    else:
        print(f"Comando desconocido: {cmd}", file=sys.stderr)
        sys.exit(1)
