#!/usr/bin/env python3
"""Pruebas aisladas del actualizador del anfitrión, sin dpkg ni systemd reales."""
import fcntl
import importlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(tempfile.mkdtemp(prefix="host-updater-"))
sys.dont_write_bytecode = True
try:
    core = WORK / "aio_core"
    core.mkdir()
    (core / "__init__.py").touch()
    for source in ("package/usr/lib/aio-debian-gui/aio_core/host_repository.py",
                   "host-package/usr/lib/aio-debian-gui/aio_core/host_requests.py",
                   "host-package/usr/lib/aio-debian-gui/aio_core/host_updater.py"):
        shutil.copy(ROOT / source, core)
    sys.path.insert(0, str(WORK))
    updater = importlib.import_module("aio_core.host_updater")
    updater.RUN_DIR = WORK / "run"
    updater.ROOT_UID = os.geteuid()
    calls = []
    state = {"installed": ("2.10.8", False), "requests": ["2.10.9"], "dpkg": 0}

    def fake_run(args, timeout=900):
        calls.append(args)
        if args[0].endswith("dpkg-query"):
            if state["installed"] is None:
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            version, hold = state["installed"]
            return SimpleNamespace(returncode=0, stderr="",
                                   stdout=f"installed\t{version}\t{'hold' if hold else 'install'}\n")
        if args[0].endswith("dpkg-deb"):
            return SimpleNamespace(returncode=0, stderr="", stdout=state.get(
                "fields", "Package: aio-debian-gui-host\nVersion: 2.10.9\n"))
        if args[1] == "--force-confold":
            if state["dpkg"]:
                return SimpleNamespace(returncode=1, stdout="", stderr="fallo")
            state["installed"] = ("2.10.9", False)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def download(keyring):
        downloads.append(keyring)
        return {"version": state.get("remote", "2.10.9")}, b"deb"

    downloads = []

    def run_update():
        calls.clear()
        downloads.clear()
        with mock.patch.object(updater, "_run", fake_run), \
             mock.patch.object(updater.host_requests, "authorized_users", return_value=[1000, 1001]), \
             mock.patch.object(updater.host_requests, "read_request",
                               side_effect=lambda uid: (state["requests"] + [None, None])[uid - 1000]):
            return updater.update(download)

    state["requests"] = []
    assert run_update() == "sin solicitud" and not calls
    state["requests"] = ["2.10.9"]
    state["installed"] = None
    assert run_update() == "paquete no instalado" and not downloads
    state["installed"] = ("2.10.8", True)
    assert run_update() == "paquete retenido" and not downloads
    for current in ("2.10.9", "2.11.0"):
        state["installed"] = (current, False)
        assert run_update() == "actualizado" and not downloads
    state["requests"] = ["2.10.9", "2.9.99"]
    state["installed"] = ("2.10.8", False)
    state["remote"] = "2.10.8"
    assert run_update() == "repositorio sin la versión solicitada"
    assert not any(c[1:2] == ["--force-confold"] for c in calls)
    state["remote"] = "2.10.9"
    state["fields"] = "Package: otro\nVersion: 2.10.9\n"
    try:
        run_update()
    except RuntimeError as exc:
        assert "no coincide" in str(exc)
    else:
        raise AssertionError("Paquete con identidad distinta aceptado")
    del state["fields"]
    state["dpkg"] = 1
    try:
        run_update()
    except RuntimeError as exc:
        assert "No se pudo instalar" in str(exc)
    else:
        raise AssertionError("Fallo de dpkg no notificado")
    assert calls[-1][:2] == ["/usr/bin/dpkg", "--configure"]
    assert not list(updater.RUN_DIR.glob("update-*"))
    state["dpkg"] = 0
    assert run_update() == "actualizado a 2.10.9"
    install = [c for c in calls if c[1:2] == ["--force-confold"]]
    assert len(install) == 1 and install[0][:3] == ["/usr/bin/dpkg", "--force-confold", "-i"]
    assert not list(updater.RUN_DIR.glob("update-*"))

    # Un programador o mantenimiento en ejecución bloquea la actualización.
    for name in (updater.UPDATE_LOCK, updater.MAINTENANCE_LOCK):
        state["installed"] = ("2.10.8", False)
        fd = updater._open_lock(name)
        fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            run_update()
        except updater.Busy:
            assert not downloads
        else:
            raise AssertionError("Bloqueo ignorado: " + name)
        finally:
            os.close(fd)
    for bad in ("2.10", "2.10.x", "02.1.1\n", 5):
        try:
            updater.parse_version(bad)
        except ValueError:
            continue
        if bad == "02.1.1\n":
            continue
        raise AssertionError(bad)
finally:
    shutil.rmtree(WORK)
print("✔ Actualizador del anfitrión: bloqueos, no-downgrade, hold, fallos y limpieza")
