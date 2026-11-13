#!/usr/bin/env python3
"""Verifica selección del logotipo y disponibilidad en los tres empaquetados."""
import ast
from pathlib import Path
from xml.etree import ElementTree

root = Path("package/usr/share/aio-debian-gui")
debian = root / "debian-openlogo.png"
ubuntu = root / "ubuntu-logo.svg"
assert debian.is_file() and ubuntu.is_file()
assert ElementTree.parse(ubuntu).getroot().tag.endswith("svg")
source = Path("package/usr/bin/aio-debian-gui")
tree = ast.parse(source.read_text(encoding="utf-8"))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "logo_distribucion")
env = {"DEBIAN_LOGO": str(debian), "UBUNTU_LOGO": str(ubuntu)}
exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), env)
assert env["logo_distribucion"]("debian") == (str(debian), "Logotipo de Debian")
assert env["logo_distribucion"]("ubuntu") == (str(ubuntu), "Logotipo de Ubuntu")
assert env["logo_distribucion"]("no-soportada") == (None, None)
gui = source.read_text(encoding="utf-8")
assert "logo_distribucion(self.distribucion)" in gui
assert "GdkPixbuf.Pixbuf.new_from_file_at_scale(" in gui
for script in ("scripts/build-appimage.sh", "flatpak/io.github.julioayusoalende_hue.aio_debian_gui.yml"):
    content = Path(script).read_text(encoding="utf-8")
    assert "ubuntu-logo.svg" in content, script
control = Path("package/DEBIAN/control").read_text(encoding="utf-8")
assert "librsvg2-common" in control
print("✔ logos de Debian y Ubuntu, accesibilidad y recursos en DEB/AppImage/Flatpak")
