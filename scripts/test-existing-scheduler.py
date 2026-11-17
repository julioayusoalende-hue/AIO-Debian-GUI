#!/usr/bin/env python3
"""A compatible scheduler must never enter the privileged installer."""
import json
from pathlib import Path
import subprocess
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'package/usr/lib/aio-debian-gui'))
from aio_core import host_integration as integration, scheduler

report = {'available': True, 'version': scheduler.VERSION, 'config': dict(scheduler.DEFAULT)}
def result(data, code=0):
    return subprocess.CompletedProcess([], code, json.dumps(data), '')

assert not scheduler.compatible_version('2.10.10')
assert scheduler.compatible_version('2.10.12')
assert scheduler.compatible_host({'protocol': 1, 'version': '99.0.0'})
assert not scheduler.compatible_host({'protocol': 2, 'version': scheduler.VERSION})
assert scheduler.compatible_version(scheduler.VERSION)
assert not scheduler.compatible_version('2.10.9')
assert not scheduler.compatible_version(None)

for formato in ('appimage', 'flatpak'):
    with mock.patch.object(integration.subprocess, 'run', return_value=result(report)) as run, mock.patch.object(integration, '_resources') as resources, mock.patch.object(integration, '_privileged') as privileged:
        integration.install_host(formato)
        resources.assert_not_called()
        privileged.assert_not_called()
        command = run.call_args.args[0]
        assert command[-2:] == ['/usr/lib/aio-debian-gui/aio-debian-gui-helper', '--schedule-status']
        assert (command[:2] == ['flatpak-spawn', '--host']) == (formato == 'flatpak')
    for invalid in ({**report, 'version': '0.0.1'}, {**report, 'available': False}, {**report, 'available': 'yes'}, {**report, 'config': {'enabled': True}}, [], None):
        with mock.patch.object(integration.subprocess, 'run', return_value=result(invalid)):
            assert not integration.existing_scheduler(formato), invalid
    with mock.patch.object(integration.subprocess, 'run', side_effect=FileNotFoundError):
        assert not integration.existing_scheduler(formato)
    with mock.patch.object(integration.subprocess, 'run', return_value=result(report, code=1)):
        assert not integration.existing_scheduler(formato)
    with mock.patch.object(integration.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'invalid json', '')):
        assert not integration.existing_scheduler(formato)
print('✔ Compatible host scheduler reused; missing, obsolete and invalid reports rejected')

with mock.patch.object(integration.subprocess, 'run', return_value=result({**report, 'version': scheduler.VERSION})), mock.patch.object(integration, '_resources') as resources:
    integration.install_host('appimage')
    resources.assert_not_called()

with mock.patch.object(integration, 'request_host_update') as update, \
     mock.patch.object(integration, 'install_host') as install:
    integration.prepare_host('flatpak', '2.11.3')
    update.assert_called_once_with('flatpak', '2.11.3')
    install.assert_not_called()

helper = '/usr/lib/aio-debian-gui/aio-debian-gui-helper'
module = '/usr/lib/aio-debian-gui/aio_core/__init__.py'
for package in ('aio-debian-gui', 'aio-debian-gui-host'):
    # dpkg may own only one of the resources that blocks portable installation.
    ownership = subprocess.CompletedProcess([], 1, f'{package}: {module}\n',
        f'dpkg-query: no path found matching pattern {helper}\n')
    with mock.patch.object(integration.subprocess, 'run', return_value=ownership), \
         mock.patch.object(integration, '_request_legacy_host_update', return_value=True) as legacy:
        assert integration.request_host_update('flatpak', '2.11.3') is (package == 'aio-debian-gui-host')
        assert legacy.called is (package == 'aio-debian-gui-host')
    with mock.patch.object(integration, 'existing_scheduler', return_value=False), \
         mock.patch.object(integration.subprocess, 'run', return_value=ownership), \
         mock.patch.object(integration, '_request_legacy_host_update', return_value=True), \
         mock.patch.object(integration, '_privileged') as privileged:
        try:
            integration.install_host('flatpak')
        except RuntimeError as exc:
            assert ('actualización firmada' if package == 'aio-debian-gui-host' else 'gestor de software') in str(exc)
        else:
            raise AssertionError('A packaged scheduler must not invoke the portable installer')
        privileged.assert_not_called()
