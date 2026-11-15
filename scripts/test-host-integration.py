#!/usr/bin/env python3
"""Integración portable: manifiestos, exportación y ciclo root simulado en temporales."""
import copy
from contextlib import ExitStack
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path('package/usr/lib/aio-debian-gui').resolve()))
from aio_core import host_integration as h

version = Path('package/DEBIAN/control').read_text().split('Version: ', 1)[1].splitlines()[0]
payload = h.build_payload('package', version)
assert set(payload['files']) == set(h.FILES)
for value in payload['files'].values():
    assert value['sha256'] == hashlib.sha256(value['content'].encode()).hexdigest()
for altered in (None, {}, {**payload, 'schema': True}, {**payload, 'version': '../1'},
                {**payload, 'command': 'bad'}, {**payload, 'files': {}}):
    try:
        h.validate_payload(altered)
    except ValueError:
        pass
    else:
        raise AssertionError(altered)
for name in ('../../etc/sudoers', '/usr/lib/aio-debian-gui/aio_core/preflight.py'):
    altered = copy.deepcopy(payload)
    altered['files'][name] = next(iter(altered['files'].values()))
    try:
        h.validate_payload(altered)
    except ValueError:
        pass
    else:
        raise AssertionError('Ruta no permitida aceptada')
altered = copy.deepcopy(payload)
next(iter(altered['files'].values()))['content'] += '\nchanged'
try:
    h.validate_payload(altered)
except ValueError:
    pass
else:
    raise AssertionError('SHA256 inválido aceptado')
assert h._trusted(SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644))
for uid, mode in ((1000, 0o644), (0, 0o666), (0, 0o4755)):
    assert not h._trusted(SimpleNamespace(st_uid=uid, st_mode=stat.S_IFREG | mode))
with patch.dict(os.environ, {'PKEXEC_UID': '0'}):
    try:
        h._uid()
    except PermissionError:
        pass
    else:
        raise AssertionError('UID root aceptado')

