#!/usr/bin/env python3
"""User-level scheduling tests; no real user units or privileged commands are run."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path('package/usr/lib/aio-debian-gui').resolve()))
from aio_core import scheduler as s

base = copy.deepcopy(s.DEFAULT)
assert s.calendar(base) == 'Sun *-*-* 10:00:00'
assert s.calendar({**base, 'frequency': 'daily', 'hour': 0, 'minute': 5}) == '*-*-* 00:05:00'
assert s.calendar({**base, 'frequency': 'monthly'}) == '*-*-01 10:00:00'
for uid in ('0', '-1', '../1000', '1000\n', '01', '4294967295'):
    try:
        s.validate_uid(uid)
    except ValueError:
        pass
    else:
        raise AssertionError(uid)
invalid = [None, {}, {**base, 'extra': 'bad'}, {**base, 'hour': True},
           {**base, 'hour': 24}, {**base, 'minute': -1}, {**base, 'weekday': 7},
           {**base, 'enabled': 'yes'}, {**base, 'frequency': 'daily\nExecStart=bad'},
           {**base, 'tasks': []}, {**base, 'tasks': ['upgrade', 'upgrade']},
           {**base, 'tasks': ['backports-kernel-mesa']}, {**base, 'tasks': ['reboot']},
           {**base, 'tasks': ['upgrade; reboot']}, {**base, 'tasks': ['repos']},
           {**base, 'launcher': {'format': 'shell', 'path': '/tmp/run'}},
           {**base, 'launcher': {'format': 'appimage', 'path': 'relative.AppImage'}}]
for config in invalid:
    try:
        s.validate_config(config)
    except (ValueError, TypeError):
        pass
    else:
        raise AssertionError(config)
assert 'Persistent=true' in s.timer_text(base)
assert f'Unit={s.SERVICE_NAME}' in s.timer_text(base)
assert 'systemctl --user' not in s.service_text()
assert '--run %U' in s.service_text()
for frequency in ('daily', 'weekly', 'monthly'):
    if Path('/usr/bin/systemd-analyze').exists():
        result = subprocess.run(['systemd-analyze', 'calendar', s.calendar({**base, 'frequency': frequency})],
                                capture_output=True)
        assert result.returncode == 0, result.stderr

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    config_dir, state_dir, unit_dir = root/'config', root/'state', root/'units'
    service, timer = unit_dir/'aio-debian-gui-maintenance.service', unit_dir/'aio-debian-gui-maintenance.timer'
    home = root/'home'
    home.mkdir()
    with patch.multiple(s, CONFIG_DIR=config_dir, STATE_DIR=state_dir, UNIT_DIR=unit_dir,
                        SERVICE=service, TIMER=timer, LOCK=state_dir/'maintenance.lock'), \
         patch.object(s.os, 'getuid', return_value=1000), \
         patch.object(s.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir=str(home))), \
         patch.object(s, 'available', return_value=True), \
         patch.object(s, 'host_supported', return_value=True), \
         patch.object(s.shutil, 'which', side_effect=lambda name: f'/usr/bin/{name}'), \
         patch.object(s, '_systemctl', return_value='') as systemctl:
        config = {**base, 'enabled': True}
        s.configure('1000', config)
        path = config_dir/'schedule.json'
        assert json.loads(path.read_text()) == config
        assert path.stat().st_mode & 0o777 == 0o600
        assert timer.read_text() == s.timer_text(config)
        assert service.read_text() == s.service_text()
        assert ('--now', s.TIMER_NAME) in [call.args[-2:] for call in systemctl.call_args_list
                                          if call.args[0] == 'enable']

        config_unavailable = {**config, 'enabled': False}
        with patch.object(s, 'available', return_value=False):
            try:
                s.configure('1000', config_unavailable)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Configuración sin systemd --user aceptada')

        with patch.object(s.os, 'getuid', return_value=1001):
            try:
                s.configure('1000', base)
            except PermissionError:
                pass
            else:
                raise AssertionError('Se permitió modificar la programación de otro usuario')

        def fail_enable(*args):
            if args[0] == 'enable':
                raise RuntimeError('enable failed')
            return ''
        with patch.object(s, '_systemctl', side_effect=fail_enable):
            try:
                s.configure('1000', {**config, 'hour': 11})
            except RuntimeError:
                pass
            else:
                raise AssertionError('Fallo de systemd ignorado')
        assert json.loads(path.read_text()) == config
        assert timer.read_text() == s.timer_text(config)

        with patch.object(s, '_systemctl', return_value=''):
            s.configure('1000', base)
            with patch.object(s.shutil, 'which', return_value=None):
                try:
                    s.configure('1000', {**config, 'tasks': ['flatpak-update']})
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('Flatpak ausente aceptado')
            s.remove('1000')
        assert not path.exists() and not timer.exists() and not service.exists()
        assert not (state_dir/'schedule.json').exists()
        assert (home/'.config/aio-debian-gui/legacy-disabled').read_text() == 'disabled\n'

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    home = root/'home'
    config_dir, state_dir, unit_dir = root/'config', root/'state', root/'units'
    config_dir.mkdir()
    legacy = root/'etc/aio-debian-gui/schedules'
    legacy.mkdir(parents=True)
    legacy_config = {**base, 'enabled': True, 'tasks': ['rebootcheck']}
    (legacy/'1000.json').write_text(json.dumps(legacy_config))
    with patch.multiple(s, CONFIG_DIR=config_dir, STATE_DIR=state_dir, UNIT_DIR=unit_dir,
                        SERVICE=unit_dir/'aio-debian-gui-maintenance.service',
                        TIMER=unit_dir/'aio-debian-gui-maintenance.timer',
                        LOCK=state_dir/'maintenance.lock', LEGACY_CONFIG_DIR=legacy,
                        LEGACY_STATE_DIR=root/'legacy-state'), \
         patch.object(s.os, 'getuid', return_value=1000), \
         patch.object(s.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir=str(home))), \
         patch.object(s, 'available', return_value=True), \
         patch.object(s, '_systemctl', return_value=''):
        migrated = s.status('1000')
        assert migrated['config'] == legacy_config
        assert json.loads((config_dir/'schedule.json').read_text()) == legacy_config
        assert (home/'.config/aio-debian-gui/legacy-disabled').read_text() == 'disabled\n'
        with patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s, '_legacy_disabled', return_value=True), \
             patch.object(s, '_run_legacy_schedule') as old_run:
            assert s.run_schedule('1000') == 0
            old_run.assert_not_called()
        s.remove('1000')
        assert not (config_dir/'schedule.json').exists()
        assert (home/'.config/aio-debian-gui/legacy-disabled').exists()

with patch.object(s, '_run_admin') as admin:
    admin.assert_not_called()
    with patch.object(s.shutil, 'which', return_value='/usr/bin/flatpak'), \
         patch.object(s.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as flatpak:
        s._run_task('flatpak-update')
        assert flatpak.call_count == 2
        assert flatpak.call_args_list[0].args[0] == ['/usr/bin/flatpak', '--user', 'update', '-y']
        assert flatpak.call_args_list[1].args[0] == [
            '/usr/bin/flatpak', '--user', 'uninstall', '--unused', '-y']
    admin.assert_not_called()
    with patch.object(s, '_trusted_system_command', return_value=True):
        s._run_task('upgrade')
    assert admin.call_count == 2
    assert admin.call_args_list[0].args[0][-1] == 'update'
    assert admin.call_args_list[1].args[0][-1] == 'upgrade'
    assert 'dist-upgrade' not in admin.call_args_list[1].args[0]
    admin.reset_mock()
    with patch.object(s, '_trusted_system_command', return_value=True), \
         patch.object(s.subprocess, 'run',
                      return_value=subprocess.CompletedProcess([], 0, 'Name Version Rev Tracking Publisher Notes\n', '')):
        s._run_task('snap-update')
    admin.assert_called_once_with([s.SNAP, 'refresh'])

with tempfile.TemporaryDirectory() as directory:
    state_dir = Path(directory)/'state'
    config_dir = Path(directory)/'config'
    config_dir.mkdir()
    state_dir.mkdir()
    config = {**base, 'enabled': True, 'tasks': ['flatpak-update', 'rebootcheck']}
    (config_dir/'schedule.json').write_text(json.dumps(config))
    with patch.multiple(s, CONFIG_DIR=config_dir, STATE_DIR=state_dir, LOCK=state_dir/'maintenance.lock'), \
         patch.object(s.os, 'getuid', return_value=1000), \
    patch.object(s.os, 'geteuid', return_value=1000), \
         patch.object(s, 'host_supported', return_value=True), \
         patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=4*1024**3)), \
         patch.object(s, '_systemctl', return_value=''), \
         patch('aio_core.preflight._apt_locks', return_value=[]), \
         patch('aio_core.preflight._check_local', return_value=SimpleNamespace(blocked=False, messages=[])), \
         patch.object(s, '_run_task', side_effect=[False, True]) as task, \
         patch.object(s, '_notify') as notify:
        assert s.run_schedule('1000') == 0
        assert task.call_args_list[0].args == ('flatpak-update',)
        assert task.call_args_list[1].args == ('rebootcheck',)
        result = json.loads((state_dir/'schedule.json').read_text())
        assert result['status'] == 'success' and result['reboot_required']
        assert result['tasks'] == {'flatpak-update': 'success', 'rebootcheck': 'success'}
        assert notify.call_count == 2

with patch.object(s.os, 'getuid', return_value=1000), \
     patch.object(s.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir='/tmp')):
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(s, 'STATE_DIR', Path(directory)), \
             patch.object(s, '_systemctl', return_value='inactive'), \
             patch.object(s, 'available', return_value=True):
            report = s.status('1000')
            assert report['available'] and report['config'] is None

print('User scheduler: calendars, validation, user ownership, units, rollback, persistence and task authorization OK')
