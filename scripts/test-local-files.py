#!/usr/bin/env python3
"""Pruebas de los archivos locales del gestor: .flatpakref (validación, instalación) y .deb."""
import hashlib
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "ayusos-control-center/package/usr/lib/aio-debian-gui/extensions/ayusos"))
from software_manager import admin, backend
from software_manager.manager import SoftwareManagerPage

REF = (b"[Flatpak Ref]\nTitle=GIMP\nName=org.gimp.GIMP\nBranch=stable\n"
       b"Url=https://dl.flathub.org/repo/\nIsRuntime=false\n"
       b"RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo\nGPGKey=AAAA\n")

fields = admin.parse_flatpakref(REF)
assert fields == {'Title': 'GIMP', 'Name': 'org.gimp.GIMP', 'Branch': 'stable',
                  'Url': 'https://dl.flathub.org/repo/',
                  'RuntimeRepo': 'https://dl.flathub.org/repo/flathub.flatpakrepo'}, fields

for invalid in (
    b"no es un ini",
    REF.replace(b"https://dl.flathub.org/repo/\n", b"http://dl.flathub.org/repo/\n"),
    REF.replace(b"Name=org.gimp.GIMP", b"Name=../evil"),
    REF.replace(b"Name=org.gimp.GIMP", b"Name=gimp"),
    REF.replace(b"IsRuntime=false", b"IsRuntime=true"),
    REF.replace(b"Branch=stable", b"Branch=st able;rm"),
    REF.replace(b"RuntimeRepo=https://", b"RuntimeRepo=file://"),
    b"\xff\xfe" + REF,
    REF + b"#" * admin.FLATPAKREF_MAX,
):
    try:
        admin.parse_flatpakref(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f'.flatpakref aceptado: {invalid[:60]!r}')

with tempfile.TemporaryDirectory() as directory:
    ref = Path(directory) / 'GIMP.flatpakref'
    ref.write_bytes(REF)
    data, digest, preview = backend.preview_flatpakref(str(ref))
    assert data == REF and digest == hashlib.sha256(REF).hexdigest() and preview == fields
    other = Path(directory) / 'GIMP.txt'
    other.write_bytes(REF)
    try:
        backend.preview_flatpakref(str(other))
    except ValueError:
        pass
    else:
        raise AssertionError('Extensión no comprobada')

    # Usuario: flatpak --user install --from <temporal con el mismo contenido>.
    seen = []
    def fake_run(command, stdin=None, timeout=None):
        seen.append((command, Path(command[-1]).read_bytes() if command[-1].endswith('.flatpakref') else stdin.read()))
        return ''
    with patch.object(backend, 'run', fake_run):
        backend.install_flatpakref(REF, backend.flatpak('user', 'install', '-y', '--noninteractive', '--from'))
        backend.install_flatpakref(REF, ['/usr/bin/pkexec', backend.ADMIN, 'install-flatpakref', digest])
    assert seen[0][0][:6] == ['/usr/bin/flatpak', '--user', 'install', '-y', '--noninteractive', '--from']
    assert seen[0][1] == REF
    assert seen[1][0] == ['/usr/bin/pkexec', backend.ADMIN, 'install-flatpakref', digest]
    assert seen[1][1] == REF

# Sistema: admin.py comprueba el resumen y llama a flatpak --system install --from.
calls = []
def fake_call(command, **kwargs):
    calls.append((command, Path(command[-1]).read_bytes()))
    return 0
class Stdin:
    def __init__(self, data):
        self.buffer = io.BytesIO(data)
with patch.object(admin.os, 'geteuid', return_value=0), \
     patch.object(admin.subprocess, 'call', fake_call), \
     patch.object(admin.tempfile, 'TemporaryDirectory', lambda dir=None, _real=tempfile.TemporaryDirectory: _real()):
    with patch.object(admin.sys, 'stdin', Stdin(REF)):
        assert admin.main(['install-flatpakref', hashlib.sha256(REF).hexdigest()]) == 0
    assert calls[0][0][:6] == ['/usr/bin/flatpak', '--system', 'install', '-y', '--noninteractive', '--from']
    assert calls[0][1] == REF
    with patch.object(admin.sys, 'stdin', Stdin(REF + b"\n")):
        try:
            admin.main(['install-flatpakref', hashlib.sha256(REF).hexdigest()])
        except ValueError:
            pass
        else:
            raise AssertionError('Archivo modificado aceptado')
    assert len(calls) == 1

# Arrastrar y soltar / argumento: tipo por extensión y solo URIs locales.
assert SoftwareManagerPage.local_kind('/tmp/a.DEB') == 'deb'
assert SoftwareManagerPage.local_kind('/tmp/a.flatpakref') == 'flatpakref'
assert SoftwareManagerPage.local_kind('/tmp/a.flatpakrepo') is None
page = SoftwareManagerPage.__new__(SoftwareManagerPage)
assert page.dropped_files([
    'file:///home/u/Descargas/Mi%20App.flatpakref',
    'file://localhost/tmp/p.deb',
    'https://example.org/x.flatpakref',
    'file://otro-equipo/tmp/p.deb',
    'file:///tmp/notas.txt',
]) == ['/home/u/Descargas/Mi App.flatpakref', '/tmp/p.deb']
opened = []
page.open_local_flatpakref = lambda f: opened.append(('ref', f))
page.open_local_deb = lambda f: opened.append(('deb', f))
page.open_local_file('/tmp/x.flatpakref')
page.open_local_file('/tmp/x.deb')
assert opened == [('ref', '/tmp/x.flatpakref'), ('deb', '/tmp/x.deb')]

# El helper acepta la operación nueva en modo sin contraseña.
helper = (root / 'package/usr/lib/aio-debian-gui/aio-debian-gui-helper').read_text()
assert '|install-flatpakref|' in helper
desktop = (root / 'package/usr/share/applications/aio-debian-gui.desktop').read_text()
assert 'application/vnd.flatpak.ref;' in desktop
print('archivos locales: OK')
