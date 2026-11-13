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
    path = check(["snap", "get", "aio-debian-gui", "nonexistent-test-key"]) if False else None
    del path
    result = subprocess.run(["snap", "run", "--shell", "aio-debian-gui", "-c",
                             'test -f "$SNAP/usr/bin/aio-debian-gui" && '
                             'test -f "$SNAP/usr/lib/aio-debian-gui/aio_core/updates.py" && '
                             'test -f "$SNAP/usr/share/aio-debian-gui/ubuntu-logo.svg"'],
                            text=True, capture_output=True, timeout=20)
    if result.returncode:
        print("No se pudieron verificar los recursos del Snap:", result.stderr, file=sys.stderr)
        return 1
    print("Recursos Python e iconos verificados.")
    print("PENDIENTE MANUAL: abrir la interfaz desde el menú y comprobar Polkit con supervisión.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
