#!/usr/bin/env python3
"""Pruebas sin tocar APT ni el sistema anfitrión."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui/aio_core/preflight.py"
spec = importlib.util.spec_from_file_location("preflight", path)
import sys
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

def run(cmd, timeout=25):
    if "dist-upgrade" in cmd:
        return SimpleNamespace(returncode=0, stdout="Rem linux-image-old [1]\n", stderr="")
    return SimpleNamespace(returncode=0, stdout="", stderr="")

with patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=run):
    assert mod.check(["apt-upgrade"]).blocked
    assert not mod.check(["flatpak-update"]).blocked
    assert not mod.check(["apt-autoclean"]).blocked
with patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=500*1024**2)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=run):
    assert mod.check(["apt-autoclean"]).blocked
print("Preflight: OK")
