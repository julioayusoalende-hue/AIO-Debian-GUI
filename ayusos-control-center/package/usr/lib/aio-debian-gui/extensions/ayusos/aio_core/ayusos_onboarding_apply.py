"""Aplica las elecciones guardadas por el wizard de onboarding de AyusOS.

Se ejecuta como root desde ayusos-aio-inicial, después del wizard y antes del
mantenimiento programado. Es idempotente y tolerante: un paso fallido no impide
que el resto de opciones se apliquen.

Si algún paso requiere reinicio (kernel, NVIDIA, GRUB), se crea el marcador
/var/lib/ayusos/reboot-required y se ofrece reiniciar al usuario.
"""

import argparse
import json
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path

from .ayusos_config import APP_PROFILES, AYUSOS_ACCENT, SYSTEM_DEFAULTS, installed_gnome_tasks

HELPER = "/usr/lib/aio-debian-gui/aio-debian-gui-helper"
SCHEDULER = "/usr/lib/aio-debian-gui/aio_core/scheduler.py"
AptEnv = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive"}
REBOOT_MARKER = Path("/var/lib/ayusos/reboot-required")


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


def helper(steps, uid, *, timeout=900):
    """Ejecuta paso del helper y devuelve (completed_process, reboot_required)."""
    env = dict(AptEnv, PKEXEC_UID=str(uid))
    result = run([HELPER, "--lang", "es", *steps], env=env, timeout=timeout)
    reboot_needed = "##REBOOT:1" in (result.stdout or "") or "##REBOOT:1" in (result.stderr or "")
    return result, reboot_needed


def apply_repos(config, uid, dry):
    if config["repos"]["contrib_nonfree"]:
        return helper(["repos"], uid)
    return None, False


def apply_flatpak(config, uid, dry):
    if config["flatpak"]["enabled"]:
        if config["flatpak"]["flathub"]:
            return helper(["flatpak-setup"], uid)
        return run(["apt-get", "install", "-y", "--no-remove", "flatpak"]), False
    return None, False


def apply_kernel(config, uid, dry):
    variant = config["kernel"]["variant"]
    if variant == "backports":
        return helper(["backports-kernel-mesa"], uid)
    if variant == "hwe":
        return helper(["ubuntu-hwe"], uid)
    return None, False


def notify_nvidia(uid, message):
    runtime = Path(f"/run/user/{uid}")
    if not (runtime / "bus").is_socket():
        return
    try:
        username = pwd.getpwuid(uid).pw_name
        run(["runuser", "-u", username, "--", "env", f"XDG_RUNTIME_DIR={runtime}",
             f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus",
             "notify-send", "Controlador NVIDIA", message], timeout=5)
    except (KeyError, OSError, subprocess.SubprocessError):
        pass


def apply_nvidia(config, uid, dry):
    mode = config["nvidia"]["mode"]
    if dry or config["nvidia"].get("handled_by_wizard") or mode not in ("auto", "manual"):
        return None, False
    report = run([HELPER, "--nvidia-report"], timeout=15)
    if report.returncode:
        return report, False
    flags = (report.stdout or "").splitlines()
    if "##NVIDIA:present:0" in flags and mode == "auto":
        print("  No se detectó una GPU NVIDIA PCI. Se omite la instalación.")
        return None, False
    # DKMS puede tardar varios minutos; el helper conserva su bloqueo hasta terminar.
    print("  Iniciando la instalación del controlador NVIDIA…", flush=True)
    notify_nvidia(uid, "AyusOS está instalando el controlador seleccionado. La compilación puede tardar varios minutos.")
    return helper(["nvidia-driver"], uid, timeout=None)


def apply_apps(config, uid, dry):
    # Compatibilidad con elecciones explícitas de asistentes anteriores.
    if not config["apps"].get("auto_install", False):
        print("  Instalación automática de apps desactivada (auto_install=false)")
        return None, False
    if dry:
        return None, False
    profile = config["apps"]["profile"]
    packages = APP_PROFILES.get(profile, [])
    if not packages:
        return None, False
    available, skipped = [], []
    for package in packages:
        if run(["apt-cache", "show", package], timeout=30).returncode == 0:
            available.append(package)
        else:
            skipped.append(package)
    if skipped:
        print(f"  Aplicaciones no disponibles en APT (se omiten): {', '.join(skipped)}")
    if not available:
        return None, False
    return run(["apt-get", "install", "-y", "--no-remove", *available]), False


