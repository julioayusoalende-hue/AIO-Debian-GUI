#!/usr/bin/env python3
"""Sincroniza o valida las versiones de los paquetes desde DEBIAN/control."""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "package/DEBIAN/control"
HELPER = ROOT / "package/usr/lib/aio-debian-gui/aio-debian-gui-helper"
FLATPAK = ROOT / "flatpak/io.github.julioayusoalende_hue.aio_debian_gui.yml"
META = ROOT / "flatpak/io.github.julioayusoalende_hue.aio_debian_gui.metainfo.xml"

def run(write=False):
    control = CONTROL.read_text(encoding="utf-8")
    match = re.search(r"^Version: (\d+\.\d+\.\d+)$", control, re.M)
    if not match:
        raise ValueError("Versión inválida en package/DEBIAN/control")
    version = match.group(1)
    specs = [
        (HELPER, r"(?m)^HELPER_VERSION=\d+\.\d+\.\d+$", f"HELPER_VERSION={version}"),
        (FLATPAK, r"--env=AIO_DEBIAN_GUI_VERSION=\d+\.\d+\.\d+", f"--env=AIO_DEBIAN_GUI_VERSION={version}"),
    ]
    errors = []
    for path, pattern, replacement in specs:
        old = path.read_text(encoding="utf-8")
        new, count = re.subn(pattern, replacement, old)
        if count != 1:
            errors.append(f"{path.relative_to(ROOT)}: marcador ausente o duplicado")
        elif old != new:
            if write:
                path.write_text(new, encoding="utf-8")
                print(f"Actualizado: {path.relative_to(ROOT)} -> {version}")
            else:
                errors.append(f"{path.relative_to(ROOT)}: versión distinta de {version}")
    metadata = META.read_text(encoding="utf-8")
    release = re.search(r'<release\s+version="([^"]+)"', metadata)
    if not release or release.group(1) != version:
        errors.append(f"{META.relative_to(ROOT)}: la primera release AppStream debe ser {version}")
    if errors:
        for error in errors:
            print("ERROR:", error, file=sys.stderr)
        return 1
    print(f"Versiones sincronizadas: DEB, AppImage, Flatpak, helper y AppStream = {version}")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Sincroniza helper y Flatpak con el control DEB")
    args = parser.parse_args()
    sys.exit(run(args.write))
