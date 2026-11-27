"""Solicita sincronización NTP sin esperar a que llegue una respuesta de red."""

import subprocess

ENABLE = "/usr/lib/aio-debian-gui/aio-clock-enable"


def solicitar_sincronizacion(comando_host):
    try:
        result = subprocess.run(comando_host(
            "/usr/bin/timedatectl", "--no-ask-password", "show", "-p", "CanNTP", "-p", "NTP",
        ), capture_output=True, text=True, timeout=5, check=True)
        estado = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if estado.get("CanNTP") == "yes" and estado.get("NTP") != "yes":
            subprocess.run(comando_host("/usr/bin/pkexec", "--disable-internal-agent", ENABLE),
                           capture_output=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        # El servicio de hora gestiona sus reintentos. AiO no depende de ellos.
        pass
