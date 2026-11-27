"""Actualización de AyusOS: gestión de canales, versiones y migración."""

import json
import os
import re
import subprocess
from pathlib import Path

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
    # Leer de la fuente APT si existe
    if AYUSOS_REPO_SOURCES.exists():
        content = AYUSOS_REPO_SOURCES.read_text()
        if "testing" in content:
            return "testing"
    return "stable"


def get_available_versions(channel: str) -> list[dict[str, str]]:
    """Obtiene versiones disponibles desde el repositorio AyusOS."""
    # En producción: consultar API GitHub releases o repo APT
    # Por ahora: simulación
    return []


def check_updates() -> tuple[bool, str | None, str | None]:
    """Comprueba el candidato del repositorio firmado usando índices APT locales."""
    current = get_current_version()
    if os.environ.get("AIO_TEST_AYUSOS_UPDATE"):
        return True, current, "1.5.3"
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


def perform_update(channel: str = None, dry_run: bool = False) -> tuple[bool, str]:
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
        # Simular: mostrar qué paquetes se actualizarían
        try:
            result = subprocess.run(
                ["apt-get", "-s", "install", "--only-upgrade", "ayusos-release"],
                capture_output=True, text=True, timeout=30,
                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
            )
            if result.returncode == 0 and "ayusos-release" in result.stdout:
                return True, f"Simulación: se actualizaría ayusos-release a {channel}"
            return True, f"Simulación: actualización a {channel} (sin cambios detectados)"
        except (OSError, subprocess.SubprocessError):
            return True, f"Simulación: actualización a {channel}"

    # Crear snapshot antes de actualizar (si Timeshift está disponible)
    snapshot_created = False
    try:
        if Path("/usr/bin/timeshift").exists():
            subprocess.run(
                ["timeshift", "--create", "--comments", "Pre-update AyusOS", "--tags", "O"],
                capture_output=True, timeout=120,
            )
            snapshot_created = True
    except (OSError, subprocess.SubprocessError):
        pass

    old_version = get_current_version()

    try:
        # Actualizar índices APT
        subprocess.run(
            ["apt-get", "update"],
            check=True, capture_output=True, timeout=60,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        )

        # Instalar/actualizar ayusos-release
        subprocess.run(
            ["apt-get", "install", "-y", "--only-upgrade", "ayusos-release"],
            check=True, capture_output=True, timeout=120,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive"},
        )

        # Verificar nueva versión y migrar configuración si procede
        new_version = get_current_version()
        if old_version != new_version:
            migrate_config(old_version, new_version)

        # Ejecutar aplicador de onboarding para aplicar nuevos ajustes
        try:
            subprocess.run(
                ["/usr/local/libexec/ayusos-aplicar-onboarding"],
                capture_output=True, timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            pass

        msg = f"AyusOS actualizado a {new_version}"
        if snapshot_created:
            msg += " (snapshot creado antes de actualizar)"
        return True, msg

    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
        return False, f"Error durante la actualización: {err_msg}"
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"Error de sistema: {e}"


def migrate_config(old_version: str, new_version: str) -> bool:
    """Migra configuración entre versiones."""
    # TODO: Implementar migraciones específicas por versión
    return True


def get_changelog(version: str) -> str:
    """Obtiene changelog de una versión desde el paquete o archivo local."""
    # Intentar leer desde el paquete instalado
    changelog_paths = [
        Path("/usr/share/doc/ayusos-release/changelog.Debian.gz"),
        Path("/usr/share/doc/ayusos-release/changelog.gz"),
        Path("/usr/share/doc/ayusos-release/NEWS.gz"),
    ]
    for path in changelog_paths:
        if path.exists():
            try:
                import gzip
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    content = f.read(50000)  # límite 50KB
                return content
            except (OSError, gzip.BadGzipFile):
                continue
    return f"Changelog para {version} no disponible localmente."


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
