"""Comprobaciones conservadoras, sin privilegios y sin modificar el sistema.

La simulación no sustituye la validación final del asistente privilegiado.
"""
from dataclasses import dataclass
import os
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


def check(tasks):
    """Bloquear errores conocidos; avisar de comprobaciones no concluyentes."""
    if tasks == ["flatpak-update"]:
        return Report(False, [])
    messages = []
    blocked = False
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
            removed = [line for line in result.stdout.splitlines()
                       if line.startswith("Rem ")]
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
