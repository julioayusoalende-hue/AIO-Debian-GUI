"""Operaciones privilegiadas del modo de recuperación de AyusOS."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from aio_core.constants import comando_host

from . import ayusos_diagnostics, ayusos_snapshots

RECOVERY_PARAMETER = "ayusos-recovery"
_SNAPSHOT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}$")


def is_recovery_boot(cmdline: str = "/proc/cmdline") -> bool:
    """Indica si el kernel recibió el parámetro exacto ``ayusos-recovery``."""
    try:
        tokens = Path(cmdline).read_text(encoding="utf-8").split()
    except OSError:
        return False
    return RECOVERY_PARAMETER in tokens


def _run(command: list[str], timeout: int = 300) -> tuple[bool, str]:
    env = os.environ.copy()
    env.update({
        "DEBIAN_FRONTEND": "noninteractive",
        "APT_LISTCHANGES_FRONTEND": "none",
        "NEEDRESTART_MODE": "l",
        "LC_ALL": "C",
    })
    try:
        result = subprocess.run(
            comando_host(*command),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    detail = "\n".join(part for part in (output, error) if part)
    return result.returncode == 0, detail


def repair_system() -> tuple[bool, str]:
    """Repara dpkg y APT sin solicitar entrada interactiva."""
    commands = (
        ("dpkg --configure -a", ["dpkg", "--configure", "-a"]),
        (
            "apt-get --fix-broken install",
            [
                "apt-get", "-y",
                "-o", "Dpkg::Options::=--force-confdef",
                "-o", "Dpkg::Options::=--force-confold",
                "--fix-broken", "install",
            ],
        ),
        ("apt-get update", ["apt-get", "-o", "APT::Update::Error-Mode=any", "update"]),
    )
    messages = []
    failed = False
    for title, command in commands:
        ok, detail = _run(command, timeout=600)
        messages.append(f"{title}: {'OK' if ok else 'ERROR'}")
        if detail:
            messages.append(detail)
        failed = failed or not ok
    return not failed, "\n".join(messages)


def regenerate_grub() -> tuple[bool, str]:
    """Regenera grub.cfg con la herramienta disponible en el sistema."""
    if shutil.which("update-grub"):
        ok, detail = _run(["update-grub"], timeout=180)
    elif shutil.which("grub-mkconfig"):
        ok, detail = _run(["grub-mkconfig", "-o", "/boot/grub/grub.cfg"], timeout=180)
    else:
        return False, "No se encontró update-grub ni grub-mkconfig."
    return ok, detail or "GRUB actualizado."


def restore_snapshot(snapshot_id: str) -> tuple[bool, str]:
    """Valida y restaura un snapshot de Timeshift."""
    if not _SNAPSHOT_ID.fullmatch(snapshot_id or ""):
        return False, "Identificador de snapshot no válido."
    return ayusos_snapshots.restore_timeshift_snapshot(snapshot_id)


def execute(action: str, snapshot_id: str | None = None) -> dict:
    """Ejecuta una acción y devuelve un resultado serializable para la GUI."""
    if action == "repair":
        ok, message = repair_system()
        return {"success": ok, "message": message}
    if action == "grub":
        ok, message = regenerate_grub()
        return {"success": ok, "message": message}
    if action == "diagnostics":
        return {"success": True, "diagnostics": ayusos_diagnostics.run_full_diagnostics()}
    if action == "snapshots":
        return {
            "success": True,
            "snapshots": ayusos_snapshots.list_timeshift_snapshots(),
        }
    if action == "restore":
        if not snapshot_id:
            return {"success": False, "message": "Falta el snapshot seleccionado."}
        ok, message = restore_snapshot(snapshot_id)
        return {"success": ok, "message": message}
    return {"success": False, "message": f"Acción desconocida: {action}"}


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if os.geteuid() != 0:
        print(json.dumps({"success": False, "message": "Se requieren privilegios de administrador."}))
        return 1
    if not args or args[0] not in {"repair", "grub", "diagnostics", "snapshots", "restore"}:
        print(json.dumps({
            "success": False,
            "message": "Uso: ayusos-recovery repair|grub|diagnostics|snapshots|restore [ID]",
        }))
        return 2
    if args[0] == "restore" and len(args) != 2:
        print(json.dumps({"success": False, "message": "Falta el snapshot seleccionado."}))
        return 2
    if args[0] != "restore" and len(args) != 1:
        print(json.dumps({"success": False, "message": "Argumentos no válidos."}))
        return 2
    result = execute(args[0], args[1] if len(args) == 2 else None)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
