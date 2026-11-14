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

with patch.object(mod, "_apt_locks", return_value=[]), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=run):
    assert mod.check(["upgrade"]).blocked
    assert not mod.check(["flatpak-update"]).blocked
    assert not mod.check(["autoclean"]).blocked
with patch.object(mod, "_apt_locks", return_value=[]), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=500*1024**2)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=run):
    assert mod.check(["autoclean"]).blocked
print("Preflight: OK")

with patch.object(mod, "_apt_locks", return_value=["/var/lib/dpkg/lock"]), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=run):
    assert mod.check(["autoclean"]).blocked

# Fallar de forma segura si /proc/locks no es legible.
with patch.object(mod, "_apt_locks", return_value=None), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=run):
    assert mod.check(["upgrade"]).blocked

# Bloquear si falta dpkg y no iniciar simulaciones posteriores.
with patch.object(mod, "_apt_locks", return_value=[]), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", side_effect=lambda cmd: None if cmd == "dpkg" else "/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=run) as mocked:
    assert mod.check(["upgrade"]).blocked
    mocked.assert_not_called()
