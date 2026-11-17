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

assert scheduler.compatible_version('2.10.10') == (scheduler.VERSION == '2.10.11')
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
