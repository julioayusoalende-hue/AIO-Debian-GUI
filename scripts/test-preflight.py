#!/usr/bin/env python3
"""Pruebas sin tocar APT ni el sistema anfitrión."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui/aio_core/preflight.py"
spec = importlib.util.spec_from_file_location("preflight", path)
import sys

mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

def run(cmd, timeout=25, **kwargs):
    if "upgrade" in cmd:
        return SimpleNamespace(returncode=0, stdout="Remv linux-image-old [1]\n", stderr="")
    return SimpleNamespace(returncode=0, stdout="", stderr="")

with patch.object(mod, "_apt_locks", return_value=[]), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=run):
    assert mod.check(["upgrade"]).blocked
    assert not mod.check(["flatpak-update"]).blocked
    for tarea in ("clean-trash", "clean-thumbnails", "clean-journal", "clean-flatpak", "clean-snap"):
        assert not mod.check([tarea]).blocked
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
with patch.object(mod, "_apt_locks", return_value=[]), patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), patch.object(mod, "_run", side_effect=lambda cmd, timeout=25, **kwargs: SimpleNamespace(returncode=0, stdout="Inst nano [7.2] (7.3 Debian:stable)\nInst vim (9.1 Debian:stable)\n" if "upgrade" in cmd else "", stderr="")):
    report = mod.check(["upgrade"])
    assert not report.blocked
    assert any("ACTUALIZAR: nano 7.2 → 7.3" in x for x in report.preview)
    assert any("INSTALAR: vim 9.1" in x for x in report.preview)

# Avisar de cambios en componentes críticos.
with patch.object(mod, "_apt_locks", return_value=[]), patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), patch.object(mod, "_run", side_effect=lambda cmd, timeout=25, **kwargs: SimpleNamespace(returncode=0, stdout="Inst linux-image-amd64 [6.1] (6.12 Debian:stable)\n" if "upgrade" in cmd else "", stderr="")):
    report = mod.check(["upgrade"])
    assert any("kernel, Mesa o NVIDIA" in m for m in report.messages)

# Las eliminaciones se bloquean durante upgrade y se revisan para autoremove.
for task in ("upgrade", "autoremove"):
    for marker in ("Remv", "Purg"):
        plan = f"{marker} old-package [1]\n"
        with patch.object(mod, "_apt_locks", return_value=[]), \
             patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
             patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
             patch.object(mod, "_run", side_effect=lambda cmd, timeout=25, **kwargs: SimpleNamespace(
                 returncode=0, stdout=plan if "-s" in cmd else "", stderr="")):
            report = mod.check([task])
            assert ("PURGAR: " if marker == "Purg" else "ELIMINAR: ") + "old-package" in report.preview
            if task == "upgrade":
                assert report.blocked
            else:
                assert not report.blocked
                assert report.autoremove_plan == hashlib.sha256(plan.encode()).hexdigest()
                assert "Aviso: la simulación de autoremove propone eliminar paquetes:" in report.messages[-1]

# La purga tiene una simulación explícita y una huella de las acciones mostradas.
with patch.object(mod, "_apt_locks", return_value=[]), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=lambda cmd, timeout=25, **kwargs: SimpleNamespace(
         returncode=0, stdout="Purg old-package [1]\n" if "--purge" in cmd else "", stderr="")) as run:
    report = mod.check(["autopurge"])
    assert not report.blocked
    assert "PURGAR: old-package" in report.preview
    assert report.autoremove_plan == hashlib.sha256(b"Purg old-package [1]\n").hexdigest()
    assert any("archivos de configuración" in message for message in report.messages)
    assert any("--purge" in args[0] for args, _kwargs in run.call_args_list)
    assert mod.check(["autoremove", "autopurge"]).blocked

plan = "Inst nano [7.2] (7.3 Debian:stable)\n"
with patch.object(mod, "_apt_locks", return_value=[]), \
     patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod.shutil, "which", return_value="/usr/bin/tool"), \
     patch.object(mod, "_run", side_effect=lambda cmd, timeout=25, **kwargs: SimpleNamespace(
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


# Comunicar la causa concreta del bloqueo sin continuar con APT.
for result, detail in (
    (subprocess.TimeoutExpired(["dpkg", "--audit"], 60), "no terminó en 60 segundos"),
    (PermissionError("Permiso denegado"), "Permiso denegado"),
    (SimpleNamespace(returncode=2, stdout="", stderr="dpkg: error: cannot read status"), "cannot read status"),
    (SimpleNamespace(returncode=0, stdout="", stderr="dpkg: warning: missing metadata"), "missing metadata"),
    (SimpleNamespace(returncode=0, stdout="libreoffice-core pendiente", stderr=""), "libreoffice-core pendiente"),
):
    with patch.object(mod, "_apt_locks", return_value=[]), \
         patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
         patch.object(mod.shutil, "which", return_value="/usr/bin/dpkg"), \
         patch.object(mod, "_run", side_effect=[result]) as audit:
        report = mod._check_local(["upgrade"])
    assert report.blocked and detail in "\n".join(report.messages), report.messages
    audit.assert_called_once_with(["dpkg", "--audit"], timeout=60, raise_errors=True)


with patch.object(mod.shutil, "disk_usage", return_value=SimpleNamespace(free=4*1024**3)), \
     patch.object(mod, "_apt_locks", side_effect=AssertionError("APT gestiona sus bloqueos")), \
     patch.object(mod, "_run", side_effect=AssertionError("comprobación APT duplicada")):
    report = mod._check_local(["upgrade", "autoremove", "autoclean", "rebootcheck"])
    assert not report.blocked and report.upgrade_plan is None and report.autoremove_plan is None
