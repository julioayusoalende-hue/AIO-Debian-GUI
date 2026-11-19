#!/usr/bin/env python3
"""Comprobar el versionado de pruebas y su aislamiento del paquete estable."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent.parent


def run(*args, cwd, check=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    shutil.copytree(root / "package", work / "package")
    control = work / "package/DEBIAN/control"
    original = control.read_text()
    current = re.search(r"^Version: (?:\d+:)?(.+)$", original, re.M)
    if not current:
        raise RuntimeError("No se encontró la versión del paquete")
    control.write_text(re.sub(r"^Version: .+$", "Version: 1:1.0.3", original, count=1, flags=re.M))
    for path, old, new in [
        (work / "package/usr/lib/aio-debian-gui/aio_core/scheduler.py",
         f"VERSION = '{current[1]}'", "VERSION = '1.0.3'"),
        (work / "package/usr/lib/aio-debian-gui/aio-debian-gui-helper",
         f"HELPER_VERSION={current[1]}", "HELPER_VERSION=1.0.3"),
    ]:
        text = path.read_text()
        if text.count(old) != 1:
            raise RuntimeError(f"Versión incompatible en {path}")
        path.write_text(text.replace(old, new))
    (work / "CHANGELOG.md").write_text(
        "## 1.0.4\n\n- Novedades testing\n\n## 1.0.3\n\n- Novedades estables\n",
        encoding="utf-8",
    )
    (work / "scripts").mkdir()
    for name in ("build-deb.sh", "testing-version.sh"):
        shutil.copy(root / "scripts" / name, work / "scripts" / name)

    def version(tag, stable, number, attempt, check=True):
        return run("bash", "scripts/testing-version.sh", tag, stable, number, attempt,
                   cwd=work, check=check)

    assert version("v1.0.3", "1:1.0.3", "1", "1").stdout.strip() == "1.0.4~testing.1.1"
    assert version("v1.0.4", "1:1.0.4", "12", "2").stdout.strip() == "1.0.5~testing.12.2"
    for args in [("v1.0.3-rc1", "1:1.0.3", "1", "1"),
                 ("v1.0.3", "2:1.0.3", "1", "1"),
                 ("v1.0.3", "1:1.0.2", "1", "1"),
                 ("v1.0.3", "1:1.0.3", "0", "1")]:
        assert version(*args, check=False).returncode != 0

    before = (work / "package/DEBIAN/control").read_text()
    run("bash", "scripts/build-deb.sh", "--testing-version", "1.0.4~testing.1.1", cwd=work)
    deb = work / "dist/aio-debian-gui_1.0.4~testing.1.1_all.deb"
    assert run("dpkg-deb", "-f", str(deb), "Version", cwd=work).stdout.strip() == "1:1.0.4~testing.1.1"
    run("dpkg", "--compare-versions", "1:1.0.3", "lt", "1:1.0.4~testing.1.1", cwd=work)
    run("dpkg", "--compare-versions", "1:1.0.4~testing.1.1", "lt", "1:1.0.4~testing.2.1", cwd=work)
    run("dpkg", "--compare-versions", "1:1.0.4~testing.1.1", "lt", "1:1.0.4", cwd=work)
    run("dpkg-deb", "-x", str(deb), str(work / "extracted"), cwd=work)
    notes = work / "extracted/usr/share/aio-debian-gui/release-notes.txt"
    assert notes.read_text(encoding="utf-8") == "1.0.4~testing.1.1\n• Novedades testing\n"
    metainfo = next((work / "extracted/usr/share/metainfo").glob("*.metainfo.xml"))
    component = ET.parse(metainfo).getroot()
    assert component.findtext("project_license") == "GPL-3.0-or-later"
    assert component.findtext("launchable") == "aio-debian-gui.desktop"
    release = component.find("releases/release")
    assert release.get("version") == "1.0.4~testing.1.1"
    assert release.get("type") == "development"
    assert release.findtext("description/ul/li") == "Novedades testing"
    assert int(run("dpkg-deb", "-f", str(deb), "Installed-Size", cwd=work).stdout) > 0
    core = work / "extracted/usr/lib/aio-debian-gui"
    assert "VERSION = '1.0.4~testing.1.1'" in (core / "aio_core/scheduler.py").read_text()
    assert "HELPER_VERSION=1.0.4~testing.1.1" in (core / "aio-debian-gui-helper").read_text()
    assert (work / "package/DEBIAN/control").read_text() == before
    assert run("bash", "scripts/build-deb.sh", "--testing-version", "1.0.4", cwd=work, check=False).returncode != 0
    run("bash", "scripts/build-deb.sh", cwd=work)
    stable_deb = work / "dist/aio-debian-gui_1.0.3_all.deb"
    assert run("dpkg-deb", "-f", str(stable_deb), "Version", cwd=work).stdout.strip() == "1:1.0.3"
    run("dpkg-deb", "-x", str(stable_deb), str(work / "stable"), cwd=work)
    stable_metainfo = work / "stable/usr/share/metainfo" / metainfo.name
    stable_release = ET.parse(stable_metainfo).find("releases/release")
    assert stable_release.get("version") == "1.0.3" and stable_release.get("type") == "stable"
    assert stable_release.findtext("description/ul/li") == "Novedades estables"

print("✔ versionado testing y aislamiento del paquete estable")
