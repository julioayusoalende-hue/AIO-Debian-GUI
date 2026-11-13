#!/usr/bin/env python3
"""Probar la edición Snap experimental de manera no destructiva.

No inicia pkexec, no modifica APT y no ejecuta tareas administrativas.
Usar dentro de un Ubuntu de pruebas con el snap instalado.
"""
import os
import pathlib
import subprocess
import sys

def check(command):
    result = subprocess.run(command, text=True, capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError(f"{command!r} falló: {result.stderr.strip()[:500]}")
    return result.stdout.strip()

def main():
    if not pathlib.Path("/snap/bin/aio-debian-gui").exists():
        print("El Snap aio-debian-gui no parece estar instalado.", file=sys.stderr)
        return 2

    info = check(["snap", "list", "aio-debian-gui"])
    print("Instalación Snap:", info.splitlines()[-1])
    print("Confinamiento:", check(["snap", "info", "aio-debian-gui"]).split("confinement:")[-1].splitlines()[0].strip()
          if "confinement:" in check(["snap", "info", "aio-debian-gui"]) else "consultar snap info")
    snap_root = pathlib.Path("/snap/aio-debian-gui/current")
    for relative in ("usr/bin/aio-debian-gui",
                     "usr/lib/aio-debian-gui/aio_core/updates.py",
                     "usr/share/aio-debian-gui/ubuntu-logo.svg"):
        if not (snap_root / relative).is_file():
            print("Recurso ausente:", relative, file=sys.stderr)
            return 1
    print("Recursos Python e iconos verificados.")
    print("PENDIENTE MANUAL: abrir la interfaz desde el menú y comprobar Polkit con supervisión.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
