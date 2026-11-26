"""Actualización de AyusOS: gestión de canales, versiones y migración."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .ayusos_config import get_effective_config
from aio_core.constants import comando_host, leer_texto, paquete_instalado
from aio_core.updates import version_numerica, obtener_release_actualizacion


AYUSOS_RELEASE_PATH = Path("/etc/ayusos-release")
AYUSOS_REPO_SOURCES = Path("/etc/apt/sources.list.d/ayusos.sources")
AYUSOS_KEYRING = Path("/usr/share/keyrings/ayusos-archive.gpg")


def get_current_version() -> str:
    """Versión actual de AyusOS instalada."""
    for path in [AYUSOS_RELEASE_PATH, Path("/usr/lib/ayusos/version")]:
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
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", content):
            return content
    return "0.0.0"


def get_current_channel() -> str:
    """Canal actual: stable o testing."""
    config = get_effective_config()
    # Leer de la fuente APT si existe
    if AYUSOS_REPO_SOURCES.exists():
        content = AYUSOS_REPO_SOURCES.read_text()
        if "testing" in content:
            return "testing"
    return "stable"


def get_available_versions(channel: str) -> List[Dict[str, str]]:
    """Obtiene versiones disponibles desde el repositorio AyusOS."""
    # En producción: consultar API GitHub releases o repo APT
    # Por ahora: simulación
    return []


def check_updates() -> Tuple[bool, Optional[str], Optional[str]]:
    """Comprueba el candidato del repositorio firmado usando índices APT locales."""
    current = get_current_version()
    if os.environ.get("AIO_TEST_AYUSOS_UPDATE"):
        return True, current, "1.5.0"
    if not AYUSOS_REPO_SOURCES.is_file():
        return False, current, None
    try:
        result = subprocess.run(
            ["apt-cache", "policy", "ayusos-release"],
            capture_output=True, text=True, timeout=15,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return False, current, None
    match = re.search(r"^\s*Candidate:\s*(\S+)", result.stdout, re.MULTILINE)
    if result.returncode or not match or match.group(1) == "(none)":
        return False, current, None
    candidate = match.group(1)
    newer = subprocess.run(
        ["dpkg", "--compare-versions", candidate, "gt", current],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    return newer, current, candidate if newer else None


def perform_update(channel: str = None, dry_run: bool = False) -> Tuple[bool, str]:
    """Ejecuta actualización de AyusOS.
    Returns: (exito, mensaje)"""
    if channel is None:
        channel = get_current_channel()

    if channel not in ("stable", "testing"):
        return False, "Canal inválido: use 'stable' o 'testing'"

    # Verificar llave y repo
    if not AYUSOS_KEYRING.exists():
        return False, "Falta llave de verificación del repositorio AyusOS"
    if not AYUSOS_REPO_SOURCES.exists():
        return False, "Falta configuración del repositorio AyusOS"

    if dry_run:
        return True, f"Simulación: actualización a {channel} (no implementado)"

    # TODO: Implementar apt update + apt install ayusos-release + migración
    return False, "Actualización no implementada aún"


def migrate_config(old_version: str, new_version: str) -> bool:
    """Migra configuración entre versiones."""
    # TODO: Implementar migraciones específicas por versión
    return True


def get_changelog(version: str) -> str:
    """Obtiene changelog de una versión."""
    # TODO: Consultar repo o archivo local
    return f"Changelog para {version} no disponible."


# CLI para helper privilegiado
def cli_check_updates() -> str:
    """Salida JSON para el helper."""
    hay, actual, nueva = check_updates()
    return json.dumps({
        "update_available": hay,
        "current_version": actual,
        "new_version": nueva,
        "channel": get_current_channel(),
    })


def cli_update(channel: str, dry_run: bool = False) -> str:
    ok, msg = perform_update(channel, dry_run)
    return json.dumps({"success": ok, "message": msg})


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: ayusos_update.py check|update [channel] [--dry-run]", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "check":
        print(cli_check_updates())
    elif cmd == "update":
        ch = sys.argv[2] if len(sys.argv) > 2 else "stable"
        dry = "--dry-run" in sys.argv
        print(cli_update(ch, dry))
    else:
        print(f"Comando desconocido: {cmd}", file=sys.stderr)
        sys.exit(1)