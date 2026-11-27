#!/usr/bin/env python3
"""Build a signed scheduler payload before packaging either portable format."""
import base64
import importlib.machinery
import json
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
module = importlib.machinery.SourceFileLoader('portable_updater', str(root / 'portable/aio-portable-update')).load_module()
release = next(line.split(': ', 1)[1] for line in (root / 'package/DEBIAN/control').read_text().splitlines() if line.startswith('Version: '))
files = {name: base64.b64encode((root / 'package' / target.lstrip('/')).read_bytes()).decode() for name, target in module.FILES.items()}
# The portable service uses the shared update gate already used by the host package.
files['aio-debian-gui-maintenance@.service'] = base64.b64encode((root / 'host-package/usr/lib/systemd/system/aio-debian-gui-maintenance@.service').read_bytes()).decode()
# The helper queries scheduler.py as the desktop user. Its administrative
# commands already use aio-host-scheduler when that update gate is installed.
data = json.dumps({'version': release, 'files': files}, sort_keys=True).encode()
output = root / 'portable/payload.json'
with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / 'payload'
    signature = Path(tmp) / 'signature'
    source.write_bytes(data)
    fingerprint = subprocess.check_output(['gpg', '--show-keys', '--with-colons', str(root / 'package/usr/share/keyrings/aio-debian-gui.gpg')], text=True)
    fingerprint = next(line.split(':')[9] for line in fingerprint.splitlines() if line.startswith('fpr:'))
    args = ['gpg', '--batch', '--yes', '--local-user', fingerprint]
    if os.environ.get('GPG_PASSPHRASE'):
        args += ['--pinentry-mode', 'loopback', '--passphrase-fd', '0']
    subprocess.run([*args, '--detach-sign', '--output', str(signature), str(source)],
                   input=os.environ.get('GPG_PASSPHRASE', '').encode(), check=True)
    output.write_text(json.dumps({'data': base64.b64encode(data).decode(), 'signature': base64.b64encode(signature.read_bytes()).decode()}))
