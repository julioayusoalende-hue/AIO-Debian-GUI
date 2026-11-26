"""Aplica las elecciones guardadas por el wizard de onboarding de AyusOS.

Se ejecuta como root desde ayusos-aio-inicial, después del wizard y antes del
mantenimiento programado. Es idempotente y tolerante: un paso fallido no impide
que el resto de opciones se apliquen.
"""

import argparse
import json
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path

from .ayusos_config import APP_PROFILES, SYSTEM_DEFAULTS

HELPER = "/usr/lib/aio-debian-gui/aio-debian-gui-helper"
SCHEDULER = "/usr/lib/aio-debian-gui/aio_core/scheduler.py"
AptEnv = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive"}


def _merge(base, override):
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_preferences(username):
    home = Path(pwd.getpwnam(username).pw_dir)
    path = home / ".config" / "aio-debian-gui" / "preferences.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return _merge(SYSTEM_DEFAULTS, data) if isinstance(data, dict) else dict(SYSTEM_DEFAULTS)


def run(cmd, *, env=None, timeout=900, capture=True):
    return subprocess.run(
        cmd, env=env or AptEnv, text=True, capture_output=capture, timeout=timeout
    )


def helper(steps, uid):
    env = dict(AptEnv, PKEXEC_UID=str(uid))
    return run([HELPER, "--lang", "es", *steps], env=env)


def apply_repos(config, uid, dry):
    if config["repos"]["contrib_nonfree"]:
        return helper(["repos"], uid)
    return None


def apply_flatpak(config, uid, dry):
    if config["flatpak"]["enabled"]:
        return helper(["flatpak-setup"], uid)
    return None


def apply_kernel(config, uid, dry):
    variant = config["kernel"]["variant"]
    if variant == "backports":
        return helper(["backports-kernel-mesa"], uid)
    if variant == "hwe":
        return helper(["ubuntu-hwe"], uid)
    return None


def apply_nvidia(config, uid, dry):
    if config["nvidia"]["mode"] in ("auto", "manual"):
        return helper(["nvidia-driver"], uid)
    return None


def apply_apps(config, uid, dry):
    profile = config["apps"]["profile"]
    packages = APP_PROFILES.get(profile, [])
    if not packages:
        return None
    available, skipped = [], []
    for package in packages:
        if run(["apt-cache", "show", package], timeout=30).returncode == 0:
            available.append(package)
        else:
            skipped.append(package)
    if skipped:
        print(f"  Aplicaciones no disponibles en APT (se omiten): {', '.join(skipped)}")
    if not available:
        return None
    return run(["apt-get", "install", "-y", "--no-remove", *available])


def apply_extensions(config, uid, dry):
    allowed = {
        "gnome-ext-appindicator", "gnome-ext-blur-shell", "gnome-ext-dash-to-dock",
        "gnome-ext-caffeine", "gnome-ext-tiling-shell",
        "gnome-ext-clipboard-indicator", "gnome-ext-places-status",
    }
    steps = [item for item in config["gnome_extensions"]["enabled_by_default"] if item in allowed]
    return helper(steps, uid) if steps else None


def apply_maintenance(config, uid, dry):
    schedule = config["maintenance"]["schedule"]
    hour, minute = 3, 0
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", config["maintenance"]["time"])
    if match:
        hour, minute = map(int, match.groups())
    scheduler_config = {
        "enabled": schedule != "disabled",
        "frequency": schedule if schedule in ("daily", "weekly", "monthly") else "weekly",
        "weekday": 6,
        "hour": hour,
        "minute": minute,
        "tasks": config["maintenance"]["tasks"],
        "launcher": {"format": "deb", "path": ""},
    }
    payload = json.dumps(scheduler_config, separators=(",", ":"))
    return run(["/usr/bin/python3", "-I", SCHEDULER, "--configure", str(uid), payload])


def apply_appearance(config, username, uid, dry):
    appearance = config["appearance"]
    theme = appearance["theme"]
    if theme not in ("system", "light", "dark"):
        return None
    home = Path(pwd.getpwnam(username).pw_dir)
    runtime = Path(f"/run/user/{uid}")
    env = {
        **os.environ,
        "HOME": str(home),
        "USER": username,
        "LOGNAME": username,
        "XDG_RUNTIME_DIR": str(runtime),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus",
        "LANG": "es_ES.UTF-8",
    }

    def gsettings(*args):
        return run(["runuser", "-u", username, "--", "gsettings", "set", *args], env=env)

    scheme = "prefer-dark" if theme == "dark" else "default"
    result = gsettings("org.gnome.desktop.interface", "color-scheme", scheme)

    accent = {"ayusos": "green"}.get(appearance["accent"], appearance["accent"])
    if accent in ("blue", "green", "orange", "purple", "red", "teal"):
        gsettings("org.gnome.desktop.interface", "accent-color", accent)

    wallpaper_mode = appearance["wallpaper_mode"]
    light = Path("/usr/share/backgrounds/ayusos/ayusos-claro.jpg")
    dark = Path("/usr/share/backgrounds/ayusos/ayusos-oscuro.jpg")
    if wallpaper_mode in ("auto", "light", "dark"):
        if light.is_file():
            gsettings("org.gnome.desktop.background", "picture-uri", f"file://{light}")
        if dark.is_file():
            gsettings("org.gnome.desktop.background", "picture-uri-dark", f"file://{dark}")
    return result


def apply(config, username, uid, dry=False):
    print(f"Aplicando onboarding para {username} (uid={uid})")
    steps = [
        ("repositorios", lambda: apply_repos(config, uid, dry)),
        ("flatpak", lambda: apply_flatpak(config, uid, dry)),
        ("kernel", lambda: apply_kernel(config, uid, dry)),
        ("nvidia", lambda: apply_nvidia(config, uid, dry)),
        ("aplicaciones", lambda: apply_apps(config, uid, dry)),
        ("extensiones GNOME", lambda: apply_extensions(config, uid, dry)),
        ("mantenimiento", lambda: apply_maintenance(config, uid, dry)),
        ("apariencia", lambda: apply_appearance(config, username, uid, dry)),
    ]
    failures = []
    for name, callback in steps:
        print(f"[{name}]")
        try:
            result = callback()
            if result is not None and result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()[-800:]
                print(f"  Aviso: {detail}")
                failures.append(name)
            else:
                print("  OK")
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  Aviso: {exc}")
            failures.append(name)
    if failures:
        print(f"Onboarding aplicado con avisos: {', '.join(failures)}")
    else:
        print("Onboarding aplicado correctamente")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Aplica preferencias del onboarding AyusOS")
    parser.add_argument("--user", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        entry = pwd.getpwnam(args.user)
    except KeyError:
        print(f"Usuario no encontrado: {args.user}", file=sys.stderr)
        return 1
    config = load_preferences(args.user)
    if args.dry_run:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0
    return apply(config, args.user, entry.pw_uid)


if __name__ == "__main__":
    sys.exit(main())
