"""Comprobaciones conservadoras, sin privilegios y sin modificar el sistema.

La simulación no sustituye la validación final del asistente privilegiado.
"""
from dataclasses import dataclass
import os
import re
import shutil
import subprocess


@dataclass
class Report:
    blocked: bool
    messages: list


def _run(command, timeout=25):
    try:
        return subprocess.run(command, capture_output=True, text=True,
                              timeout=timeout, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return None


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
    """Bloquear errores conocidos; avisar de comprobaciones no concluyentes."""
    if tasks == ["flatpak-update"]:
        return Report(False, [])
    messages = []
    blocked = False
    locks = _apt_locks()
    if locks:
        blocked = True
        messages.append('APT/dpkg ocupado: ' + ', '.join(locks))
    elif locks is None:
        messages.append('No se pudo comprobar el bloqueo de APT/dpkg.')
    try:
        free = shutil.disk_usage("/").free
        if free < 1024 ** 3:
            blocked = True
            messages.append("Espacio insuficiente en /: menos de 1 GiB disponible.")
        elif free < 2 * 1024 ** 3:
            messages.append("Aviso: quedan menos de 2 GiB libres en /.")
    except OSError:
        messages.append("No se pudo comprobar el espacio libre en /.")

    if shutil.which("dpkg"):
        dpkg = _run(["dpkg", "--audit"])
        if dpkg is None or dpkg.returncode != 0:
            blocked = True
            messages.append("No se pudo verificar el estado de dpkg.")
        elif dpkg.stdout.strip():
            blocked = True
            messages.append("Hay paquetes pendientes de configurar (dpkg --audit).")

    if shutil.which("apt-get"):
        apt = _run(["apt-get", "-o", "Debug::NoLocking=1", "check"])
        if apt is None or apt.returncode != 0:
            blocked = True
            messages.append("APT informa de dependencias inconsistentes o no se pudo comprobar.")
        # No simular operaciones de configuración de repositorios o instalación de
        # paquetes aún no disponibles en índices: la simulación sería engañosa.
        simulations = []
        if "upgrade" in tasks:
            simulations.append(["apt-get", "-s", "-o", "Debug::NoLocking=1", "dist-upgrade"])
        if "autoremove" in tasks:
            simulations.append(["apt-get", "-s", "-o", "Debug::NoLocking=1", "autoremove"])
        for cmd in simulations:
            result = _run(cmd, timeout=45)
            if result is None or result.returncode != 0:
                blocked = True
                messages.append("No se pudo simular APT: " + cmd[-1])
                continue
            installs = [line.split()[1] for line in result.stdout.splitlines() if line.startswith("Inst ") and len(line.split()) > 1]
            removed = [line for line in result.stdout.splitlines()
                       if line.startswith("Rem ")]
            if installs:
                messages.append("Paquetes previstos para instalar/actualizar (" + str(len(installs)) + "): " + ", ".join(installs[:15]))
            if removed:
                blocked = True
                messages.append("La simulación propone eliminar paquetes: " +
                                ", ".join(line.split()[1] for line in removed[:12]))
            else:
                messages.append("Simulación APT correcta: " + cmd[-1] +
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
    return Report(blocked, messages)