with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    bundle = directory/'bundle'
    assert h.main(['--build', 'package', version, str(bundle)]) == 0
    assert (bundle/'payload.json').stat().st_mode & 0o777 == 0o644
    assert (bundle/'host_integration.py').stat().st_mode & 0o777 == 0o644
    # La exportación debe usar /tmp aunque el anfitrión configure otro TMPDIR.
    with patch.dict(os.environ, {'TMPDIR': str(directory)}):
        staged = h.prepare(lambda *args: list(args), bundle)
    try:
        assert staged.startswith('/tmp/aio-debian-gui-host-')
        assert Path(staged).stat().st_mode & 0o777 == 0o700
        assert (Path(staged)/'payload.json').stat().st_mode & 0o777 == 0o600
        assert json.loads((Path(staged)/'payload.json').read_text()) == payload
        assert h.install_command(lambda *a: list(a), staged)[-2:] == ['--install', staged+'/payload.json']
        assert h.uninstall_command(lambda *a: list(a), staged)[-1] == '--uninstall'
    finally:
        h.cleanup(lambda *a: list(a), staged)
    assert not Path(staged).exists()
    with patch.object(h.subprocess, 'run', side_effect=subprocess.TimeoutExpired('host', 30)):
        try:
            h.prepare(lambda *a: list(a), bundle)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Fallo de exportación ignorado')
    for path in ('/', '/tmp', '/tmp/aio-debian-gui-host-../x'):
        try:
            h.cleanup(lambda *a: list(a), path)
        except ValueError:
            pass
        else:
            raise AssertionError('Limpieza de ruta no válida aceptada')

    manifest = bundle/'payload.json'
    caller = os.getuid()
    # Solo los destinos bajo este root temporal pueden modificarse.
    with ExitStack() as stack:
        stack.enter_context(patch.object(h, '_check_host'))
        stack.enter_context(patch.object(h, '_uid', return_value=caller))
        stack.enter_context(patch.object(h, '_trusted', return_value=True))
        stack.enter_context(patch.object(h.os, 'chown'))
        dpkg = stack.enter_context(patch.object(h, '_dpkg_owned', return_value=False))
        systemctl = stack.enter_context(patch.object(h, '_systemctl', return_value=''))
        root = directory/'fresh'
        root.mkdir()
        assert h.install(manifest, root)['managed_by'] == 'standalone'
        marker = json.loads((root/h.MARKER).read_text())
        assert marker['owner_uid'] == caller and marker['version'] == version
        for relative, mode in h.FILES.items():
            assert (root/relative).read_text() == payload['files'][relative]['content']
            assert (root/relative).stat().st_mode & 0o777 == mode
        assert all(call.args[0] in ('list-units', 'daemon-reload') for call in systemctl.call_args_list)
        # La misma versión es idempotente; una aplicación antigua no rebaja el servicio.
        assert h.install(manifest, root)['version'] == version
        older = copy.deepcopy(payload)
        older['version'] = '0.0.1'
        for name, entry in older['files'].items():
            if name.endswith('/aio-debian-gui-helper'):
                entry['content'] = entry['content'].replace('HELPER_VERSION=' + version, 'HELPER_VERSION=0.0.1')
            if name.endswith('/scheduler.py'):
                entry['content'] = re.sub(r"^VERSION = ['\"][^'\"]+['\"]$", "VERSION = '0.0.1'", entry['content'], flags=re.M)
            entry['sha256'] = hashlib.sha256(entry['content'].encode()).hexdigest()
        old_manifest = directory/'old-payload.json'
        old_manifest.write_text(json.dumps(h.validate_payload(older)))
        try:
            h.install(old_manifest, root)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Degradación de una integración más reciente aceptada')
        assert json.loads((root/h.MARKER).read_text())['version'] == version
        assert all(hashlib.sha256((root/name).read_bytes()).hexdigest() == entry['sha256']
                   for name, entry in payload['files'].items())
        # Una programación de cualquier UID impide retirar componentes compartidos.
        schedule = root/'etc/aio-debian-gui/schedules/99999.json'
        schedule.parent.mkdir(parents=True)
        schedule.write_text('{}')
        try:
            h.uninstall(root)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Retirada con programación ajena aceptada')
        schedule.unlink()
        target = root/next(iter(h.FILES))
        original = target.read_bytes()
        target.write_bytes(original+b'\n# admin change')
        for action in (lambda: h.install(manifest, root), lambda: h.uninstall(root)):
            try:
                action()
            except RuntimeError:
                pass
            else:
                raise AssertionError('Cambio del administrador sobrescrito')
        target.write_bytes(original)
        with patch.object(h, '_uid', return_value=caller+1):
            try:
                h.uninstall(root)
            except PermissionError:
                pass
            else:
                raise AssertionError('Retirada de integración de otro usuario aceptada')
        h.uninstall(root)
        assert not (root/h.MARKER).exists()
        assert all(not (root/p).exists() for p in h.FILES)

        # Adoptar un helper manual conserva una copia privada y la restaura al retirar.
        legacy = directory/'legacy'
        legacy.mkdir()
        relative = next(iter(h.FILES))
        h._atomic(legacy, relative, b'previous helper', 0o750)
        h.install(manifest, legacy)
        assert (legacy/h.BACKUP).stat().st_mode & 0o777 == 0o700
        assert (legacy/h.BACKUP/relative).read_bytes() == b'previous helper'
        h.uninstall(legacy)
        assert (legacy/relative).read_bytes() == b'previous helper'
        assert (legacy/relative).stat().st_mode & 0o777 == 0o750

        # El fallo de recarga revierte archivos, permisos y propiedad del marcador.
        failure = directory/'failure'
        failure.mkdir()
        h._atomic(failure, relative, b'original', 0o640)
        failed = [False]
        def fail_reload(*args):
            if args[0] == 'daemon-reload' and not failed[0]:
                failed[0] = True
                raise RuntimeError('reload failed')
            return ''
        with patch.object(h, '_systemctl', side_effect=fail_reload):
            try:
                h.install(manifest, failure)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Fallo de systemd ignorado')
        assert (failure/relative).read_bytes() == b'original'
        assert (failure/relative).stat().st_mode & 0o777 == 0o640
        assert not (failure/h.MARKER).exists()

        # Los archivos registrados por dpkg solo admiten una comprobación idéntica.
        deb = directory/'deb'
        deb.mkdir()
        for name, mode in h.FILES.items():
            h._atomic(deb, name, payload['files'][name]['content'].encode(), mode)
        with patch.object(h, '_dpkg_owned', return_value=True):
            assert h.install(manifest, deb)['managed_by'] == 'deb'
            assert not (deb/h.MARKER).exists()
            (deb/relative).write_bytes(b'deb version differs')
            try:
                h.install(manifest, deb)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Archivo dpkg sobrescrito')
            assert (deb/relative).read_bytes() == b'deb version differs'

        # Una ascendencia enlazada nunca permite leer, restaurar ni borrar fuera del root.
        unsafe = directory/'unsafe'
        unsafe.mkdir()
        outside = directory/'outside'
        outside.mkdir()
        sentinel = outside/'sentinel'
        sentinel.write_text('keep')
        (unsafe/'usr').symlink_to(outside, target_is_directory=True)
        try:
            h.install(manifest, unsafe)
        except PermissionError:
            pass
        else:
            raise AssertionError('Ascendencia symlink aceptada')
        assert sentinel.read_text() == 'keep' and list(outside.iterdir()) == [sentinel]

        active = directory/'active'
        active.mkdir()
        with patch.object(h, '_systemctl', return_value='active service'):
            try:
                h.install(manifest, active)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Actualización durante servicio activo aceptada')
        assert not (active/h.MARKER).exists()
print('Integración portable: manifiesto, SHA256, exportación, permisos, adopción, rollback, dpkg, retirada y rutas seguras OK')
