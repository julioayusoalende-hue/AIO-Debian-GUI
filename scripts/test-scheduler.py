#!/usr/bin/env python3
"""Planificación aislada: temporales y comandos simulados; nunca activa timers reales."""
import copy
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path('package/usr/lib/aio-debian-gui').resolve()))
from aio_core import scheduler as s, preflight

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
           {**base, 'tasks': ['autoremove']}, {**base, 'tasks': ['clock']},
           {**base, 'launcher': {'format': 'shell', 'path': '/tmp/run'}},
           {**base, 'launcher': {'format': 'appimage', 'path': 'relative.AppImage'}},
           {**base, 'launcher': {'format': 'deb', 'path': '/tmp/custom'}}]
for config in invalid:
    try:
        s.validate_config(config)
    except (ValueError, TypeError):
        pass
    else:
        raise AssertionError(config)
legacy = {key: value for key, value in base.items() if key != 'launcher'}
assert s.validate_config(legacy)['launcher'] is None
unit = s.timer_text('1000', base)
assert 'Persistent=true' in unit and 'WakeSystem=false' in unit
assert 'Unit=aio-debian-gui-maintenance@1000.service' in unit
for frequency in ('daily', 'weekly', 'monthly'):
    if Path('/usr/bin/systemd-analyze').exists():
        result = subprocess.run(['systemd-analyze', 'calendar', s.calendar({**base, 'frequency': frequency})], capture_output=True)
        assert result.returncode == 0, result.stderr
with patch.object(s.os, 'geteuid', return_value=1000):
    try:
        s.configure('1000', base)
    except PermissionError:
        pass
    else:
        raise AssertionError('Configuración sin privilegios aceptada')

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    helper = root/'usr/lib/aio-debian-gui/aio-debian-gui-helper'
    modules = helper.parent/'aio_core'
    service = root/'usr/lib/systemd/system/aio-debian-gui-maintenance@.service'
    modules.mkdir(parents=True)
    service.parent.mkdir(parents=True)
    shutil.copy('package/usr/lib/aio-debian-gui/aio-debian-gui-helper', helper)
    shutil.copy('package/usr/lib/systemd/system/aio-debian-gui-maintenance@.service', service)
    for name in ('__init__.py', 'scheduler.py', 'preflight.py'):
        shutil.copy(Path('package/usr/lib/aio-debian-gui/aio_core')/name, modules/name)
    with patch.multiple(s, HELPER=str(helper), SERVICE=service), \
         patch.object(s, 'host_supported', return_value=True), \
         patch.object(s.shutil, 'which', return_value='/usr/bin/systemctl'), \
         patch.object(Path, 'is_dir', return_value=True):
        assert s.available()
        (modules/'preflight.py').unlink()
        assert not s.available()
    shutil.copy('package/usr/lib/aio-debian-gui/aio_core/preflight.py', modules/'preflight.py')
    isolated = subprocess.run(
        [sys.executable, '-I', str(modules/'scheduler.py'), '--status', '1000'],
        cwd=root, capture_output=True, text=True, check=True)
    assert json.loads(isolated.stdout)['version'] == s.VERSION
    assert '/usr/lib/aio-debian-gui/aio_core/scheduler.py --run %i' in service.read_text()

