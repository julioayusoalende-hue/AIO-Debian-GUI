"""Programación systemd con configuración validada y persistencia exclusiva de root."""
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
import subprocess
import sys
import tempfile

VERSION = '2.7.3'
CONFIG_DIR = Path('/etc/aio-debian-gui/schedules')
STATE_DIR = Path('/var/lib/aio-debian-gui/schedules')
UNIT_DIR = Path('/etc/systemd/system')
SERVICE = Path('/usr/lib/systemd/system/aio-debian-gui-maintenance@.service')
HELPER = '/usr/lib/aio-debian-gui/aio-debian-gui-helper'
LOCK = '/run/aio-debian-gui/maintenance.lock'
TASKS = ('upgrade', 'autoclean', 'flatpak-update', 'rebootcheck')
DAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
DEFAULT = {'enabled': False, 'frequency': 'weekly', 'weekday': 6,
           'hour': 10, 'minute': 0, 'tasks': ['upgrade', 'autoclean', 'rebootcheck'],
           'launcher': None}


def validate_uid(uid):
    value = str(uid)
    if not re.fullmatch(r'[1-9][0-9]{0,9}', value) or int(value) >= 2**32 - 1:
        raise ValueError('UID no válido.')
    return value


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


def timer_text(uid, config):
    uid = validate_uid(uid)
    return ('[Unit]\nDescription=AiO Debian GUI scheduled maintenance\n\n'
            '[Timer]\n' + f'OnCalendar={calendar(config)}\n'
            f'Unit=aio-debian-gui-maintenance@{uid}.service\n'
            'Persistent=true\nAccuracySec=1min\nWakeSystem=false\n\n'
            '[Install]\nWantedBy=timers.target\n')


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
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.aio-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _systemctl(*args):
    result = subprocess.run(['systemctl', *args], capture_output=True, text=True,
                            timeout=25, env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or 'systemctl falló.').strip()[-600:])
    return result.stdout.strip()


def host_supported():
    try:
        values = {}
        for line in Path('/etc/os-release').read_text().splitlines():
            key, _, value = line.partition('=')
            values[key] = value.strip().strip('"').strip("'")
        return values.get('ID') == 'debian' or (values.get('ID') == 'ubuntu' and values.get('VERSION_ID') in ('24.04', '26.04'))
    except OSError:
        return False


def available():
    modules = Path(HELPER).parent / 'aio_core'
    return bool(host_supported() and shutil.which('systemctl') and Path('/run/systemd/system').is_dir()
                and SERVICE.is_file() and Path(HELPER).is_file()
                and all((modules / name).is_file() for name in ('__init__.py', 'scheduler.py', 'preflight.py')))


def _require_root():
    if os.geteuid() != 0:
        raise PermissionError('Se necesita autorización de administrador.')


