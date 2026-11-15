#!/usr/bin/env python3
"""Comprueba el bundle autónomo sin instalar paquetes ni alterar el anfitrión."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'package'
BUILDER = ROOT / 'scripts/build-host-integration.py'
INSTALLER = PACKAGE / 'usr/lib/aio-debian-gui/aio_core/host_integration.py'
FILES = {
    'usr/lib/aio-debian-gui/aio-debian-gui-helper',
    'usr/lib/aio-debian-gui/aio_core/__init__.py',
    'usr/lib/aio-debian-gui/aio_core/scheduler.py',
    'usr/lib/aio-debian-gui/aio_core/preflight.py',
    'usr/share/polkit-1/actions/es.aiodebian.gui.policy',
    'usr/lib/systemd/system/aio-debian-gui-maintenance@.service',
}

spec = importlib.util.spec_from_file_location('host_integration_builder', BUILDER)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
version = builder.package_version(PACKAGE)

with tempfile.TemporaryDirectory() as directory:
    temporary = Path(directory)
    outputs = [temporary / 'first', temporary / 'second']
    for output in outputs:
        subprocess.run([sys.executable, str(BUILDER), str(output)], check=True,
                       capture_output=True, text=True)
        assert (output / 'host_integration.py').read_bytes() == INSTALLER.read_bytes()
        data = json.loads((output / 'payload.json').read_text(encoding='utf-8'))
        assert set(data) == {'schema', 'version', 'files'}
        assert data['schema'] == 1 and data['version'] == version
        assert set(data['files']) == FILES, set(data['files'])
        for path, entry in data['files'].items():
            assert not path.startswith('/') and '..' not in Path(path).parts
            assert set(entry) == {'sha256', 'content'}, (path, entry.keys())
            encoded = entry['content'].encode('utf-8')
            assert hashlib.sha256(encoded).hexdigest() == entry['sha256'], path
            assert encoded == (PACKAGE / path).read_bytes(), path
        unit = data['files']['usr/lib/systemd/system/aio-debian-gui-maintenance@.service']['content']
        assert 'ExecStart=/usr/bin/python3 -I /usr/lib/aio-debian-gui/aio_core/scheduler.py --run %i' in unit
        assert '/app/' not in unit and 'APPDIR' not in unit and '/tmp/' not in unit
        assert not any(path.startswith(('etc/apt/', 'usr/bin/')) for path in data['files'])
    assert (outputs[0] / 'payload.json').read_bytes() == (outputs[1] / 'payload.json').read_bytes()
    assert (outputs[0] / 'host_integration.py').read_bytes() == (outputs[1] / 'host_integration.py').read_bytes()

    # Una actualización incoherente no debe producir un instalador parcialmente válido.
    fixture = temporary / 'fixture'
    for name in FILES | {'DEBIAN/control', 'usr/lib/aio-debian-gui/aio_core/host_integration.py'}:
        target = fixture / 'package' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PACKAGE / name, target)
    helper = fixture / 'package/usr/lib/aio-debian-gui/aio-debian-gui-helper'
    helper.write_text(helper.read_text().replace(f'HELPER_VERSION={version}', 'HELPER_VERSION=0.0.0', 1))
    output = temporary / 'invalid'
    result = subprocess.run([sys.executable, str(BUILDER), str(output), '--source-root', str(fixture)],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert not output.exists()

# Todos los formatos reciben la misma integración completa sin incluir un paquete DEB.
for name, output in (
    ('scripts/build-appimage.sh', '$APPDIR/usr/share/aio-debian-gui/host-integration'),
    ('scripts/build-deb.sh', '$STAGE/usr/share/aio-debian-gui/host-integration'),
    ('flatpak/io.github.julioayusoalende_hue.aio_debian_gui.yml', '/app/share/aio-debian-gui/host-integration'),
):
    source = (ROOT / name).read_text(encoding='utf-8')
    assert 'python3 scripts/build-host-integration.py' in source, name
    assert output in source, name
print('Bundle autónomo: runtime completo, rutas fijas, versiones, SHA-256, reproducibilidad y tres formatos OK')