def apply_extensions(config, uid, dry):
    allowed = {
        "gnome-ext-appindicator", "gnome-ext-blur-shell", "gnome-ext-dash-to-dock",
        "gnome-ext-caffeine", "gnome-ext-tiling-shell",
        "gnome-ext-clipboard-indicator", "gnome-ext-places-status",
    }
    data_dir = Path(pwd.getpwuid(uid).pw_dir) / ".local/share"
    pending = allowed - installed_gnome_tasks(data_dir)
    steps = [item for item in config["gnome_extensions"]["enabled_by_default"] if item in pending]
    return helper(steps, uid) if steps else (None, False)


def apply_maintenance(config, uid, dry):
    schedule = config["maintenance"]["schedule"]
    hour, minute = 3, 0
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", config["maintenance"]["time"])
    if match:
        hour, minute = map(int, match.groups())
    # Las preferencias de versiones anteriores pueden incluir una tarea
    # que el programador de AiO nunca admitió.
    tasks = [task for task in config["maintenance"]["tasks"] if task != "clean-journal"]
    if schedule == "disabled" and not tasks:
        tasks = ["rebootcheck"]
    scheduler_config = {
        "enabled": schedule != "disabled",
        "frequency": schedule if schedule in ("daily", "weekly", "monthly") else "weekly",
        "weekday": 6,
        "hour": hour,
        "minute": minute,
        "tasks": tasks,
        "launcher": {"format": "deb", "path": ""},
    }
    payload = json.dumps(scheduler_config, separators=(",", ":"))
    return run(["/usr/bin/python3", "-I", SCHEDULER, "--configure", str(uid), payload]), False


def apply_appearance(config, username, uid, dry):
    appearance = config["appearance"]
    theme = appearance["theme"]
    if theme not in ("system", "light", "dark"):
        return None, False
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

    scheme = {"system": "default", "dark": "prefer-dark", "light": "prefer-light"}[theme]
    result = gsettings("org.gnome.desktop.interface", "color-scheme", scheme)

    accent = {"ayusos": AYUSOS_ACCENT}.get(appearance["accent"], appearance["accent"])
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
    return result, False


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
    reboot_needed = False
    for name, callback in steps:
        print(f"[{name}]")
        try:
            result, step_reboot = callback()
            if step_reboot:
                reboot_needed = True
                print("  ⚠ Requiere reinicio del sistema")
            if result is not None and result.returncode != 0:
                detail = "\n".join(
                    output.strip()[-1200:] for output in (result.stdout, result.stderr) if output and output.strip()
                )
                print(f"  Aviso: {detail or f'código de salida {result.returncode}'}", flush=True)
                failures.append(name)
                if name == "nvidia":
                    notify_nvidia(uid, "No se pudo instalar el controlador. Consulta el registro de ayusos-aio-inicial.")
            else:
                print("  OK")
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  Aviso: {exc}")
            failures.append(name)
            if name == "nvidia":
                notify_nvidia(uid, "No se pudo instalar el controlador. Consulta el registro de ayusos-aio-inicial.")

    # Paso final: comprobación de reinicio necesaria
    print("[comprobación de reinicio]")
    try:
        _result, check_reboot = helper(["rebootcheck"], uid)
        if check_reboot:
            reboot_needed = True
            print("  ⚠ Se recomienda reiniciar el sistema")
        else:
            print("  OK")
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  Aviso: {exc}")

    # Marcar reinicio requerido
    if reboot_needed:
        REBOOT_MARKER.parent.mkdir(parents=True, exist_ok=True)
        REBOOT_MARKER.write_text(f"{username}\n")
        print(f"\n⚠ REINICIO REQUERIDO: Se ha creado {REBOOT_MARKER}")
        print("  Los cambios de kernel, NVIDIA o GRUB requieren reinicio para aplicarse.")

    if failures:
        print(f"\nOnboarding aplicado con avisos: {', '.join(failures)}")
        return 1
    print("\nOnboarding aplicado correctamente")
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
    result = apply(config, args.user, entry.pw_uid)
    reboot_boot_id = config["nvidia"].get("reboot_boot_id")
    if result == 0 and config["nvidia"].get("handled_by_wizard") and reboot_boot_id:
        if reboot_boot_id == Path("/proc/sys/kernel/random/boot_id").read_text().strip():
            return 11
    return result


if __name__ == "__main__":
    sys.exit(main())