@contextmanager
def _settings_lock(uid):
    directory = Path(LOCK).parent
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd = os.open(directory / ('schedule-' + validate_uid(uid) + '.lock'),
                 os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def configure(uid, config):
    _require_root()
    uid = validate_uid(uid)
    config = validate_config(config)
    with _settings_lock(uid):
        _configure(uid, config)


def _configure(uid, config):
    _require_root()
    uid = validate_uid(uid)
    pwd.getpwuid(int(uid))
    config = validate_config(config)
    if not available():
        raise RuntimeError('La programación requiere systemd y la integración de AiO en el anfitrión.')
    if config['enabled'] and 'flatpak-update' in config['tasks'] and not shutil.which('flatpak'):
        raise RuntimeError('Flatpak no está instalado en el anfitrión.')
    path, unit = CONFIG_DIR / (uid + '.json'), UNIT_DIR / timer_name(uid)
    old_config = _read(path)
    if old_config is not None:
        old_config = validate_config(old_config)
    old_unit = unit.read_text() if unit.exists() else None
    try:
        _atomic(path, json.dumps(config) + '\n')
        _atomic(unit, timer_text(uid, config))
        _systemctl('daemon-reload')
        if config['enabled']:
            _systemctl('enable', '--now', timer_name(uid))
            # Reiniciar el temporizador aplica una nueva hora incluso si ya estaba activo.
            _systemctl('restart', timer_name(uid))
        else:
            _systemctl('disable', '--now', timer_name(uid))
    except (OSError, RuntimeError, subprocess.SubprocessError):
        # Detener el temporizador nuevo mientras su definición sigue disponible.
        with suppress(OSError, RuntimeError, subprocess.SubprocessError):
            _systemctl('disable', '--now', timer_name(uid))
        if old_config is None:
            path.unlink(missing_ok=True)
        else:
            _atomic(path, json.dumps(old_config) + '\n')
        if old_unit is None:
            unit.unlink(missing_ok=True)
        else:
            _atomic(unit, old_unit)
        _systemctl('daemon-reload')
        if old_config and old_config['enabled']:
            _systemctl('enable', '--now', timer_name(uid))
            _systemctl('restart', timer_name(uid))
        raise


def remove(uid):
    _require_root()
    uid = validate_uid(uid)
    with _settings_lock(uid):
        _remove(uid)


def _remove(uid):
    _require_root()
    uid = validate_uid(uid)
    unit = UNIT_DIR / timer_name(uid)
    if unit.exists():
        _systemctl('disable', '--now', timer_name(uid))
    (CONFIG_DIR / (uid + '.json')).unlink(missing_ok=True)
    unit.unlink(missing_ok=True)
    _systemctl('daemon-reload')


def status(uid):
    uid = validate_uid(uid)
    config = _read(CONFIG_DIR / (uid + '.json'))
    if config is not None:
        config = validate_config(config)
    last = _read(STATE_DIR / (uid + '.json'))
    result = {'version': VERSION, 'available': available(), 'config': config, 'last_result': last,
              'next_run': '', 'timer_active': False}
    if config and result['available']:
        try:
            result['timer_active'] = _systemctl('show', timer_name(uid), '--property=ActiveState', '--value') == 'active'
            result['next_run'] = _systemctl('show', timer_name(uid), '--property=NextElapseUSecRealtime', '--value')
            if last and last.get('status') == 'running':
                active = _systemctl('show', f'aio-debian-gui-maintenance@{uid}.service', '--property=ActiveState', '--value')
                if active not in ('active', 'activating'):
                    result['last_result'] = {**last, 'status': 'interrupted'}
        except (OSError, RuntimeError, subprocess.SubprocessError):
            pass
    return result


def _notify_success(uid):
    runtime = Path('/run/user') / uid
    bus = runtime / 'bus'
    notify_send = shutil.which('notify-send')
    runuser = shutil.which('runuser')
    if not runtime.is_dir() or not bus.is_socket():
        print('No hay una sesión de usuario activa para notificar el mantenimiento.', file=sys.stderr)
        return
    if not notify_send or not runuser:
        print('No se pudo notificar el mantenimiento: faltan notify-send o runuser.', file=sys.stderr)
        return
    command = [
        runuser, '-u', uid, '--', '/usr/bin/env',
        f'XDG_RUNTIME_DIR={runtime}',
        f'DBUS_SESSION_BUS_ADDRESS=unix:path={bus}',
        notify_send, '--app-name=AiO Debian GUI', '--urgency=normal',
        '--expire-time=10000', 'Mantenimiento programado completado',
        'El mantenimiento programado se ha realizado correctamente.',
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'No se pudo notificar el mantenimiento: {str(exc)[:300]}', file=sys.stderr)
        return
    if result.returncode:
        detail = (result.stderr or result.stdout or 'notify-send falló.').strip()[-300:]
        print(f'No se pudo notificar el mantenimiento: {detail}', file=sys.stderr)


def _launch_for_reboot(uid, launcher):
    runtime = Path('/run/user') / uid
    bus = runtime / 'bus'
    runuser = shutil.which('runuser')
    if not runtime.is_dir() or not bus.is_socket():
        print('No hay una sesión de usuario activa para abrir AiO.', file=sys.stderr)
        return
    if not runuser or launcher is None:
        print('No se pudo abrir AiO: falta runuser o la configuración del lanzador.', file=sys.stderr)
        return
    if launcher['format'] == 'deb':
        application = '/usr/bin/aio-debian-gui'
        if not os.access(application, os.X_OK):
            print('No se pudo abrir AiO: no está disponible el ejecutable DEB.', file=sys.stderr)
            return
        command = [application]
    elif launcher['format'] == 'flatpak':
        flatpak = shutil.which('flatpak')
        if not flatpak:
            print('No se pudo abrir AiO: Flatpak no está instalado.', file=sys.stderr)
            return
        command = [flatpak, 'run', 'io.github.julioayusoalende_hue.aio_debian_gui']
    else:
        application = launcher['path']
        if not os.access(application, os.X_OK):
            print('No se pudo abrir AiO: el AppImage configurado ya no está disponible.', file=sys.stderr)
            return
        command = [application]
    env = [f'XDG_RUNTIME_DIR={runtime}',
           f'DBUS_SESSION_BUS_ADDRESS=unix:path={bus}']
    try:
        session_env = subprocess.run(
            [runuser, '-u', uid, '--', '/usr/bin/env',
             f'XDG_RUNTIME_DIR={runtime}', f'DBUS_SESSION_BUS_ADDRESS=unix:path={bus}',
             'systemctl', '--user', 'show-environment'],
            capture_output=True, text=True, timeout=10, check=False)
        if session_env.returncode == 0:
            for line in session_env.stdout.splitlines():
                key, separator, value = line.partition('=')
                if separator and key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY',
                                         'XDG_CURRENT_DESKTOP', 'XDG_SESSION_TYPE',
                                         'XDG_DATA_DIRS'):
                    env.append(f'{key}={value}')
        result = subprocess.run(
            [runuser, '-u', uid, '--', '/usr/bin/env', *env, *command,
             '--scheduled-reboot-required'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'No se pudo abrir AiO para avisar del reinicio: {str(exc)[:300]}', file=sys.stderr)
        return
    if result.returncode:
        print(f'No se pudo iniciar AiO para avisar del reinicio (código {result.returncode}).',
              file=sys.stderr)


def run_schedule(uid):
    _require_root()
    uid = validate_uid(uid)
    config = _read(CONFIG_DIR / (uid + '.json'))
    if config is None or not validate_config(config)['enabled']:
        return 0
    pwd.getpwuid(int(uid))
    config = validate_config(config)
    result = {'started': datetime.now(timezone.utc).isoformat(), 'finished': None,
              'status': 'running', 'detail': '', 'reboot_required': False, 'tasks': {t: 'not-run' for t in config['tasks']}}
    path = STATE_DIR / (uid + '.json')

    def finish(state, detail):
        result.update(status=state, detail=detail, finished=datetime.now(timezone.utc).isoformat())
        _atomic(path, json.dumps(result) + '\n')
        if state == 'success':
            _notify_success(uid)
            if result['reboot_required']:
                _launch_for_reboot(uid, config.get('launcher'))
        return 0 if state in ('success', 'skipped') else 1

    if not host_supported():
        return finish('blocked', 'Sistema no compatible.')
    Path(LOCK).parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return finish('skipped', 'Ya hay otro mantenimiento de AiO en curso.')
        _atomic(path, json.dumps(result) + '\n')
        from aio_core import preflight
        if config['tasks'] != ['flatpak-update'] and preflight._apt_locks() != []:
            return finish('skipped', 'APT/dpkg ocupado o no se pudo comprobar su bloqueo.')
        if 'flatpak-update' in config['tasks'] and not shutil.which('flatpak'):
            return finish('blocked', 'Flatpak no está instalado en el anfitrión.')
        if shutil.disk_usage('/').free < 1024**3:
            return finish('blocked', 'Espacio insuficiente en /: menos de 1 GiB disponible.')
        if 'upgrade' in config['tasks']:
            update = subprocess.run(['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'], check=False)
            if update.returncode:
                return finish('blocked', 'No se pudieron actualizar los índices APT.')
        report = preflight._check_local(config['tasks'])
        if report.blocked:
            return finish('blocked', '\n'.join(report.messages)[:2000])
        command = [HELPER, '--lang', 'C.UTF-8', '--lock-fd', str(fd)]
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
                    _atomic(path, json.dumps(result) + '\n')
            code = process.wait()
        if code == 0 and all(v == 'success' for v in result['tasks'].values()):
            return finish('success', 'Mantenimiento completado.')
        return finish('error', 'El mantenimiento terminó con errores; revisa los resultados de las tareas.')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return finish('error', str(exc)[:600])
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('--status', '--configure', '--remove', '--run'))
    # Acciones con prefijo -- se analizan después de un separador de opciones.
    parser.add_argument('uid')
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
    # La ejecución aislada desde systemd no importa código del directorio actual.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
