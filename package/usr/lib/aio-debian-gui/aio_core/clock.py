"""Comprueba la sincronización mediante el proveedor NTP del sistema."""
import subprocess
import time

ENABLE = "/usr/lib/aio-debian-gui/aio-clock-enable"


def sincronizar(comando_host, espera=25):
    def ejecutar(*args, timeout=5):
        return subprocess.run(comando_host(*args), capture_output=True, text=True,
                              check=True, timeout=timeout).stdout

    def estado():
        return dict(line.split("=", 1) for line in ejecutar(
            "/usr/bin/timedatectl", "--no-ask-password", "show",
            "-p", "NTPSynchronized", "-p", "NTP",
        ).splitlines() if "=" in line)

    inicial = estado()
    if inicial.get("NTPSynchronized") == "yes":
        return True
    if inicial.get("NTP") != "yes":
        ejecutar("/usr/bin/test", "-x", ENABLE)
        ejecutar("/usr/bin/pkexec", "--disable-internal-agent", ENABLE, timeout=90)

    limite = time.monotonic() + espera
    while time.monotonic() < limite:
        if estado().get("NTPSynchronized") == "yes":
            return True
        time.sleep(1)
    return False
