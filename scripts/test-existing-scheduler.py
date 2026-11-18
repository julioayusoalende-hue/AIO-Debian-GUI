#!/usr/bin/env python3
"""The scheduler is staged and controlled as the desktop user in every format."""
import base64
import json
from pathlib import Path
import subprocess
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'package/usr/lib/aio-debian-gui'))
from aio_core import host_integration as integration, scheduler

helper = Path(__file__).resolve().parents[1] / 'package/usr/lib/aio-debian-gui/aio-debian-gui-helper'
assert integration.compatible_helper('appimage', str(helper)), \
    'The packaged maintenance helper must advertise the scheduler host protocol.'

report = {'available': True, 'version': scheduler.VERSION, 'protocol': scheduler.HOST_PROTOCOL,
          'config': dict(scheduler.DEFAULT), 'timer_active': False, 'last_result': None}

for fmt in ('deb', 'appimage', 'flatpak', 'snap', 'dev'):
    result = subprocess.CompletedProcess([], 0, json.dumps(report), '')
    with mock.patch.object(integration.subprocess, 'run', return_value=result) as run:
        actual = integration.run_user_scheduler(fmt, '--status', '1000')
    assert actual == report
    command = run.call_args.args[0]
    assert command[-3:] == ['-I', '-c', integration._USER_SCHEDULER_PROGRAM]
    assert (command[:2] == ['flatpak-spawn', '--host']) == (fmt == 'flatpak')
    request = json.loads(run.call_args.kwargs['input'])
    assert request['action'] == '--status' and request['uid'] == '1000'
    assert set(request['files']) == {'__init__.py', 'preflight.py', 'scheduler.py'}
    for name, file in request['files'].items():
        data = base64.b64decode(file['data'], validate=True)
        assert data == (Path(integration.__file__).parent/name).read_bytes()
        assert file['sha256']

config = {**scheduler.DEFAULT, 'enabled': True, 'tasks': ['flatpak-update']}
with mock.patch.object(integration.subprocess, 'run',
                       return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
    assert integration.run_user_scheduler('flatpak', '--configure', '1000', config) is None
    request = json.loads(run.call_args.kwargs['input'])
    assert request['config'] == scheduler.validate_config(config)
    assert request['action'] == '--configure'

for fmt, action, uid, config in (
    ('rpm', '--status', '1000', None),
    ('flatpak', '--schedule-save', '1000', None),
    ('appimage', '--remove', '0', None),
    ('deb', '--status', '1000', config),
):
    try:
        integration.run_user_scheduler(fmt, action, uid, config)
    except ValueError:
        pass
    else:
        raise AssertionError((fmt, action, uid, config))

with mock.patch.object(integration.subprocess, 'run',
                       return_value=subprocess.CompletedProcess([], 1, '', 'systemd user manager unavailable')):
    try:
        integration.run_user_scheduler('flatpak', '--status', '1000')
    except RuntimeError as error:
        assert 'systemd user manager unavailable' in str(error)
    else:
        raise AssertionError('Host scheduler failures must be surfaced')

print('User scheduler: host staging, no-privilege actions and DEB/AppImage/Flatpak dispatch OK')