with patch.object(Path, 'is_dir', return_value=True), \
     patch.object(Path, 'is_socket', return_value=True), \
     patch.object(s.shutil, 'which', side_effect=lambda name: f'/usr/bin/{name}'), \
     patch.object(s.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')) as notify:
    s._notify_success('1000')
    command = notify.call_args.args[0]
    assert command[:4] == ['/usr/bin/runuser', '-u', '1000', '--']
    assert 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus' in command
    assert command[-5:] == [
        '--app-name=AiO Debian GUI', '--urgency=normal', '--expire-time=10000',
        'Mantenimiento programado completado',
        'El mantenimiento programado se ha realizado correctamente.',
    ]
with patch.object(Path, 'is_dir', return_value=False), \
     patch.object(s.subprocess, 'run') as notify:
    s._notify_success('1000')
    notify.assert_not_called()

with patch.object(Path, 'is_dir', return_value=True), \
     patch.object(Path, 'is_socket', return_value=True), \
     patch.object(s.shutil, 'which', side_effect=lambda name: f'/usr/bin/{name}'), \
     patch.object(s.os, 'access', return_value=True), \
     patch.object(s.subprocess, 'run', return_value=SimpleNamespace(
         returncode=0, stdout='DISPLAY=:0\nWAYLAND_DISPLAY=wayland-0\n', stderr='')) as session_env, \
     patch.object(s.subprocess, 'Popen') as launch:
    s._launch_for_reboot('1000', {'format': 'deb', 'path': ''})
    assert session_env.call_count == 2
    command = session_env.call_args.args[0]
    assert command[:4] == ['/usr/bin/runuser', '-u', '1000', '--']
    assert '/usr/bin/aio-debian-gui' in command
    assert command[-1] == '--scheduled-reboot-required'
    assert '/usr/bin/systemd-run' in command
    assert '--setenv=DISPLAY=:0' in command and '--setenv=WAYLAND_DISPLAY=wayland-0' in command
    launch.assert_not_called()

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    with patch.multiple(s, CONFIG_DIR=root/'config', STATE_DIR=root/'state', UNIT_DIR=root/'units', LOCK=str(root/'run/maintenance.lock')), \
         patch.object(s.os, 'geteuid', return_value=0), \
         patch.object(s.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='test')), \
         patch.object(s, 'available', return_value=True), \
         patch.object(s, 'host_supported', return_value=True), \
         patch.object(s, '_systemctl', return_value='') as systemctl:
        config = {**base, 'enabled': True}
        s.configure('1000', config)
        path = s.CONFIG_DIR/'1000.json'
        assert json.loads(path.read_text()) == config
        assert path.stat().st_mode & 0o777 == 0o644
        assert (s.UNIT_DIR/s.timer_name('1000')).read_text() == s.timer_text('1000', config)
        assert any(call.args == ('enable', '--now', s.timer_name('1000')) for call in systemctl.call_args_list)
        s.configure('1000', base)
        with patch.object(s.shutil, 'which', return_value=None):
            try:
                s.configure('1000', {**config, 'tasks':['flatpak-update']})
            except RuntimeError:
                pass
            else:
                raise AssertionError('Flatpak ausente aceptado')
        assert systemctl.call_args.args == ('disable', '--now', s.timer_name('1000'))
        def fail_enable(*args):
            if args[0] == 'enable':
                raise RuntimeError('enable failed')
            return ''
        with patch.object(s, '_systemctl', side_effect=fail_enable):
            try:
                s.configure('1000', config)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Fallo de systemd ignorado')
        assert json.loads(path.read_text()) == base
        assert (s.UNIT_DIR/s.timer_name('1000')).read_text() == s.timer_text('1000', base)
        s.remove('1000')
        assert not path.exists() and not (s.UNIT_DIR/s.timer_name('1000')).exists()
        assert not any('stop' in call.args for call in systemctl.call_args_list)
        s._atomic(path, json.dumps(base))
        with patch.object(s.subprocess, 'run') as run:
            assert s.run_schedule('1000') == 0
            run.assert_not_called()
        s._atomic(path, json.dumps(config))
        class Process:
            def __init__(self, command, **kwargs):
                assert command[:4] == [s.HELPER, '--lang', 'C.UTF-8', '--lock-fd']
                assert '--upgrade-plan' in command
                assert kwargs['pass_fds'] == (int(command[4]),)
                assert kwargs['env']['PKEXEC_UID'] == '1000'
                fd = os.open(s.LOCK, os.O_WRONLY)
                try:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        pass
                    else:
                        raise AssertionError('Mantenimiento sin bloqueo global')
                finally:
                    os.close(fd)
                self.stdout = iter(['##REBOOT:1\n'] + ['##RESULT:' + t + ':0\n' for t in config['tasks']])
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def wait(self): return 0
        report = preflight.Report(False, [], [], 'a'*64)
        with patch.object(preflight, '_apt_locks', return_value=[]), \
             patch.object(preflight, '_check_local', return_value=report) as check, \
             patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=4*1024**3)), \
             patch.object(s.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run, \
             patch.object(s.subprocess, 'Popen', side_effect=Process) as popen, \
             patch.object(s, '_notify_success') as notify, \
             patch.object(s, '_launch_for_reboot') as launch:
            assert s.run_schedule('1000') == 0
            notify.assert_called_once_with('1000')
            launch.assert_called_once_with('1000', config['launcher'])
            result = s._read(s.STATE_DIR/'1000.json')
            assert result['status'] == 'success' and result['finished'] and result['reboot_required']
            assert all(v == 'success' for v in result['tasks'].values())
            assert run.call_args.args[0] == ['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update']
            with patch.object(preflight, '_check_local', return_value=preflight.Report(True, ['blocked'])):
                popen.reset_mock()
                notify.reset_mock()
                launch.reset_mock()
                assert s.run_schedule('1000') == 1
                popen.assert_not_called()
                notify.assert_not_called()
                launch.assert_not_called()
                assert s._read(s.STATE_DIR/'1000.json')['status'] == 'blocked'
            with patch.object(preflight, '_apt_locks', return_value=['/var/lib/dpkg/lock']):
                run.reset_mock()
                assert s.run_schedule('1000') == 0
                run.assert_not_called()
                assert s._read(s.STATE_DIR/'1000.json')['status'] == 'skipped'
            with patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=500*1024**2)):
                run.reset_mock()
                assert s.run_schedule('1000') == 1
                run.assert_not_called()
            run.return_value = SimpleNamespace(returncode=1)
            popen.reset_mock()
            assert s.run_schedule('1000') == 1
            popen.assert_not_called()
            run.return_value = SimpleNamespace(returncode=0)
            with patch.object(s.subprocess, 'Popen', side_effect=OSError('missing helper')):
                assert s.run_schedule('1000') == 1
                assert s._read(s.STATE_DIR/'1000.json')['status'] == 'error'
            fd = os.open(s.LOCK, os.O_WRONLY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                run.reset_mock()
                assert s.run_schedule('1000') == 0
                run.assert_not_called()
                assert s._read(s.STATE_DIR/'1000.json')['status'] == 'skipped'
            finally:
                os.close(fd)
        s._atomic(s.STATE_DIR/'1000.json', json.dumps({'status':'running', 'tasks':{}}))
        with patch.object(s, '_systemctl', return_value='inactive'):
            assert s.status('1000')['last_result']['status'] == 'interrupted'
print('Programación: validación, calendarios, permisos, persistencia, pausa, borrado, rollback, bloqueos, preflight y resultados OK')
