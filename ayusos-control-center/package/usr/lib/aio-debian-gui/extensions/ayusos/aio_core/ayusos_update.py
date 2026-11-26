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
AYUSOS_PACKAGE = "ayusos-release"
AYUSOS_CONFIG = Path("/etc/ayusos/ayusos.conf")
CHANGELOG_PATHS = (
    Path("/usr/share/doc/ayusos-release/changelog.Debian.gz"),
    Path("/usr/share/doc/ayusos-release/changelog.gz"),
)
APT_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}


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
    """Versiones publicadas en el repositorio firmado para el canal actual."""
    if channel not in ("stable", "testing"):
        raise ValueError("Canal inválido: use 'stable' o 'testing'")
    try:
        result = subprocess.run(
            ["apt-cache", "madison", AYUSOS_PACKAGE],
            capture_output=True, text=True, timeout=15, env=APT_ENV,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    versions = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2 or not re.fullmatch(r"[0-9][0-9A-Za-z.+~:-]*", parts[1]):
            continue
        versions.append({"version": parts[1], "suite": parts[2] if len(parts) > 2 else ""})
    return versions


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


def _apt(command, timeout=120):
    return subprocess.run(
        ["apt-get", *command], capture_output=True, text=True, timeout=timeout,
        env={**APT_ENV, "DEBIAN_FRONTEND": "noninteractive"},
    )


def _apt_failure(result):
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    return detail[-1] if detail else f"apt-get terminó con estado {result.returncode}"


def _snapshot_before_update(candidate: str):
    """Crea un snapshot previo cuando Timeshift está disponible."""
    try:
        from . import ayusos_snapshots
        if not ayusos_snapshots.is_timeshift_installed():
            return True, "Timeshift no está instalado; se omite el snapshot."
        ok, message = ayusos_snapshots.create_timeshift_snapshot(
            f"AiO: actualización de AyusOS a {candidate}", "O")
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return False, f"No se pudo crear el snapshot previo: {exc}"
    if not ok:
        return False, f"No se pudo crear el snapshot previo: {message}"
    return True, "Snapshot previo creado."


def perform_update(channel: str = None, dry_run: bool = False) -> Tuple[bool, str]:
    """Actualiza AyusOS con simulación previa, snapshot y comprobación de reinicio.

    Returns: (exito, mensaje)
    """
    if channel is None:
        channel = get_current_channel()

    if channel not in ("stable", "testing"):
        return False, "Canal inválido: use 'stable' o 'testing'"

    if not AYUSOS_KEYRING.exists():
        return False, "Falta llave de verificación del repositorio AyusOS"
    if not AYUSOS_REPO_SOURCES.exists():
        return False, "Falta configuración del repositorio AyusOS"

    current = get_current_version()
    hay_actualizacion, _, candidate = check_updates()
    if not hay_actualizacion or not candidate:
        return True, f"AyusOS ya está actualizado (versión {current})."

    try:
        actualizar = _apt(["update"], timeout=300)
        if actualizar.returncode:
            return False, f"No se pudieron actualizar los índices APT: {_apt_failure(actualizar)}"

        simulacion = _apt(
            ["-s", "-o", "Debug::NoLocking=1", "install", "--no-remove", AYUSOS_PACKAGE],
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"No se pudo simular la actualización: {exc}"

    if simulacion.returncode:
        return False, f"La simulación de la actualización falló: {_apt_failure(simulacion)}"
    if re.search(r"^(Remv|Purg) ", simulacion.stdout, re.MULTILINE):
        return False, "La actualización propone eliminar paquetes y se ha bloqueado."

    plan = [line for line in simulacion.stdout.splitlines() if line.startswith("Inst ")]
    if dry_run:
        detalle = plan[0] if plan else "sin cambios pendientes"
        return True, f"Simulación correcta para {candidate}: {detalle}"

    snapshot_ok, snapshot_message = _snapshot_before_update(candidate)
    if not snapshot_ok:
        return False, snapshot_message

    try:
        resultado = _apt(
            ["-y", "--no-remove", "-o", "Dpkg::Options::=--force-confdef",
             "-o", "Dpkg::Options::=--force-confold", "install", AYUSOS_PACKAGE],
            timeout=3600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Error ejecutando la actualización: {exc}"

    if resultado.returncode:
        pista = " El snapshot previo permite volver al estado anterior." if snapshot_ok else ""
        return False, f"La actualización falló: {_apt_failure(resultado)}.{pista}"

    migrate_config(current, candidate)
    reinicio = (Path("/var/run/reboot-required").exists()
                or Path("/run/reboot-required").exists())
    mensaje = f"AyusOS actualizado de {current} a {candidate}. {snapshot_message}"
    if reinicio:
        mensaje += " Reinicia el equipo para completar la actualización."
    return True, mensaje


def migrate_config(old_version: str, new_version: str) -> bool:
    """Conserva una copia de la configuración antes de migrarla."""
    if not AYUSOS_CONFIG.is_file():
        return True
    try:
        import shutil
        copia = AYUSOS_CONFIG.with_name(f"{AYUSOS_CONFIG.name}.bak-{old_version}")
        shutil.copy2(AYUSOS_CONFIG, copia)
    except OSError:
        return False
    return True


def get_changelog(version: str) -> str:
    """Notas de versión locales del paquete ayusos-release."""
    import gzip
    for path in CHANGELOG_PATHS:
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8", errors="replace") as stream:
                    return stream.read(65536)
            return path.read_text(encoding="utf-8", errors="replace")[:65536]
        except OSError:
            continue
    return f"No hay notas de versión locales para {version}."


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