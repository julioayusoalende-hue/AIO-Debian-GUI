"""Programación systemd por usuario, sin instalar componentes privilegiados."""
import argparse
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile

VERSION = '2.12.0'
HOST_PROTOCOL = 2
_LEGACY_VERSIONS = frozenset(f'2.10.{patch}' for patch in range(12, 16))


def compatible_version(value):
    return isinstance(value, str) and (value == VERSION or value in _LEGACY_VERSIONS)


def compatible_host(report):
    if 'protocol' in report:
        return type(report['protocol']) is int and report['protocol'] == HOST_PROTOCOL
    return compatible_version(report.get('version'))


HOME = Path.home()
CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
STATE_HOME = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state'))
CONFIG_DIR = CONFIG_HOME / 'aio-debian-gui'
STATE_DIR = STATE_HOME / 'aio-debian-gui'
UNIT_DIR = CONFIG_HOME / 'systemd/user'
SERVICE = UNIT_DIR / 'aio-debian-gui-maintenance.service'
TIMER = UNIT_DIR / 'aio-debian-gui-maintenance.timer'
LOCK = STATE_DIR / 'maintenance.lock'
LEGACY_CONFIG_DIR = Path('/etc/aio-debian-gui/schedules')
LEGACY_STATE_DIR = Path('/var/lib/aio-debian-gui/schedules')
LEGACY_LOCK = Path('/run/aio-debian-gui/maintenance.lock')
SERVICE_NAME = 'aio-debian-gui-maintenance.service'
TIMER_NAME = 'aio-debian-gui-maintenance.timer'
PKEXEC = '/usr/bin/pkexec'
APT_GET = '/usr/bin/apt-get'
SNAP = '/usr/bin/snap'
NEEDRESTART = '/usr/sbin/needrestart'
TASKS = ('upgrade', 'autoclean', 'flatpak-update', 'snap-update', 'rebootcheck')
DAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
DEFAULT = {'enabled': False, 'frequency': 'weekly', 'weekday': 6,
           'hour': 10, 'minute': 0, 'tasks': ['upgrade', 'autoclean', 'rebootcheck'],
           'launcher': None}


def validate_uid(uid):
    value = str(uid)
    if not re.fullmatch(r'[1-9][0-9]{0,9}', value) or int(value) >= 2**32 - 1:
        raise ValueError('UID no válido.')
    return value


def _require_owner(uid):
    if int(validate_uid(uid)) != os.getuid():
        raise PermissionError('Solo puedes modificar tu propia programación.')


def _legacy_marker(uid):
    try:
        home = Path(pwd.getpwuid(int(validate_uid(uid))).pw_dir)
    except KeyError:
        raise ValueError('No se encontró la cuenta propietaria de la programación.')
    return home / '.config/aio-debian-gui/legacy-disabled'


