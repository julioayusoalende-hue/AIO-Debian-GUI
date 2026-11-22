#!/usr/bin/env python3
"""Verifica selección del logotipo y disponibilidad en el paquete Debian."""
import ast
from pathlib import Path
from xml.etree import ElementTree

root = Path("package/usr/share/aio-debian-gui")
debian = root / "debian-openlogo.png"
ubuntu = root / "ubuntu-logo.svg"
ayusos = root / "ayusos-logo.png"
assert debian.is_file() and ubuntu.is_file()
assert ayusos.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
assert ElementTree.parse(ubuntu).getroot().tag.endswith("svg")
source = Path("package/usr/bin/aio-debian-gui")
tree = ast.parse(source.read_text(encoding="utf-8"))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "logo_distribucion")
env = {"DEBIAN_LOGO": str(debian), "UBUNTU_LOGO": str(ubuntu), "AYUSOS_LOGO": str(ayusos)}
exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), env)
assert env["logo_distribucion"]("debian") == (str(debian), "Logotipo de Debian")
assert env["logo_distribucion"]("ubuntu") == (str(ubuntu), "Logotipo de Ubuntu")
assert env["logo_distribucion"]("ayusos") == (str(ayusos), "Logotipo de AyusOS Linux")
assert env["logo_distribucion"]("no-soportada") == (None, None)
gui = source.read_text(encoding="utf-8")
assert "imagen_logo_distribucion(self.datos_anfitrion, 16)" in gui
assert "imagen_logo_distribucion(self.datos_anfitrion, 100)" in gui
assert "GdkPixbuf.Pixbuf.new_from_file_at_scale(" in gui
for icon in ("brave", "gearlever", "celluloid", "feishin", "gimp", "google-chrome", "handbrake",
             "plex", "spotify", "switcheroo", "video-downloader", "vlc"):
    assert (root / "recommended-icons" / (icon + ".png")).is_file()
for icon in ("ghostty.svg", "kitty.svg"):
    assert ElementTree.parse(root / "recommended-icons" / icon).getroot().tag.endswith("svg")
for icon in ("timeshift.png", "deja-dup.png", "NOTICE.txt", "GPL-2.txt"):
    assert (root / "backup-icons" / icon).is_file()
control = Path("package/DEBIAN/control").read_text(encoding="utf-8")
assert "librsvg2-common" in control
print("✔ logos de Debian y Ubuntu, accesibilidad y recursos en el paquete Debian")
