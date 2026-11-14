#!/usr/bin/env python3
"""Pruebas sin red, sin GTK y sin cambios al sistema para actualizaciones de AiO."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

module = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui/aio_core/updates.py"
spec = importlib.util.spec_from_file_location("aio_updates", module)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

APPID = "io.github.julioayusoalende_hue.aio_debian_gui"


def process(code=0, out="", err=""):
    return SimpleNamespace(returncode=code, stdout=out, stderr=err)


def apt_simulated(args, **kw):
    assert kw["check"] is False
    if args[:3] == ["apt-cache", "policy", "aio-debian-gui"]:
        assert kw["env"]["LC_ALL"] == "C", "apt-cache policy debe ejecutarse en locale C"
    if args[:3] == ["apt-cache", "policy", "aio-debian-gui"]:
        return process(out="  Installed: 2.0.6\n  Candidate: 2.0.7\n")
    assert args == ["dpkg", "--compare-versions", "2.0.7", "gt", "2.0.6"]
    return process()


with patch("subprocess.run", side_effect=apt_simulated):
    r = mod.estado_actualizacion_app("deb", "2.0.6", APPID)
    assert r["status"] == "available" and r["version"] == "2.0.7"

# APT puede estar en español en el escritorio; la implementación
# debe forzar LC_ALL=C para interpretar Candidate sin traducción.
with patch.dict("os.environ", {"LANG": "es_ES.UTF-8", "LC_ALL": "es_ES.UTF-8"}):
    with patch("subprocess.run", side_effect=apt_simulated):
        assert mod.estado_actualizacion_app("deb", "2.0.6", APPID)["status"] == "available"

with patch("subprocess.run", return_value=process(
        out="  Installed: 2.0.6\n  Candidate: (none)\n")):
    assert mod.estado_actualizacion_app("deb", "2.0.6", APPID)["status"] == "unknown"

with patch("subprocess.run", return_value=process(
        out=f"{APPID}\n")):
    assert mod.estado_actualizacion_app("flatpak", "2.0.6", APPID)["status"] == "available"

with patch("subprocess.run", return_value=process(out="other.app\n")):
    assert mod.estado_actualizacion_app("flatpak", "2.0.6", APPID)["status"] == "current"

with patch("subprocess.run", return_value=process(1, err="Sin red")):
    assert mod.estado_actualizacion_app("flatpak", "2.0.6", APPID)["status"] == "unknown"

with patch.object(mod, "obtener_release_actualizacion",
                  return_value=("2.0.7", "x.AppImage", "url", "sha")):
    assert mod.estado_actualizacion_app("appimage", "2.0.6", APPID)["status"] == "available"
    assert mod.estado_actualizacion_app("appimage", "2.0.7", APPID)["status"] == "current"

with patch.object(mod, "obtener_release_actualizacion", side_effect=OSError("Sin red")):
    assert mod.estado_actualizacion_app("appimage", "2.0.6", APPID)["status"] == "unknown"

assert mod.estado_actualizacion_app("snap", "2.0.6", APPID)["status"] == "unsupported"
print("✔ Verificación de la versión de AiO: DEB, Flatpak, AppImage y errores")