def _legacy_disabled(uid):
    try:
        fd = os.open(_legacy_marker(uid), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return False
    try:
        info = os.fstat(fd)
        return (stat.S_ISREG(info.st_mode) and info.st_uid == int(validate_uid(uid))
                and info.st_mode & 0o077 == 0
                and os.read(fd, 16) == b'disabled\n')
    finally:
        os.close(fd)


def _disable_legacy(uid):
    _atomic(_legacy_marker(uid), 'disabled\n')


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError('Configuración de programación no válida.')
    if set(config) == set(DEFAULT) - {'launcher'}:
        config = {**config, 'launcher': None}
    if set(config) != set(DEFAULT):
        raise ValueError('Configuración de programación no válida.')
    if type(config['enabled']) is not bool or config['frequency'] not in ('daily', 'weekly', 'monthly'):
        raise ValueError('Frecuencia o activación no válida.')
    for key, maximum in (('weekday', 6), ('hour', 23), ('minute', 59)):
        if type(config[key]) is not int or not 0 <= config[key] <= maximum:
            raise ValueError('Día u hora no válidos.')
    tasks = config['tasks']
    if (not isinstance(tasks, list) or not tasks or len(tasks) > len(TASKS)
            or any(not isinstance(t, str) or t not in TASKS for t in tasks)
            or len(set(tasks)) != len(tasks)):
        raise ValueError('Selecciona al menos una tarea programable, sin duplicados.')
    launcher = config['launcher']
    if launcher is not None:
        if (not isinstance(launcher, dict) or set(launcher) != {'format', 'path'}
                or launcher['format'] not in ('deb', 'flatpak', 'appimage')
                or not isinstance(launcher['path'], str)):
            raise ValueError('Aplicación de aviso no válida.')
        if launcher['format'] == 'appimage':
            if not launcher['path'].startswith('/') or '\0' in launcher['path']:
                raise ValueError('Ruta de AppImage no válida.')
        elif launcher['path'] != '':
            raise ValueError('Ruta de aplicación no válida.')
    return {**config, 'tasks': [t for t in TASKS if t in tasks]}


def calendar(config):
    config = validate_config(config)
    time = f"{config['hour']:02}:{config['minute']:02}:00"
    if config['frequency'] == 'weekly':
        return f"{DAYS[config['weekday']]} *-*-* {time}"
    return f"*-*-{'01' if config['frequency'] == 'monthly' else '*'} {time}"


def timer_name(uid):
    return f'aio-debian-gui-maintenance-{validate_uid(uid)}.timer'


def timer_text(config, legacy_config=None):
    if legacy_config is not None:
        uid = validate_uid(config)
        config = validate_config(legacy_config)
        return ('[Unit]\nDescription=AiO Debian GUI scheduled maintenance\n\n'
                '[Timer]\n' + f'OnCalendar={calendar(config)}\n'
                f'Unit=aio-debian-gui-maintenance@{uid}.service\n'
                'Persistent=true\nAccuracySec=1min\nWakeSystem=false\n\n'
                '[Install]\nWantedBy=timers.target\n')
    return ('[Unit]\nDescription=AiO Debian GUI scheduled maintenance\n\n'
            '[Timer]\n' + f'OnCalendar={calendar(config)}\n'
            f'Unit={SERVICE_NAME}\n'
            'Persistent=true\nAccuracySec=1min\nWakeSystem=false\n\n'
            '[Install]\nWantedBy=timers.target\n')


def service_text():
    script = '%h/.local/share/aio-debian-gui/scheduler/aio_core/scheduler.py'
    return ('[Unit]\nDescription=AiO Debian GUI scheduled maintenance\n'
            'After=graphical-session.target\n\n'
            '[Service]\nType=oneshot\n'
            f'ExecStart=/usr/bin/python3 -I {script} --run %U\n'
            'TimeoutStartSec=2h\nNice=10\nUMask=0077\n'
            'StandardOutput=journal\nStandardError=journal\n')


def _read(path):
    try:
        with path.open(encoding='utf-8') as stream:
            text = stream.read(32769)
        if len(text) > 32768:
            raise ValueError('Archivo de programación demasiado grande.')
        return json.loads(text)
    except FileNotFoundError:
        return None


def _atomic(path, text):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.aio-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _systemctl(*args):
    result = subprocess.run(['systemctl', '--user', *args], capture_output=True, text=True,
                            timeout=25, env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or 'systemctl --user falló.').strip()[-600:])
    return result.stdout.strip()


def host_supported():
    try:
        values = {}
        for line in Path('/etc/os-release').read_text().splitlines():
            key, _, value = line.partition('=')
            values[key] = value.strip().strip('"').strip("'")
        return values.get('ID') == 'debian' or (
            values.get('ID') == 'ubuntu' and values.get('VERSION_ID') in ('24.04', '26.04'))
    except OSError:
        return False


def availability_error():
    if not host_supported():
        return 'El sistema del anfitrión no es compatible con el programador.'
    if not shutil.which('systemctl'):
        return 'El anfitrión no tiene systemctl disponible.'
    try:
        _systemctl('show-environment')
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return 'La sesión del usuario no tiene un gestor systemd activo.'
    return None


def available():
    return availability_error() is None


