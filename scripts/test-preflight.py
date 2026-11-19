#!/usr/bin/env python3
"""Pruebas sin tocar APT ni el sistema anfitrión."""
import importlib.util
import hashlib
import json
import subprocess
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
    if "upgrade" in cmd:
        return SimpleNamespace(returncode=0, stdout="Remv linux-image-old [1]\n", stderr="")
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

# Vista previa detallada de versiones sin escrituras
with patch.object(mod, "_apt_locks", return_value=[]), patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), patch.object(mod, "_run", side_effect=lambda cmd, timeout=25: SimpleNamespace(returncode=0, stdout="Inst nano [7.2] (7.3 Debian:stable)\nInst vim (9.1 Debian:stable)\n" if "upgrade" in cmd else "", stderr="")):
    report = mod.check(["upgrade"])
    assert not report.blocked
    assert any("ACTUALIZAR: nano 7.2 → 7.3" in x for x in report.preview)
    assert any("INSTALAR: vim 9.1" in x for x in report.preview)

# Avisar de cambios en componentes críticos.
with patch.object(mod, "_apt_locks", return_value=[]), patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), patch.object(mod, "_run", side_effect=lambda cmd, timeout=25: SimpleNamespace(returncode=0, stdout="Inst linux-image-amd64 [6.1] (6.12 Debian:stable)\n" if "upgrade" in cmd else "", stderr="")):
    report = mod.check(["upgrade"])
    assert any("kernel, Mesa o NVIDIA" in m for m in report.messages)

# Las eliminaciones se bloquean durante upgrade y se revisan para autoremove.
for task in ("upgrade", "autoremove"):
    for marker in ("Remv", "Purg"):
        plan = f"{marker} old-package [1]\n"
        with patch.object(mod, "_apt_locks", return_value=[]), \
             patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
             patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
             patch.object(mod, "_run", side_effect=lambda cmd, timeout=25: SimpleNamespace(
                 returncode=0, stdout=plan if "-s" in cmd else "", stderr="")):
            report = mod.check([task])
            assert "ELIMINAR: old-package" in report.preview
            if task == "upgrade":
                assert report.blocked
            else:
                assert not report.blocked
                assert report.autoremove_plan == hashlib.sha256(plan.encode()).hexdigest()
                assert "Aviso: la simulación de autoremove propone eliminar paquetes:" in report.messages[-1]

plan = "Inst nano [7.2] (7.3 Debian:stable)\n"
with patch.object(mod, "_apt_locks", return_value=[]), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=lambda cmd, timeout=25: SimpleNamespace(
         returncode=0, stdout="Reading package lists...\n" + plan if "-s" in cmd else "", stderr="")):
    report = mod.check(["upgrade"])
    assert report.upgrade_plan == hashlib.sha256(plan.encode()).hexdigest()

# Dentro de Flatpak no se consulta /proc, espacio ni herramientas del sandbox.
host_report = {"blocked": False, "messages": ["host"], "preview": [],
               "upgrade_plan": hashlib.sha256(plan.encode()).hexdigest()}
with patch.dict(mod.os.environ, {"FLATPAK_ID": "test.app"}), \
     patch.object(mod, "_check_local", side_effect=AssertionError("sandbox inspected")), \
     patch.object(mod.subprocess, "run", return_value=SimpleNamespace(
         returncode=0, stdout=json.dumps(host_report))) as spawn:
    report = mod.check(["upgrade"])
    assert report.messages == ["host"] and report.upgrade_plan == host_report["upgrade_plan"]
    command = spawn.call_args.args[0]
    assert command[:6] == ["flatpak-spawn", "--host", "env", "LC_ALL=C", "python3", "-c"]
    compile(command[6], "<host-preflight>", "exec")
    assert json.loads(command[7]) == ["upgrade"]
    spawn.reset_mock()
    assert not mod.check(["flatpak-update"]).blocked
    spawn.assert_not_called()

for response in (SimpleNamespace(returncode=1, stdout=""),
                 SimpleNamespace(returncode=0, stdout="not json"),
                 SimpleNamespace(returncode=0, stdout='{"blocked": "false", "messages": []}')):
    with patch.dict(mod.os.environ, {"FLATPAK_ID": "test.app"}), \
         patch.object(mod.subprocess, "run", return_value=response):
        assert mod.check(["upgrade"]).blocked
for error in (OSError("host unavailable"), subprocess.TimeoutExpired("host", 180)):
    with patch.dict(mod.os.environ, {"FLATPAK_ID": "test.app"}), \
         patch.object(mod.subprocess, "run", side_effect=error):
        assert mod.check(["upgrade"]).blocked
print("Preflight: Remv/Purg, huella del plan y anfitrión Flatpak OK")
