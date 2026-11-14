"""Diagnóstico preventivo, local y de solo lectura para AiO Debian GUI.

No ejecuta apt update/install, dpkg --configure, systemctl start ni sudo.
Los fallos de lectura se muestran como «no disponible», nunca como sistema sano.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def _check(name, status, detail, advice=""):
    return {"name": name, "status": status, "detail": detail, "advice": advice}


def _run(args, timeout=12):
    try:
        result = subprocess.run(
            args, text=True, capture_output=True, timeout=timeout,
            check=False, env={**os.environ, "LC_ALL": "C"},
        )
        return result.returncode, (result.stdout or ""), (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "", str(exc)


def run_diagnostics():
    """Devuelve una lista de comprobaciones sin alterar el sistema."""
    findings = []
    # La sandbox Flatpak no representa fielmente el sistema anfitrión:
    # sin conexión de confianza no se deduce salud del host a partir de ella.
    if Path("/.flatpak-info").exists():
        return [_check(
            "Sistema anfitrión", "unknown",
            "El diagnóstico local está limitado dentro de Flatpak; no se han comprobado APT, dpkg ni systemd del anfitrión.",
            "Para revisar Debian/Ubuntu usa la edición DEB o AppImage fuera del sandbox."
        )]

    # Espacio libre en la partición del sistema.
    try:
        disk = shutil.disk_usage("/")
        ratio = disk.free / disk.total if disk.total else 0
        gib = disk.free / (1024 ** 3)
        level = "critical" if gib < 1 or ratio < .03 else (
            "warning" if gib < 3 or ratio < .10 else "ok"
        )
        findings.append(_check("Espacio en /", level,
            f"{gib:.1f} GiB libres ({ratio:.0%} del volumen)",
            "Libera espacio antes de grandes actualizaciones." if level != "ok" else ""))
    except OSError as exc:
        findings.append(_check("Espacio en /", "unknown", str(exc)))

    # Recuento conservador de paquetes que dpkg considera incompletos.
    rc, output, error = _run(["dpkg", "--audit"])
    if rc is None or rc != 0:
        findings.append(_check("Estado de dpkg", "unknown",
            (error or output or "No pudo comprobarse dpkg.").strip()[:350]))
    elif output.strip():
        findings.append(_check("Estado de dpkg", "critical",
            output.strip()[:500],
            "Revisa los paquetes incompletos antes de iniciar otras operaciones APT."))
    else:
        findings.append(_check("Estado de dpkg", "ok", "No se detectaron paquetes parcialmente instalados."))

    # apt-get check lee dependencias; nunca resuelve ni modifica paquetes.
    rc, output, error = _run(["apt-get", "check"], timeout=20)
    if rc is None:
        findings.append(_check("Dependencias APT", "unknown", error[:350]))
    elif rc != 0:
        findings.append(_check("Dependencias APT", "critical",
            (error or output or "APT informa de errores.").strip()[-500:],
            "Examina las dependencias antes de actualizar."))
    else:
        findings.append(_check("Dependencias APT", "ok", "APT no comunica errores de dependencias."))

    # Contar solo las líneas Inst de la simulación, sin aplicar actualizaciones.
    rc, output, error = _run(["apt-get", "-s", "upgrade"], timeout=25)
    if rc is None or rc != 0:
        findings.append(_check("Actualizaciones pendientes", "unknown",
            (error or output or "No se pudo simular APT.").strip()[-350:]))
    else:
        pending = sum(1 for line in output.splitlines() if line.startswith("Inst "))
        held = re.search(r"(\d+) not upgraded", output)
        suffix = f"; {held.group(1)} retenidos" if held and int(held.group(1)) else ""
        findings.append(_check("Actualizaciones pendientes",
            "warning" if pending else "ok",
            f"{pending} actualizaciones estimadas por APT{suffix}.",
            "Revisa y aplica las actualizaciones del sistema cuando corresponda." if pending else ""))
    
    # Una caché antigua NO significa cero actualizaciones. Esta comprobación
    # informa de la frescura de los índices existentes, sin actualizar APT.
    try:
        entries = [p.stat().st_mtime for p in Path("/var/lib/apt/lists").glob("*_Packages*")
                   if p.is_file()]
        if entries:
            days = max(0, int((time.time() - max(entries)) / 86400))
            stale = days >= 7
            findings.append(_check("Índices de APT", "warning" if stale else "ok",
                f"Último índice de paquetes: hace {days} días.",
                "Ejecuta «Actualizar paquetes del sistema» para refrescar los índices." if stale else ""))
        else:
            findings.append(_check("Índices de APT", "unknown",
                "No se pudieron fechar los índices disponibles."))
    except OSError as exc:
        findings.append(_check("Índices de APT", "unknown", str(exc)))

    # DKMS puede no estar instalado. La ausencia no es un problema en equipos
    # sin módulos externos.
    if shutil.which("dkms"):
        rc, output, error = _run(["dkms", "status"])
        if rc is None or rc != 0:
            findings.append(_check("Módulos DKMS", "unknown",
                (error or output or "No se pudo consultar DKMS.").strip()[:350]))
        else:
            problems = [line.strip() for line in output.splitlines()
                        if line.strip() and (":" in line) and
                        not re.search(r":\s*installed(?:\s|$)", line)]
            findings.append(_check("Módulos DKMS", "warning" if problems else "ok",
                "; ".join(problems[:4])[:400] if problems else
                ("Módulos registrados sin incidencias detectadas." if output.strip()
                 else "No hay módulos DKMS registrados."),
                "Comprueba la compilación de módulos para el kernel actual." if problems else ""))
    else:
        findings.append(_check("Módulos DKMS", "ok",
            "DKMS no está instalado; es normal si no utilizas módulos externos."))

    # Indicador estándar (Debian/Ubuntu) de reinicio pendiente.
    reboot = Path("/run/reboot-required")
    findings.append(_check("Reinicio pendiente",
        "warning" if reboot.exists() else "ok",
        "El sistema solicita reiniciar." if reboot.exists() else
        "No hay una solicitud explícita de reinicio registrada.",
        "Guarda tu trabajo y reinicia cuando sea oportuno." if reboot.exists() else ""))

    if shutil.which("systemctl") and Path("/run/systemd/system").exists():
        rc, output, error = _run(["systemctl", "--failed", "--no-legend", "--plain", "--no-pager"])
        if rc is None or rc not in (0,):
            findings.append(_check("Servicios systemd", "unknown",
                (error or output or "No se pudo consultar systemd.").strip()[:300]))
        else:
            failed = [line.strip() for line in output.splitlines()
                      if line.strip() and not line.startswith("0 loaded units")]
            findings.append(_check("Servicios systemd", "warning" if failed else "ok",
                "; ".join(failed[:4])[:400] if failed else "Sin unidades fallidas.",
                "Revisa los servicios fallidos con systemctl --failed." if failed else ""))
    else:
        findings.append(_check("Servicios systemd", "unknown",
            "systemd no está disponible en esta sesión."))

    return findings


def overall_status(findings):
    statuses = {f["status"] for f in findings}
    for status in ("critical", "warning", "unknown"):
        if status in statuses:
            return status
    return "ok"
