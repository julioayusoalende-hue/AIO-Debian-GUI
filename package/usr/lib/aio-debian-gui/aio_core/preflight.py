"""Comprobaciones conservadoras, sin privilegios y sin modificar el sistema.

La simulación no sustituye la validación final del asistente privilegiado.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


@dataclass
class Report:
    blocked: bool
    messages: list
    preview: list = None
    upgrade_plan: str = None
    autoremove_plan: str = None


def _run(command, timeout=25):
    try:
        return subprocess.run(command, capture_output=True, text=True,
                              timeout=timeout, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return None


def autoremove_keep():
    """Paquetes del programador que autoremove no debe retirar en AppImage/Flatpak."""
    keep = []
    for package in ("libnotify-bin", "needrestart"):
        result = _run(["dpkg-query", "-W", "-f=${db:Status-Status}", package])
        if result is not None and result.returncode == 0 and result.stdout == "installed":
            keep.append(package + "+")
    return keep


def _apt_locks():
    """Detectar bloqueos POSIX existentes sin modificarlos."""
    try:
        with open("/proc/locks", encoding="ascii") as stream:
            lines = stream.readlines()
        locks = set()
        for line in lines:
            if "POSIX" not in line:
                continue
            for token in line.split():
                if re.fullmatch(r"[0-9a-fA-F]+:[0-9a-fA-F]+:[0-9]+", token):
                    major, minor, inode = token.split(":")
                    locks.add((int(major, 16), int(minor, 16), int(inode)))
        busy = []
        for path in ("/var/lib/dpkg/lock", "/var/lib/dpkg/lock-frontend",
                     "/var/lib/apt/lists/lock", "/var/cache/apt/archives/lock"):
            try:
                st = os.stat(path)
            except FileNotFoundError:
                continue
            if (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino) in locks:
                busy.append(path)
        return busy
    except (OSError, ValueError):
        return None


def check(tasks):
    if tasks and set(tasks) <= {"flatpak-update", "snap-update"}:
        return Report(False, [])
    if os.environ.get("FLATPAK_ID") or Path("/.flatpak-info").exists():
        return _check_host(tasks)
    return _check_local(tasks)


def _check_host(tasks):
    """Ejecutar el mismo diagnóstico sin privilegios en el anfitrión.

    No depende de instalar módulos Python adicionales junto al helper del host.
    El código viaja como argumento, nunca se interpola en un shell.
    """
    try:
        source = Path(__file__).read_text(encoding="utf-8")
        source += ("\nimport sys\nfrom dataclasses import asdict\n"
                   "print(json.dumps(asdict(_check_local(json.loads(sys.argv[1])))))\n")
        result = subprocess.run(
            ["flatpak-spawn", "--host", "env", "LC_ALL=C", "python3", "-c",
             source, json.dumps(tasks)],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if result.returncode != 0:
            raise ValueError("host preflight failed")
        data = json.loads(result.stdout)
        if (type(data.get("blocked")) is not bool
                or not isinstance(data.get("messages"), list)
                or not all(isinstance(item, str) for item in data["messages"])
                or (data.get("preview") is not None and (
                    not isinstance(data["preview"], list)
                    or not all(isinstance(item, str) for item in data["preview"])))
                or any(data.get(key) is not None and not re.fullmatch(r"[0-9a-f]{64}", str(data[key]))
                       for key in ("upgrade_plan", "autoremove_plan"))):
            raise ValueError("invalid host report")
        return Report(**data)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError):
        return Report(True, ["No se pudieron completar las comprobaciones de seguridad en el anfitrión."])


def _check_local(tasks):
    """Bloquear errores conocidos; avisar de comprobaciones no concluyentes."""
    if tasks and set(tasks) <= {"flatpak-update", "snap-update"}:
        return Report(False, [])
    if {"autoremove", "autopurge"}.issubset(tasks):
        return Report(True, ["Selecciona una sola tarea de limpieza de dependencias."])
    messages = []
    preview = []
    upgrade_plan = None
    autoremove_plan = None
    blocked = False
    locks = _apt_locks()
    if locks:
        blocked = True
        messages.append('APT/dpkg ocupado: ' + ', '.join(locks))
    elif locks is None:
        blocked = True
        messages.append("No se pudo comprobar el bloqueo de APT/dpkg; operación detenida por seguridad.")
    try:
        free = shutil.disk_usage("/").free
        if free < 1024 ** 3:
            blocked = True
            messages.append("Espacio insuficiente en /: menos de 1 GiB disponible.")
        elif free < 2 * 1024 ** 3:
            messages.append("Aviso: quedan menos de 2 GiB libres en /.")
    except OSError:
        messages.append("No se pudo comprobar el espacio libre en /.")

    if not shutil.which("dpkg"):
        blocked = True
        messages.append("No se encuentra dpkg para comprobar su estado.")
    else:
        dpkg = _run(["dpkg", "--audit"])
        if dpkg is None or dpkg.returncode != 0 or dpkg.stderr.strip():
            blocked = True
            messages.append("No se pudo verificar el estado de dpkg.")
        elif dpkg.stdout.strip():
            blocked = True
            messages.append("Hay paquetes pendientes de configurar (dpkg --audit).")

    if blocked:
        return Report(True, messages)

    if shutil.which("apt-get"):
        apt = _run(["apt-get", "-o", "Debug::NoLocking=1", "check"])
        if apt is None or apt.returncode != 0:
            blocked = True
            messages.append("APT informa de dependencias inconsistentes o no se pudo comprobar.")
            return Report(True, messages)
        # No simular operaciones de configuración de repositorios o instalación de
        # paquetes aún no disponibles en índices: la simulación sería engañosa.
        simulations = []
        if "upgrade" in tasks:
            simulations.append(["apt-get", "-s", "-o", "Debug::NoLocking=1", "upgrade", "--with-new-pkgs", "--no-remove"])
        if "autoremove" in tasks or "autopurge" in tasks:
            mode = "--purge" if "autopurge" in tasks else "--no-purge"
            simulations.append(["apt-get", "-s", "-o", "Debug::NoLocking=1", "autoremove", mode, *autoremove_keep()])
        for cmd in simulations:
            result = _run(cmd, timeout=45)
            if result is None or result.returncode != 0:
                blocked = True
                messages.append("No se pudo simular APT: " + " ".join(cmd[4:6]))
                continue
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) < 2 or parts[0] not in ("Inst", "Remv", "Purg"):
                    continue
                if parts[0] in ("Remv", "Purg"):
                    preview.append(("PURGAR: " if parts[0] == "Purg" else "ELIMINAR: ") + parts[1])
                elif "[" in line and "]" in line:
                    previous = line.split("[", 1)[1].split("]", 1)[0]
                    new = line.split("(", 1)[1].split(" ", 1)[0] if "(" in line else "?"
                    preview.append("ACTUALIZAR: " + parts[1] + " " + previous + " → " + new)
                else:
                    new = line.split("(", 1)[1].split(" ", 1)[0] if "(" in line else "?"
                    preview.append("INSTALAR: " + parts[1] + " " + new)
            installs = [line.split()[1] for line in result.stdout.splitlines() if line.startswith("Inst ") and len(line.split()) > 1]
            removed = [line for line in result.stdout.splitlines()
                       if line.startswith(("Remv ", "Purg "))]
            plan_lines = [line for line in result.stdout.splitlines()
                          if line.startswith(("Inst ", "Remv ", "Purg "))]
            plan = hashlib.sha256("".join(line + "\n" for line in plan_lines).encode("utf-8")).hexdigest()
            action = cmd[4]
            if action == "upgrade":
                upgrade_plan = plan
                if removed:
                    blocked = True
                    messages.append("La actualización propone eliminar paquetes y se ha bloqueado.")
                    continue
            else:
                autoremove_plan = plan
            if installs:
                messages.append("Paquetes previstos para instalar/actualizar (" + str(len(installs)) + "): " + ", ".join(installs[:15]))
            if "--purge" in cmd:
                action = "autoremove --purge"
                messages.append("La purga elimina los archivos de configuración del sistema de los paquetes retirados.")
            if removed:
                messages.append("Aviso: la simulación de " + action +
                                " propone eliminar paquetes: " +
                                ", ".join(line.split()[1] for line in removed[:12]))
            else:
                messages.append("Simulación APT correcta: " + action +
                                " (sin eliminaciones previstas).")
    elif tasks:
        blocked = True
        messages.append("No se encuentra apt-get para comprobar las dependencias.")
    if shutil.which("dkms"):
        dkms = _run(["dkms", "status"])
        if dkms is None or dkms.returncode != 0:
            messages.append("No se pudo comprobar el estado de DKMS.")
        elif dkms.stdout.strip() and any(
                x in tasks for x in ("backports-kernel-mesa", "revertir-backports", "nvidia-driver", "ubuntu-hwe")):
            messages.append("Hay módulos DKMS registrados; comprueba su compatibilidad.")
    if any(any(marker in item.lower() for marker in ("linux-image", "linux-headers", "mesa", "nvidia")) for item in preview):
        messages.append("ATENCIÓN: la simulación afecta a kernel, Mesa o NVIDIA; revisa las versiones y la compatibilidad.")
    return Report(blocked, messages, preview, upgrade_plan, autoremove_plan)
