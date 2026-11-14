"""Comprobaciones de salud de solo lectura."""
import os
import shutil
import subprocess

def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=12, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return None

def summary():
    lines = []
    try:
        lines.append("Espacio libre en /: %.1f GiB" % (shutil.disk_usage("/").free / 1024**3))
    except OSError:
        lines.append("Espacio libre: no disponible")
    if shutil.which("dpkg"):
        result = run(["dpkg", "--audit"])
        lines.append("dpkg: " + ("correcto" if result and result.returncode == 0 and not result.stdout.strip() else "requiere revisión"))
    if shutil.which("apt-get"):
        result = run(["apt-get", "-o", "Debug::NoLocking=1", "check"])
        lines.append("APT: " + ("dependencias correctas" if result and result.returncode == 0 else "requiere revisión"))
        if shutil.which("apt"):
            result = run(["apt", "list", "--upgradable"])
            if result and result.returncode == 0:
                lines.append("Actualizaciones pendientes (índices locales): %d" % sum("[upgradable from:" in line for line in result.stdout.splitlines()))
    lines.append("Reinicio: " + ("solicitado" if os.path.exists("/run/reboot-required") else "sin solicitud registrada"))
    return lines
