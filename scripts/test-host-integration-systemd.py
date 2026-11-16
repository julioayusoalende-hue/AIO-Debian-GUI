#!/usr/bin/env python3
"""Prueba privilegiada únicamente en la VM efímera de GitHub Actions."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

if os.environ.get("AIO_HOST_INTEGRATION_TEST") != "1":
    print("Integración real omitida; requiere una VM de CI efímera.")
    sys.exit(0)
if os.environ.get("GITHUB_ACTIONS") != "true" or Path("/proc/1/comm").read_text().strip() != "systemd":
    raise SystemExit("Esta prueba solo puede ejecutarse en una VM de GitHub Actions con systemd.")

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "package/usr/lib/aio-debian-gui"))
from aio_core import host_integration, scheduler

files = {
    "__init__.py": "package/usr/lib/aio-debian-gui/aio_core/__init__.py",
    "scheduler.py": "package/usr/lib/aio-debian-gui/aio_core/scheduler.py",
    "preflight.py": "package/usr/lib/aio-debian-gui/aio_core/preflight.py",
    "aio-debian-gui-helper": "package/usr/lib/aio-debian-gui/aio-debian-gui-helper",
    "es.aiodebian.gui.policy": "package/usr/share/polkit-1/actions/es.aiodebian.gui.policy",
    "aio-debian-gui-maintenance@.service": "package/usr/lib/systemd/system/aio-debian-gui-maintenance@.service",
}
destinations = (
    "/usr/lib/aio-debian-gui/aio_core/__init__.py",
    "/usr/lib/aio-debian-gui/aio_core/scheduler.py",
    "/usr/lib/aio-debian-gui/aio_core/preflight.py",
    "/usr/share/polkit-1/actions/es.aiodebian.gui.policy",
    "/usr/lib/systemd/system/aio-debian-gui-maintenance@.service",
    "/usr/lib/aio-debian-gui/aio-debian-gui-helper",
)
if any(Path(path).exists() or Path(path).is_symlink() for path in destinations):
    raise SystemExit("La VM ya contiene archivos de integración; se cancela la prueba.")
payload = {}
for name, path in files.items():
    data = (root / path).read_bytes()
    payload[name] = {"sha256": hashlib.sha256(data).hexdigest(),
                     "data": base64.b64encode(data).decode("ascii")}
command = ["sudo", "pkexec", "/usr/bin/python3", "-I", "-c", host_integration._ROOT_PROGRAM]

def install():
    return subprocess.run(command, input=json.dumps(payload), text=True,
                          capture_output=True, timeout=120)

result = install()
if result.returncode:
    raise SystemExit("Falló la instalación: " + result.stderr)
try:
    status = subprocess.run([destinations[-1], "--schedule-status"],
                            text=True, capture_output=True, check=True, timeout=30)
    report = json.loads(status.stdout)
    assert report["available"] and report["version"] == scheduler.VERSION, report
    again = install()
    assert again.returncode and again.stderr.strip(), (again.stdout, again.stderr)
    for path, name in zip(destinations, ("__init__.py", "scheduler.py", "preflight.py",
                                         "es.aiodebian.gui.policy", "aio-debian-gui-maintenance@.service",
                                         "aio-debian-gui-helper")):
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == payload[name]["sha256"], path
finally:
    subprocess.run(["sudo", "rm", "--", *destinations], check=True)
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
print("Instalación real inicial, estado del programador y protección ante repetición: OK")
