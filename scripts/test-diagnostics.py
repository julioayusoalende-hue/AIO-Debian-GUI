#!/usr/bin/env python3
"""Pruebas de clasificación del diagnóstico preventivo, sin alterar APT."""
import importlib.util
from pathlib import Path
from unittest import mock

module = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui/aio_core/diagnostics.py"
spec = importlib.util.spec_from_file_location("diagnostics", module)
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)


class Disk:
    total = 100 * (1024 ** 3)
    free = 1 * (1024 ** 3)


def fake_run(args, timeout=12):
    if args[0] == "dpkg":
        return 0, "package-x is not fully installed\n", ""
    if args[:2] == ["apt-get", "check"]:
        return 100, "", "Unmet dependencies"
    if args[:3] == ["apt-get", "-s", "upgrade"]:
        return 0, "Inst foo [1] (2 repo)\nInst bar [1] (2 repo)\n", ""
    if args[0] == "dkms":
        return 0, "nvidia/550, 6.12: added\n", ""
    if args[0] == "systemctl":
        return 0, "unit.service loaded failed failed\n", ""
    raise AssertionError(args)


with mock.patch.object(diag, "_run", side_effect=fake_run), \
     mock.patch.object(diag.shutil, "disk_usage", return_value=Disk()), \
     mock.patch.object(diag.shutil, "which", return_value="/usr/bin/exe"), \
     mock.patch.object(diag.Path, "exists", autospec=True, side_effect=lambda self: str(self) != "/.flatpak-info"), \
     mock.patch.object(diag.Path, "glob", return_value=[]):
    items = diag.run_diagnostics()
    statuses = {item["name"]: item["status"] for item in items}
    assert statuses["Estado de dpkg"] == "critical"
    assert statuses["Dependencias APT"] == "critical"
    assert statuses["Actualizaciones pendientes"] == "warning"
    assert statuses["Módulos DKMS"] == "warning"
    assert statuses["Reinicio pendiente"] == "warning"
    assert statuses["Servicios systemd"] == "warning"
    assert statuses["Índices de APT"] == "unknown"
    assert diag.overall_status(items) == "critical"

# Un comando imposible de ejecutar no debe aparecer como diagnóstico correcto.
with mock.patch.object(diag, "_run", return_value=(None, "", "command unavailable")), \
     mock.patch.object(diag.shutil, "disk_usage", return_value=Disk()), \
     mock.patch.object(diag.shutil, "which", return_value=None), \
     mock.patch.object(diag.Path, "exists", return_value=False), \
     mock.patch.object(diag.Path, "glob", return_value=[]):
    items = diag.run_diagnostics()
    by_name = {item["name"]: item for item in items}
    assert by_name["Dependencias APT"]["status"] == "unknown"
    assert by_name["Actualizaciones pendientes"]["status"] == "unknown"
    assert by_name["Estado de dpkg"]["status"] == "unknown"
    assert by_name["Módulos DKMS"]["status"] == "ok"  # sin módulo externo
print("✔ Diagnóstico preventivo: incidencias, pruebas incompletas y solo lectura")