@contextmanager
def _settings_lock(uid):
    _require_owner(uid)
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(STATE_DIR / 'schedule.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def configure(uid, config):
    uid = validate_uid(uid)
    _require_owner(uid)
    config = validate_config(config)
    with _settings_lock(uid):
        _disable_legacy(uid)
        _configure(uid, config)


def _configure(uid, config):
    _require_owner(uid)
    config = validate_config(config)
    if not available():
        raise RuntimeError(availability_error() or 'systemd --user no está disponible.')
    if config['enabled'] and 'flatpak-update' in config['tasks'] and not shutil.which('flatpak'):
        raise RuntimeError('Flatpak no está instalado en este usuario.')
    path = CONFIG_DIR / 'schedule.json'
    old_config = _read(path)
    if old_config is not None:
        old_config = validate_config(old_config)
    old_timer = TIMER.read_text() if TIMER.exists() else None
    old_service = SERVICE.read_text() if SERVICE.exists() else None
    try:
        _atomic(path, json.dumps(config) + '\n')
        _atomic(SERVICE, service_text())
        _atomic(TIMER, timer_text(config))
        _systemctl('daemon-reload')
        if config['enabled']:
            _systemctl('enable', '--now', TIMER_NAME)
            _systemctl('restart', TIMER_NAME)
        else:
            _systemctl('disable', '--now', TIMER_NAME)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        with suppress(OSError, RuntimeError, subprocess.SubprocessError):
            _systemctl('disable', '--now', TIMER_NAME)
        if old_config is None:
            path.unlink(missing_ok=True)
        else:
            _atomic(path, json.dumps(old_config) + '\n')
        if old_timer is None:
            TIMER.unlink(missing_ok=True)
        else:
            _atomic(TIMER, old_timer)
        if old_service is None:
            SERVICE.unlink(missing_ok=True)
        else:
            _atomic(SERVICE, old_service)
        _systemctl('daemon-reload')
        if old_config and old_config['enabled']:
            _systemctl('enable', '--now', TIMER_NAME)
            _systemctl('restart', TIMER_NAME)
        raise


def remove(uid):
    uid = validate_uid(uid)
    _require_owner(uid)
    with _settings_lock(uid):
        _disable_legacy(uid)
        if TIMER.exists():
            _systemctl('disable', '--now', TIMER_NAME)
        (CONFIG_DIR / 'schedule.json').unlink(missing_ok=True)
        (STATE_DIR / 'schedule.json').unlink(missing_ok=True)
        SERVICE.unlink(missing_ok=True)
        TIMER.unlink(missing_ok=True)
        _systemctl('daemon-reload')


def status(uid):
    uid = validate_uid(uid)
    _require_owner(uid)
    config = _read(CONFIG_DIR / 'schedule.json')
    if config is None and not _legacy_disabled(uid):
        legacy = _read(LEGACY_CONFIG_DIR / (uid + '.json'))
        if legacy is not None:
            config = validate_config(legacy)
            configure(uid, config)
            old_result = _read(LEGACY_STATE_DIR / (uid + '.json'))
            if old_result is not None:
                _atomic(STATE_DIR / 'schedule.json', json.dumps(old_result) + '\n')
    if config is not None:
        config = validate_config(config)
    last = _read(STATE_DIR / 'schedule.json')
    result = {'version': VERSION, 'protocol': HOST_PROTOCOL, 'available': available(),
              'config': config, 'last_result': last,
              'next_run': '', 'timer_active': False}
    if not result['available']:
        result['availability_error'] = availability_error()
    if config and result['available']:
        try:
            result['timer_active'] = _systemctl(
                'show', TIMER_NAME, '--property=ActiveState', '--value') == 'active'
            result['next_run'] = _systemctl(
                'show', TIMER_NAME, '--property=NextElapseUSecRealtime', '--value')
            if last and last.get('status') == 'running':
                active = _systemctl('show', SERVICE_NAME, '--property=ActiveState', '--value')
                if active not in ('active', 'activating'):
                    result['last_result'] = {**last, 'status': 'interrupted'}
        except (OSError, RuntimeError, subprocess.SubprocessError):
            pass
    return result


def _run_admin(command):
    if not _trusted_system_command(PKEXEC):
        raise RuntimeError('No se encuentra pkexec para autorizar esta tarea del sistema.')
    result = subprocess.run([PKEXEC, *command], capture_output=True, text=True,
                            timeout=3600, check=False)
    output = (result.stdout or '') + (result.stderr or '')
    if output:
        print(output, end='' if output.endswith('\n') else '\n', flush=True)
    if result.returncode:
        raise RuntimeError((output.strip() or 'La tarea requiere autorización de administrador.')[-1200:])
    return output


def _trusted_system_command(path):
    try:
        info = os.stat(path)
        return (stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and info.st_mode & 0o022 == 0 and os.access(path, os.X_OK))
    except OSError:
        return False


def _run_task(task):
    if task == 'upgrade':
        _run_admin([APT_GET, '-o', 'APT::Update::Error-Mode=any', 'update'])
        _run_admin(['/usr/bin/env', 'DEBIAN_FRONTEND=noninteractive',
                    'APT_LISTCHANGES_FRONTEND=none', 'NEEDRESTART_MODE=l',
                    APT_GET, '-y', '-o', 'Dpkg::Use-Pty=0',
                    '-o', 'DPkg::options::=--force-confdef',
                    '-o', 'DPkg::options::=--force-confold', 'upgrade'])
    elif task == 'autoclean':
        _run_admin([APT_GET, 'autoclean'])
    elif task == 'flatpak-update':
        flatpak = shutil.which('flatpak')
        if not flatpak:
            raise RuntimeError('Flatpak no está instalado en este usuario.')
        for operation in (['update', '-y'], ['uninstall', '--unused', '-y']):
            result = subprocess.run([flatpak, '--user', *operation],
                                    capture_output=True, text=True, timeout=3600, check=False)
            output = result.stdout + result.stderr
            if output:
                print(output, end='' if output.endswith('\n') else '\n', flush=True)
            if result.returncode:
                raise RuntimeError((output.strip() or 'No se pudieron actualizar las aplicaciones Flatpak.')[-1200:])
    elif task == 'snap-update':
        if not _trusted_system_command(SNAP):
            raise RuntimeError('Snap no está instalado en el anfitrión.')
        _run_admin([SNAP, 'refresh'])
        listing = subprocess.run([SNAP, 'list', '--all'], capture_output=True,
                                 text=True, timeout=30, check=False)
        if listing.returncode:
            raise RuntimeError((listing.stderr or listing.stdout or 'No se pudieron consultar las revisiones Snap.')[-1200:])
        revisions = {}
        rows = []
        for line in listing.stdout.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 6:
                continue
            name, _version, revision = fields[:3]
            notes = fields[5:]
            if 'disabled' not in notes or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', name):
                continue
            if not re.fullmatch(r'[1-9][0-9]{0,9}', revision):
                continue
            revision_number = int(revision)
            revisions[name] = max(revisions.get(name, 0), revision_number)
            rows.append((name, revision, revision_number))
        for name, revision, number in rows:
            if number != revisions[name]:
                _run_admin([SNAP, 'remove', name, f'--revision={revision}'])
    elif task == 'rebootcheck':
        if not _trusted_system_command(NEEDRESTART):
            raise RuntimeError('needrestart no está instalado en el anfitrión.')
        output = _run_admin([NEEDRESTART, '-b'])
        if not output.strip():
            raise RuntimeError('needrestart no devolvió resultados.')
        if re.search(r'^NEEDRESTART-KSTA: [23]$', output, re.MULTILINE):
            return True
        if re.search(r'^NEEDRESTART-SVC: (dbus|dbus-broker|gdm|gdm3|lightdm|sddm|systemd-logind|systemd-udevd)\.service$',
                     output, re.MULTILINE):
            return True
        return Path('/var/run/reboot-required').is_file()
    return False


def _notify(title, body):
    notify_send = shutil.which('notify-send')
    if not notify_send:
        return
    try:
        subprocess.run([notify_send, '--app-name=AiO Debian GUI',
                        '--urgency=normal', '--expire-time=10000', title, body],
                       capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'No se pudo enviar la notificación: {str(exc)[:300]}', file=sys.stderr)


def _run_legacy_schedule(uid):
    config = _read(LEGACY_CONFIG_DIR / (uid + '.json'))
    if config is None or not validate_config(config)['enabled']:
        return 0
    config = validate_config(config)
    state_path = LEGACY_STATE_DIR / (uid + '.json')
    result = {'started': datetime.now(timezone.utc).isoformat(), 'finished': None,
              'status': 'running', 'detail': '', 'reboot_required': False,
              'tasks': {task: 'not-run' for task in config['tasks']}}

    def finish(state, detail):
        result.update(status=state, detail=detail, finished=datetime.now(timezone.utc).isoformat())
        _atomic(state_path, json.dumps(result) + '\n')
        return 0 if state in ('success', 'skipped') else 1

    if not host_supported():
        return finish('blocked', 'Sistema no compatible.')
    LEGACY_LOCK.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd = os.open(LEGACY_LOCK, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return finish('skipped', 'Ya hay otro mantenimiento de AiO en curso.')
        from aio_core import preflight
        if set(config['tasks']) - {'flatpak-update', 'snap-update'} and preflight._apt_locks() != []:
            return finish('skipped', 'APT/dpkg ocupado o no se pudo comprobar su bloqueo.')
        if 'flatpak-update' in config['tasks'] and not shutil.which('flatpak'):
            return finish('blocked', 'Flatpak no está instalado en el anfitrión.')
        if shutil.disk_usage('/').free < 1024**3:
            return finish('blocked', 'Espacio insuficiente en /: menos de 1 GiB disponible.')
        if 'upgrade' in config['tasks']:
            update = subprocess.run(
                ['/usr/bin/apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'], check=False)
            if update.returncode:
                return finish('blocked', 'No se pudieron actualizar los índices APT.')
        report = preflight._check_local(config['tasks'])
        if report.blocked:
            return finish('blocked', '\n'.join(report.messages)[:2000])
        command = ['/usr/lib/aio-debian-gui/aio-debian-gui-helper',
                   '--lang', 'C.UTF-8', '--lock-fd', str(fd)]
        if report.upgrade_plan:
            command += ['--upgrade-plan', report.upgrade_plan]
        command += config['tasks']
        environment = {**os.environ, 'PKEXEC_UID': uid, 'LC_ALL': 'C'}
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, env=environment, pass_fds=(fd,)) as process:
            for line in process.stdout:
                print(line, end='', flush=True)
                if line.strip() == '##REBOOT:1':
                    result['reboot_required'] = True
                match = re.fullmatch(r'##RESULT:([a-z-]+):([01])\n?', line)
                if match and match[1] in result['tasks']:
                    result['tasks'][match[1]] = 'success' if match[2] == '0' else 'error'
                    _atomic(state_path, json.dumps(result) + '\n')
            code = process.wait()
        if code == 0 and all(value == 'success' for value in result['tasks'].values()):
            return finish('success', 'Mantenimiento completado.')
        if result['tasks'].get('rebootcheck') == 'error':
            return finish('error', 'No se pudo comprobar si hace falta reiniciar; revisa needrestart y el journal.')
        return finish('error', 'El mantenimiento terminó con errores; revisa los resultados de las tareas.')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return finish('error', str(exc)[:600])
    finally:
        os.close(fd)


def run_schedule(uid):
    uid = validate_uid(uid)
    if os.geteuid() == 0:
        if _legacy_disabled(uid):
            return 0
        return _run_legacy_schedule(uid)
    _require_owner(uid)
    config = _read(CONFIG_DIR / 'schedule.json')
    if config is None or not validate_config(config)['enabled']:
        return 0
    config = validate_config(config)
    result = {'started': datetime.now(timezone.utc).isoformat(), 'finished': None,
              'status': 'running', 'detail': '', 'reboot_required': False,
              'tasks': {task: 'not-run' for task in config['tasks']}}
    path = STATE_DIR / 'schedule.json'

    def finish(state, detail):
        result.update(status=state, detail=detail, finished=datetime.now(timezone.utc).isoformat())
        _atomic(path, json.dumps(result) + '\n')
        if state == 'success':
            _notify('Mantenimiento programado completado',
                    'El mantenimiento programado se ha realizado correctamente.')
        if result['reboot_required']:
            _notify('Se recomienda reiniciar',
                    'El mantenimiento ha detectado cambios que requieren reiniciar el equipo.')
        return 0 if state in ('success', 'skipped') else 1

    if not host_supported():
        return finish('blocked', 'Sistema no compatible.')
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return finish('skipped', 'Ya hay otro mantenimiento programado en curso.')
        _atomic(path, json.dumps(result) + '\n')
        from aio_core import preflight
        if set(config['tasks']) & {'upgrade', 'autoclean'} and preflight._apt_locks() != []:
            return finish('skipped', 'APT/dpkg ocupado o no se pudo comprobar su bloqueo.')
        if (set(config['tasks']) & {'upgrade', 'autoclean', 'snap-update'}
                and shutil.disk_usage('/').free < 1024**3):
            return finish('blocked', 'Espacio insuficiente en /: menos de 1 GiB disponible.')
        report = preflight._check_local(config['tasks'])
        if report.blocked:
            return finish('blocked', '\n'.join(report.messages)[:2000])
        for task in config['tasks']:
            try:
                reboot_required = _run_task(task)
                result['tasks'][task] = 'success'
                result['reboot_required'] |= bool(reboot_required)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                result['tasks'][task] = 'error'
                result['detail'] = f'{task}: {str(exc)[:600]}'
            _atomic(path, json.dumps(result) + '\n')
        if all(value == 'success' for value in result['tasks'].values()):
            return finish('success', 'Mantenimiento completado.')
        if result['tasks'].get('rebootcheck') == 'error':
            return finish('error', 'No se pudo comprobar si hace falta reiniciar; revisa needrestart y el journal.')
        return finish('error', result['detail'] or 'El mantenimiento terminó con errores.')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return finish('error', str(exc)[:600])
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('--status', '--configure', '--remove', '--run'))
    parser.add_argument('uid', nargs='?', default=str(os.getuid()))
    parser.add_argument('config', nargs='?')
    args = parser.parse_args(['--', *(sys.argv[1:] if argv is None else argv)])
    if args.action == '--status':
        print(json.dumps(status(args.uid)))
    elif args.action == '--configure':
        configure(args.uid, json.loads(args.config or '{}'))
    elif args.action == '--remove':
        remove(args.uid)
    else:
        return run_schedule(args.uid)
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
