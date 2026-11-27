"""Gestión de snapshots Btrfs + Timeshift + grub-btrfs para AyusOS."""

import json
import re
import subprocess

from aio_core.constants import comando_host, paquete_instalado

from .ayusos_config import get_effective_config

TIMESHIFT_CMD = "timeshift"
GRUB_BTRFS_CMD = "grub-btrfsd"
BTRFS_CMD = "btrfs"


def is_btrfs_root() -> bool:
    """True si / está en Btrfs."""
    try:
        result = subprocess.run(
            comando_host("findmnt", "-no", "FSTYPE", "/"),
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == "btrfs"
    except (OSError, subprocess.SubprocessError):
        return False


def is_timeshift_installed() -> bool:
    return paquete_instalado("timeshift")


def is_grub_btrfs_active() -> bool:
    try:
        result = subprocess.run(
            comando_host("systemctl", "is-active", "grub-btrfsd"),
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0 and "active" in result.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def list_timeshift_snapshots() -> list[dict[str, str]]:
    """Lista snapshots de Timeshift (JSON)."""
    if not is_timeshift_installed():
        return []
    try:
        result = subprocess.run(
            comando_host(TIMESHIFT_CMD, "--list", "--json"),
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return []


def list_btrfs_snapshots(path: str = "/") -> list[dict[str, str]]:
    """Lista subvolúmenes/snapshots Btrfs."""
    if not is_btrfs_root():
        return []
    try:
        result = subprocess.run(
            comando_host(BTRFS_CMD, "subvolume", "list", "-p", path),
            capture_output=True, text=True, timeout=10
        )
        snapshots = []
        for line in result.stdout.strip().split("\n"):
            if not line.startswith("ID "):
                continue
            path_match = re.search(r"\bpath\s+(\S+)", line)
            if not path_match:
                continue
            path = path_match.group(1)
            if "snapshot" in path.lower() or ".snapshots" in path:
                parts = line.split()
                if len(parts) >= 9:
                    snapshots.append({
                        "id": parts[1],
                        "path": path,
                        "parent": parts[6],
                    })
        return snapshots
    except (OSError, subprocess.SubprocessError):
        return []


def create_timeshift_snapshot(comment: str = "", tags: str = "O") -> tuple[bool, str]:
    """Crea snapshot Timeshift. tags: O=ondemand, B=boot, H=hourly, D=daily, W=weekly, M=monthly, Y=yearly"""
    if not is_timeshift_installed():
        return False, "Timeshift no instalado"
    try:
        cmd = [TIMESHIFT_CMD, "--create", "--comments", comment, "--tags", tags]
        result = subprocess.run(
            comando_host(*cmd),
            capture_output=True, text=True, timeout=120
        )
        return result.returncode == 0, result.stdout or result.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def restore_timeshift_snapshot(snapshot_id: str) -> tuple[bool, str]:
    """Restaura snapshot Timeshift (requiere reboot)."""
    if not is_timeshift_installed():
        return False, "Timeshift no instalado"
    try:
        # La restauración debe responder sola: no hay terminal interactiva bajo pkexec.
        result = subprocess.run(
            comando_host(
                TIMESHIFT_CMD, "--restore", "--snapshot", snapshot_id,
                "--skip-grub", "--scripted", "--yes",
            ),
            capture_output=True, text=True, timeout=300,
            stdin=subprocess.DEVNULL,
        )
        return result.returncode == 0, result.stdout or result.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def delete_timeshift_snapshot(snapshot_id: str) -> tuple[bool, str]:
    """Elimina snapshot Timeshift."""
    if not is_timeshift_installed():
        return False, "Timeshift no instalado"
    try:
        result = subprocess.run(
            comando_host(TIMESHIFT_CMD, "--delete", "--snapshot", snapshot_id),
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stdout or result.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def get_timeshift_config() -> dict:
    """Obtiene configuración actual de Timeshift."""
    if not is_timeshift_installed():
        return {}
    try:
        result = subprocess.run(
            comando_host(TIMESHIFT_CMD, "--list-config"),
            capture_output=True, text=True, timeout=10
        )
        config = {}
        for line in result.stdout.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                config[k.strip()] = v.strip()
        return config
    except (OSError, subprocess.SubprocessError):
        return {}


def set_timeshift_schedule(schedule: str, retention: str) -> bool:
    """Configura programación y retención de Timeshift.
    schedule: daily, weekly, monthly
    retention: formato Timeshift (ej: '7d', '4w', '3m')"""
    if not is_timeshift_installed():
        return False
    # Timeshift config se edita en /etc/timeshift.json
    # TODO: Implementar edición segura
    return False


def trigger_grub_btrfs_update() -> tuple[bool, str]:
    """Fuerza actualización de menú GRUB con snapshots Btrfs."""
    try:
        result = subprocess.run(
            comando_host("systemctl", "reload", "grub-btrfsd"),
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0, result.stdout or result.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def get_snapshot_status() -> dict:
    """Estado general de snapshots para UI."""
    config = get_effective_config()
    return {
        "btrfs_root": is_btrfs_root(),
        "btrfs_enabled": config.snapshots.btrfs_enabled,
        "timeshift_installed": is_timeshift_installed(),
        "timeshift_enabled": config.snapshots.timeshift_enabled,
        "grub_btrfs_active": is_grub_btrfs_active(),
        "grub_btrfs_enabled": config.snapshots.grub_btrfs,
        "schedule": config.snapshots.schedule,
        "retention": config.snapshots.retention,
        "timeshift_snapshots": list_timeshift_snapshots()[:10],  # últimos 10
        "btrfs_snapshots": list_btrfs_snapshots()[:10],
    }


# CLI para helper
def cli_snapshot_status() -> str:
    return json.dumps(get_snapshot_status())


def cli_create_snapshot(comment: str = "", tags: str = "O") -> str:
    ok, msg = create_timeshift_snapshot(comment, tags)
    return json.dumps({"success": ok, "message": msg})


def cli_restore_snapshot(snapshot_id: str) -> str:
    ok, msg = restore_timeshift_snapshot(snapshot_id)
    return json.dumps({"success": ok, "message": msg})


def cli_delete_snapshot(snapshot_id: str) -> str:
    ok, msg = delete_timeshift_snapshot(snapshot_id)
    return json.dumps({"success": ok, "message": msg})


def cli_grub_btrfs_update() -> str:
    ok, msg = trigger_grub_btrfs_update()
    return json.dumps({"success": ok, "message": msg})


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: ayusos_snapshots.py status|create|restore|delete|grub-update", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "status":
        print(cli_snapshot_status())
    elif cmd == "create":
        comment = sys.argv[2] if len(sys.argv) > 2 else ""
        tags = sys.argv[3] if len(sys.argv) > 3 else "O"
        print(cli_create_snapshot(comment, tags))
    elif cmd == "restore":
        if len(sys.argv) < 3:
            print("Falta snapshot_id", file=sys.stderr)
            sys.exit(1)
        print(cli_restore_snapshot(sys.argv[2]))
    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("Falta snapshot_id", file=sys.stderr)
            sys.exit(1)
        print(cli_delete_snapshot(sys.argv[2]))
    elif cmd == "grub-update":
        print(cli_grub_btrfs_update())
    else:
        print(f"Comando desconocido: {cmd}", file=sys.stderr)
        sys.exit(1)
