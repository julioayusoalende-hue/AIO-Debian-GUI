#!/usr/bin/env python3
"""Checks required by the experimental Snap candidate before building."""
import ast
from pathlib import Path
try:
    import yaml
except ImportError:
    yaml = None
manifest = Path("snap/snapcraft.yaml").read_text(encoding="utf-8")
launcher = Path("snap/local/aio-debian-gui-snap").read_text(encoding="utf-8")
if yaml:
    data = yaml.safe_load(manifest)
    assert data["name"] == "aio-debian-gui"
    assert data["base"] == "core24"
    assert data["confinement"] == "classic"
    assert data["grade"] == "devel"
    assert data["version"] == Path("package/DEBIAN/control").read_text().split("Version: ", 1)[1].splitlines()[0]
    assert data["apps"]["aio-debian-gui"]["command"] == "usr/bin/aio-debian-gui-snap"
else:
    for name in ("name: aio-debian-gui", "base: core24", "confinement: classic", "grade: devel"):
        assert name in manifest
assert "exec /usr/bin/python3" in launcher
source = Path("package/usr/bin/aio-debian-gui").read_text(encoding="utf-8")
ast.parse(source)
assert 'if os.environ.get("SNAP"):' in source
assert 'return "snap"' in source
assert 'if formato in ("deb", "flatpak", "appimage"):' in source
print("✔ receta Snap en modo desarrollo, detección SNAP y gestión de actualizaciones por snapd")
