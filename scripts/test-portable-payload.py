#!/usr/bin/env python3
"""Real GPG verification plus simulated host updates and rollback."""
import base64
import importlib.machinery
import json
import os
import shutil
import sys
from pathlib import Path
import subprocess
import tempfile
from unittest import mock

root = Path(__file__).resolve().parents[1]
u = importlib.machinery.SourceFileLoader('portable', str(root / 'portable/aio-portable-update')).load_module()
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    home = tmp / 'gpg'
    home.mkdir(mode=0o700)
    env = {**os.environ, 'GNUPGHOME': str(home)}
    def gpg(*args):
        return subprocess.run(['gpg', '--batch', '--yes', *args], env=env, check=True, capture_output=True)
    gpg('--passphrase', '', '--quick-generate-key', 'Portable test <test@example.invalid>', 'ed25519', 'sign', '1d')
    key = tmp / 'key.gpg'
    key.write_bytes(gpg('--export').stdout)
    build = tmp / 'build'
    for directory in ('scripts', 'portable', 'package', 'host-package'):
        (build / directory).mkdir(parents=True)
    sources = ['scripts/build-portable-payload.py', 'portable/aio-portable-update',
               'package/DEBIAN/control',
               'host-package/usr/lib/systemd/system/aio-debian-gui-maintenance@.service']
    sources.extend('package' + target for target in u.FILES.values())
    for source in sources:
        target = build / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / source, target)
    keyring = build / 'package/usr/share/keyrings/aio-debian-gui.gpg'
    keyring.parent.mkdir(parents=True)
    shutil.copyfile(key, keyring)
    build_env = env.copy()
    build_env.pop('GPG_PASSPHRASE', None)
    subprocess.run([sys.executable, str(build / 'scripts/build-portable-payload.py')],
                   env=build_env, check=True, capture_output=True)
    _, bundled = u.verify((build / 'portable/payload.json').read_bytes(), key)
    helper = bundled['aio-debian-gui-helper']
    assert helper == (root / ('package' + u.FILES['aio-debian-gui-helper'])).read_bytes()
    # Exercise the read-only entry point of the signed helper against a local scheduler.
    scheduler = tmp / 'scheduler.py'
    scheduler.write_text('import sys\nprint(sys.argv[1])\n')
    helper = helper.replace(b'/usr/lib/aio-debian-gui/aio_core/scheduler.py', os.fsencode(scheduler))
    helper_path = tmp / 'bundled-helper'
    helper_path.write_bytes(helper)
    status = subprocess.run(['bash', str(helper_path), '--schedule-status'],
                            capture_output=True, check=True)
    assert status.stdout == b'--status\n'
    data = json.dumps({'version': '2.10.10', 'files': {name: base64.b64encode(('new ' + name).encode()).decode() for name in u.FILES}}).encode()
    payload = tmp / 'payload'
    payload.write_bytes(data)
    gpg('--detach-sign', str(payload))
    envelope = json.dumps({'data': base64.b64encode(data).decode(), 'signature': base64.b64encode(Path(str(payload) + '.sig').read_bytes()).decode()}).encode()
    assert u.verify(envelope, key)[0] == '2.10.10'
    altered = json.loads(envelope)
    altered['data'] = base64.b64encode(data.replace(b'2.10.10', b'2.10.99')).decode()
    try:
        u.verify(json.dumps(altered).encode(), key)
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('Tampered release accepted')
    targets = {name: str(tmp / name) for name in u.FILES}
    for target in targets.values():
        Path(target).write_bytes(b'old')
    state = tmp / 'version'
    state.write_text('2.10.9\n')
    real_verify = u.verify
    def command(args, **kw):
        if args[0].endswith('dpkg-query'):
            return subprocess.CompletedProcess(args, 1, '', 'dpkg-query: no path found matching pattern ' + args[-1])
        return subprocess.CompletedProcess(args, 0)
    real_lstat = os.lstat
    def root_stat(path, *a, **kw):
        result = list(real_lstat(path, *a, **kw)); result[4] = 0
        return os.stat_result(result)
    with mock.patch.object(u, 'FILES', targets), mock.patch.object(u, 'STATE', state), mock.patch.object(u, 'verify', side_effect=lambda data: real_verify(data, key)), mock.patch.object(u.subprocess, 'run', side_effect=command), mock.patch.object(u.os, 'lstat', side_effect=root_stat):
        # Signature validation itself uses subprocess.run, so supply verified resources here.
        with mock.patch.object(u, 'verify', return_value=('2.10.10', {name: ('new ' + name).encode() for name in targets})):
            u.apply(envelope)
            assert state.read_text() == '2.10.10\n'
            assert all(Path(target).read_bytes().startswith(b'new ') for target in targets.values())
            u.apply(envelope)  # Same version with intact files is a no-op.
            helper = Path(targets['aio-debian-gui-helper'])
            helper.unlink()
            u.apply(envelope)
            assert helper.read_bytes() == b'new aio-debian-gui-helper'
            assert helper.stat().st_mode & 0o111
            owner = subprocess.CompletedProcess([], 0, 'aio-debian-gui: ' + str(helper), '')
            with mock.patch.object(u.subprocess, 'run', return_value=owner):
                helper.write_bytes(b'deb-owned')
                u.apply(envelope)
                assert helper.read_bytes() == b'deb-owned'
            state.write_text('2.10.9\n')
            for target in targets.values():
                Path(target).write_bytes(b'old')
            before = {name: Path(target).read_bytes() for name, target in targets.items()}
            original = u.atomic
            calls = [0]
            def fail_once(path, *args):
                calls[0] += 1
                if calls[0] == 3:
                    raise OSError('injected write failure')
                return original(path, *args)
            with mock.patch.object(u, 'atomic', side_effect=fail_once):
                try:
                    u.apply(envelope)
                except OSError:
                    pass
                else:
                    raise AssertionError('Write failure swallowed')
            assert state.read_text() == '2.10.9\n'
            assert all(Path(target).read_bytes() == before[name] for name, target in targets.items())
print('✔ Portable payload: real signature, tampering, update, same-version, rollback')
