"""Diagnósticos específicos de AyusOS: salud del sistema, snapshots, repos, etc."""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

from .ayusos_config import get_effective_config
from aio_core.constants import comando_host, paquete_instalado, leer_texto
from ..branding import es_ayusos
from aio_core.diagnostics import run_diagnostics as core_diagnostico


def check_ayusos_repos() -> Tuple[bool, str]:
    """Verifica repositorio AyusOS configurado y firmado."""
    sources = Path("/etc/apt/sources.list.d/ayusos.sources")
    keyring = Path("/usr/share/keyrings/ayusos-archive.gpg")

    if not sources.exists():
        return False, "Falta /etc/apt/sources.list.d/ayusos.sources"
    if not keyring.exists():
        return False, "Falta llave /usr/share/keyrings/ayusos-archive.gpg"

    # Verificar que la fuente apunta al repo correcto
    content = sources.read_text()
    if "ayusos" not in content.lower():
        return False, "Fuente APT no parece ser de AyusOS"

    return True, "Repositorio AyusOS configurado correctamente"


def check_ayusos_keyring() -> Tuple[bool, str]:
    """Verifica llave GPG del repo AyusOS."""
    keyring = Path("/usr/share/keyrings/ayusos-archive.gpg")
    if not keyring.exists():
        return False, "Llave no encontrada"
    try:
        result = subprocess.run(
            ["gpg", "--show-keys", "--with-colons", str(keyring)],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and "pub" in result.stdout:
            return True, "Llave GPG válida"
    except (OSError, subprocess.SubprocessError):
        pass
    return False, "Llave GPG inválida o corrupta"


def check_btrfs_health() -> Tuple[bool, str]:
    """Verifica salud de Btrfs (si es root)."""
    if not Path("/").exists():
        return False, "No se puede acceder a /"
    try:
        # Verificar que es btrfs
        result = subprocess.run(
            comando_host("findmnt", "-no", "FSTYPE", "/"),
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip() != "btrfs":
            return True, "No es Btrfs (sistema de archivos diferente)"

        # btrfs filesystem usage
        result = subprocess.run(
            comando_host("btrfs", "filesystem", "usage", "/"),
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False, f"btrfs filesystem usage falló: {result.stderr}"

        # Verificar espacio libre
        for line in result.stdout.split("\n"):
            if "Free" in line and "GB" in line:
                return True, f"Btrfs OK: {line.strip()}"

        return True, "Btrfs montado correctamente"
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"Error comprobando Btrfs: {e}"


def check_timeshift_config() -> Tuple[bool, str]:
    """Verifica configuración de Timeshift."""
    if not paquete_instalado("timeshift"):
        return False, "Timeshift no instalado"

    config_file = Path("/etc/timeshift/timeshift.json")
    if not config_file.exists():
        return False, "Falta /etc/timeshift.json"

    try:
        import json
        config = json.loads(config_file.read_text())
        required = ["backup_device_uuid", "snapshot_type"]
        for key in required:
            if key not in config:
                return False, f"Config Timeshift incompleta: falta {key}"
        return True, "Timeshift configurado correctamente"
    except (OSError, json.JSONDecodeError) as e:
        return False, f"Error leyendo config Timeshift: {e}"


def check_grub_btrfs() -> Tuple[bool, str]:
    """Verifica grub-btrfsd activo."""
    try:
        result = subprocess.run(
            comando_host("systemctl", "is-active", "grub-btrfsd"),
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and "active" in result.stdout:
            return True, "grub-btrfsd activo"
        return False, "grub-btrfsd no activo"
    except (OSError, subprocess.SubprocessError):
        return False, "Error consultando grub-btrfsd"


def check_ayusos_packages() -> Tuple[bool, str]:
    """Verifica paquetes esenciales de AyusOS instalados."""
    essential = [
        "ayusos-release", "ayusos-branding", "aio-debian-gui",
        "timeshift", "google-chrome-stable", "gnome-terminal",
        "grub-btrfsd", "btrfs-progs",
    ]
    missing = []
    for pkg in essential:
        if not paquete_instalado(pkg):
            missing.append(pkg)
    if missing:
        return False, f"Paquetes faltantes: {', '.join(missing)}"
    return True, "Todos los paquetes esenciales instalados"


def check_snapshots_recent() -> Tuple[bool, str]:
    """Verifica que hay snapshots recientes (últimos 7 días)."""
    if not paquete_instalado("timeshift"):
        return True, "Timeshift no instalado (omitido)"

    try:
        result = subprocess.run(
            comando_host("timeshift", "--list", "--json"),
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False, "Error listando snapshots"

        import json
        snapshots = json.loads(result.stdout)
        if not snapshots:
            return False, "No hay snapshots creados"

        # Verificar si hay alguno en los últimos 7 días
        now = time.time()
        recent = False
        for snap in snapshots:
            # timeshift JSON tiene "date" en formato ISO
            snap_date = snap.get("date", "")
            if snap_date:
                try:
                    snap_time = time.mktime(time.strptime(snap_date[:19], "%Y-%m-%d %H:%M:%S"))
                    if now - snap_time < 7 * 86400:
                        recent = True
                        break
                except ValueError:
                    pass

        if recent:
            return True, f"Snapshots recientes encontrados ({len(snapshots)} total)"
        return False, f"Sin snapshots en 7 días ({len(snapshots)} total)"
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        return False, f"Error: {e}"


def check_firmware_updates() -> Tuple[bool, str]:
    """Verifica actualizaciones de firmware (fwupd)."""
    if not paquete_instalado("fwupd"):
        return True, "fwupd no instalado (omitido)"
    try:
        result = subprocess.run(
            comando_host("fwupdmgr", "get-updates", "--json"),
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            updates = data.get("Devices", [])
            if updates:
                return True, f"{len(updates)} actualizaciones de firmware disponibles"
            return True, "Firmware al día"
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return True, "No se pudo comprobar firmware"


def check_flatpak_flathub() -> Tuple[bool, str]:
    """Verifica Flatpak y Flathub configurados."""
    if not paquete_instalado("flatpak"):
        return False, "Flatpak no instalado"
    try:
        result = subprocess.run(
            ["flatpak", "remotes", "--show-details", "flathub"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and "flathub" in result.stdout:
            return True, "Flathub configurado"
        return False, "Flathub no configurado"
    except (OSError, subprocess.SubprocessError):
        return False, "Error consultando Flatpak"


def run_full_diagnostics() -> Dict:
    """Ejecuta todos los diagnósticos y devuelve reporte completo."""
    checks = [
        ("core", core_diagnostico),
        ("ayusos_repos", check_ayusos_repos),
        ("ayusos_keyring", check_ayusos_keyring),
        ("btrfs_health", check_btrfs_health),
        ("timeshift_config", check_timeshift_config),
        ("grub_btrfs", check_grub_btrfs),
        ("ayusos_packages", check_ayusos_packages),
        ("snapshots_recent", check_snapshots_recent),
        ("firmware_updates", check_firmware_updates),
        ("flatpak_flathub", check_flatpak_flathub),
    ]

    results = {}
    for name, check_fn in checks:
        try:
            if name == "core":
                findings = check_fn()
                # run_diagnostics returns list of findings; consider OK if no "fail" status
                ok = all(f.get("status") != "fail" for f in findings)
                details = findings
                results[name] = {"ok": ok, "details": details}
            else:
                ok, msg = check_fn()
                results[name] = {"ok": ok, "message": msg}
        except Exception as e:
            results[name] = {"ok": False, "message": f"Excepción: {e}"}

    # Resumen
    total = len(results)
    passed = sum(1 for r in results.values() if r.get("ok"))
    results["_summary"] = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "score": f"{passed}/{total}",
    }

    return results


# CLI para helper
def cli_diagnostics() -> str:
    return json.dumps(run_full_diagnostics(), indent=2)


if __name__ == "__main__":
    import sys
    print(cli_diagnostics())