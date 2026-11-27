"""Branding y apariencia de AyusOS: temas, acentos, fondos, plymouth."""

import json
import subprocess
from pathlib import Path

from aio_core.constants import comando_host
from aio_core.gtk_appearance import aplicar_tema

from ..branding import es_ayusos
from .ayusos_config import VALID_THEMES, get_effective_config

THEMES_DIR = Path("/usr/share/themes")
AYUSOS_THEME_DIR = Path("/usr/share/themes/AyusOS")
WALLPAPERS_DIR = Path("/usr/share/backgrounds/ayusos")
PLYMOUTH_DIR = Path("/usr/share/plymouth/themes/ayusos")
DCONF_DB_DIR = Path("/etc/dconf/db/local.d")
DCONF_USER_DIR = Path.home() / ".config" / "dconf"


ACENTOS = {
    "ayusos": {"gtk": "#279457", "shell": "#279457", "name": "AyusOS Verde"},
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
    try:
        if variant == "system" or variant == "dark":
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-dark"],
                check=True, timeout=5
            )
        else:
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "default"],
                check=True, timeout=5
            )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def set_accent_color(accent_id: str) -> bool:
    """Aplica color de acento a tema GTK y Shell."""
    if accent_id not in ACENTOS:
        return False

    config = get_effective_config()
    config.appearance.accent = accent_id

    # Escribir override dconf
    override_path = DCONF_DB_DIR / "99-ayusos-accent"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_content = f"""[org/gnome/desktop/interface]
gtk-theme='AyusOS-{accent_id}'
color-scheme='prefer-dark'

[org/gnome/shell]
theme-variant='dark'
"""
    try:
        override_path.write_text(override_content)
        # Compilar dconf
        subprocess.run(["dconf", "update"], check=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass

    # Aplicar tema GTK via gtK_appearance
    aplicar_tema(config.appearance.theme, accent_id)

    return True


def get_plymouth_theme() -> str | None:
    """Tema Plymouth actual."""
    try:
        result = subprocess.run(
            comando_host("plymouth-set-default-theme"),
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def set_plymouth_theme(theme: str = "ayusos") -> bool:
    """Establece tema Plymouth."""
    if not (PLYMOUTH_DIR / f"{theme}.plymouth").exists():
        theme = "bgrt"  # fallback
    try:
        subprocess.run(
            comando_host("plymouth-set-default-theme", "-R", theme),
            check=True, timeout=10
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def apply_full_branding() -> bool:
    """Aplica branding completo según config."""
    if not es_ayusos():
        return False

    config = get_effective_config()

    # Tema base
    set_theme_variant(config.appearance.theme)

    # Acento
    set_accent_color(config.appearance.accent)

    # Fondos
    walls = get_available_wallpapers()
    if walls:
        # Seleccionar según modo
        mode = config.appearance.wallpaper_mode
        light_walls = [w for w in walls if "claro" in w["id"] or "light" in w["id"]]
        dark_walls = [w for w in walls if "oscuro" in w["id"] or "dark" in w["id"]]
        if mode == "auto":
            # Usar claro/oscuro según tema; en "system" aplica ambos
            if config.appearance.theme == "light" and light_walls:
                set_wallpaper(light_walls[0]["path"], "both")
            elif config.appearance.theme == "dark" and dark_walls:
                set_wallpaper(dark_walls[0]["path"], "both")
            else:
                if light_walls:
                    set_wallpaper(light_walls[0]["path"], "light")
                if dark_walls:
                    set_wallpaper(dark_walls[0]["path"], "dark")
        elif mode == "light" and light_walls:
            set_wallpaper(light_walls[0]["path"], "light")
        elif mode == "dark" and dark_walls:
            set_wallpaper(dark_walls[0]["path"], "dark")

    # Plymouth
    set_plymouth_theme("ayusos")

    return True


def get_branding_status() -> dict:
    """Estado actual de branding para UI."""
    config = get_effective_config()
    return {
        "theme": config.appearance.theme,
        "accent": config.appearance.accent,
        "accent_name": ACENTOS.get(config.appearance.accent, {}).get("name", config.appearance.accent),
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


def cli_apply_all() -> str:
    ok = apply_full_branding()
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
