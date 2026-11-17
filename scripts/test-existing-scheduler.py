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

with mock.patch.object(integration, 'existing_scheduler', return_value=True), \
     mock.patch.object(integration, 'request_host_update') as update, \
     mock.patch.object(integration, 'install_host') as install:
    integration.prepare_host('flatpak', '2.10.15')
    update.assert_called_once_with('flatpak', '2.10.15')
    install.assert_not_called()

with mock.patch.object(integration, 'existing_scheduler', return_value=False), \
     mock.patch.object(integration, '_portable_repair_ready', return_value=False), \
     mock.patch.object(integration, 'request_host_update') as update, \
     mock.patch.object(integration, 'install_host') as install:
    integration.prepare_host('appimage', '2.10.15')
    update.assert_not_called()
    install.assert_not_called()


with mock.patch.object(integration, 'existing_scheduler', return_value=False), \
     mock.patch.object(integration, '_portable_repair_ready', return_value=True), \
     mock.patch.object(integration, 'request_host_update', return_value=True) as update, \
     mock.patch.object(integration, 'install_host') as install:
    integration.prepare_host('flatpak', '2.10.15')
    update.assert_called_once_with('flatpak', '2.10.15')
    install.assert_not_called()

native = subprocess.CompletedProcess([], 0, 'aio-debian-gui: /usr/lib/aio-debian-gui/aio-debian-gui-helper\n', '')
with mock.patch.object(integration.subprocess, 'run', return_value=native) as run:
    assert integration.request_host_update('appimage', '2.10.15') is False
    run.assert_called_once()

for formato in ('appimage', 'flatpak'):
    with mock.patch.object(integration.subprocess, 'run',
                           return_value=subprocess.CompletedProcess([], 1, '', '')) as run, \
         mock.patch.object(integration.subprocess, 'Popen') as spawn:
        integration.prepare_host(formato, '2.11.0')
        spawn.assert_not_called()
        assert all('pkexec' not in call.args[0] for call in run.call_args_list)
        assert run.call_count == 2
