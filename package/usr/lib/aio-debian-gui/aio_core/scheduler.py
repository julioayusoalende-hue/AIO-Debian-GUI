"""Programación systemd con configuración validada y persistencia exclusiva de root."""
import argparse
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
import fcntl
from html import escape
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile

VERSION = '1.2.2'


HOST_PROTOCOL = 1
_LEGACY_VERSIONS = frozenset(f'2.10.{patch}' for patch in range(12, 16))


def compatible_version(value):
    """Recognize hosts released before the protocol was explicitly advertised."""
    return isinstance(value, str) and (value == VERSION or value in _LEGACY_VERSIONS)


def compatible_host(report):
    if 'protocol' in report:
        return type(report['protocol']) is int and report['protocol'] == HOST_PROTOCOL
    return compatible_version(report.get('version'))


CONFIG_DIR = Path('/etc/aio-debian-gui/schedules')
STATE_DIR = Path('/var/lib/aio-debian-gui/schedules')
UNIT_DIR = Path('/etc/systemd/system')
SERVICE = Path('/usr/lib/systemd/system/aio-debian-gui-maintenance@.service')
HELPER = '/usr/lib/aio-debian-gui/aio-debian-gui-helper'
LOCK = '/run/aio-debian-gui/maintenance.lock'
USER_RUNTIME_DIR = Path('/run/user')
HISTORY_LIMIT = 100
# Identificador del arranque actual: caduca el aviso de reinicio al reiniciar.
BOOT_ID_FILE = Path('/proc/sys/kernel/random/boot_id')
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


def _read(path, limit=32768):
    try:
        with path.open(encoding='utf-8') as stream:
            text = stream.read(limit + 1)
        if len(text) > limit:
            raise ValueError('Archivo de programación demasiado grande.')
        return json.loads(text)
    except FileNotFoundError:
        return None


def _atomic(path, text, owner=None):
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.aio-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if owner is not None and os.geteuid() == 0:
            os.chown(temporary, owner, -1)
        os.chmod(temporary, 0o644 if owner is None else 0o400)
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


def maintenance_distro(values):
    distro = values.get('ID')
    if distro in ('debian', 'ayusos'):
        return 'debian'
    if distro == 'ubuntu' and values.get('VERSION_ID') in ('24.04', '26.04'):
        return 'ubuntu'
    return None


def host_supported():
    try:
        values = {}
        for line in Path('/etc/os-release').read_text().splitlines():
            key, _, value = line.partition('=')
            values[key] = value.strip().strip('"').strip("'")
        return maintenance_distro(values) is not None
    except OSError:
        return False


def availability_error():
    if not host_supported():
        return 'El sistema del anfitrión no es compatible con el programador.'
    if not shutil.which('systemctl') or not Path('/run/systemd/system').is_dir():
        return 'El anfitrión no tiene systemd disponible.'
    modules = Path(HELPER).parent / 'aio_core'
    for path in (SERVICE, Path(HELPER), *(modules / name for name in ('__init__.py', 'scheduler.py', 'preflight.py'))):
        if not path.is_file() or not os.access(path, os.R_OK):
            return 'No se puede leer el archivo del programador: ' + str(path)
    return None


def available():
    return availability_error() is None


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


def mensaje_error(texto):
    """Limita el texto de diagnóstico antes de guardarlo o mostrarlo."""
    return "".join(c for c in texto if c.isprintable() or c in "\n\t").strip()[:2000]


def registrar_salida_error(mensajes, linea):
    if linea.startswith(("[-] ", "E: ", "error: ", "Error: ")):
        mensaje = mensaje_error(linea[4:] if linea.startswith("[-] ") else linea)[:480]
        if mensaje and mensaje not in mensajes:
            mensajes.append(mensaje)
            del mensajes[:-4]


def _history_paths(uid):
    directory = STATE_DIR / (uid + '.history')
    return sorted(directory.glob('*.json'), reverse=True)


def _archive_result(uid, result, preserve=False):
    # Root owns the directory. Only the corresponding user can read each file.
    # Rotation uses file names; root never reads the user-owned files.
    directory = STATE_DIR / (uid + '.history')
    stamp = datetime.fromisoformat(result['started']).strftime('%Y%m%dT%H%M%S%f')
    path = directory / (stamp + '.json')
    if not preserve or not path.exists():
        _atomic(path, json.dumps(result) + '\n', owner=int(uid))
    for path in _history_paths(uid)[HISTORY_LIMIT:]:
        path.unlink(missing_ok=True)


def _history(uid):
    entries = []
    for path in _history_paths(uid)[:HISTORY_LIMIT]:
        try:
            entry = _read(path, limit=131072)
        except (OSError, ValueError):
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def status(uid, include_history=False):
    uid = validate_uid(uid)
    config = _read(CONFIG_DIR / (uid + '.json'))
    if config is not None:
        config = validate_config(config)
    last = _read(STATE_DIR / (uid + '.json'))
    result = {'version': VERSION, 'protocol': HOST_PROTOCOL, 'available': available(),
              'config': config, 'last_result': last,
              'next_run': '', 'timer_active': False}
    if not result['available']:
        result['availability_error'] = availability_error()
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
    if include_history:
        result['history'] = _history(uid)
    return result


def _notify_success(uid):
    uid = validate_uid(uid)
    runtime = USER_RUNTIME_DIR / uid
    bus = runtime / 'bus'
    notify_send = shutil.which('notify-send')
    runuser = shutil.which('runuser')
    if not runtime.is_dir() or not bus.is_socket():
        print('No hay una sesión de usuario activa para notificar el mantenimiento.', file=sys.stderr)
        return
    if not notify_send or not runuser:
        print('No se pudo notificar el mantenimiento: faltan notify-send o runuser.', file=sys.stderr)
        return
    try:
        username = pwd.getpwuid(int(uid)).pw_name
    except KeyError:
        print(f'No se pudo notificar el mantenimiento: no existe el usuario con UID {uid}.', file=sys.stderr)
        return
    command = [
        runuser, '-u', username, '--', '/usr/bin/env',
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


# Se ejecuta como el usuario, en una unidad independiente del trabajo de mantenimiento.
_NOTIFICATION_ACTION = """\
import subprocess
import sys

sender, title, body, *launcher = sys.argv[1:]
try:
    result = subprocess.run(
        [sender, '--app-name=AiO Debian GUI', '--urgency=normal',
         '--expire-time=300000', '--action=open=Abrir AiO Debian',
         title, body],
        capture_output=True, text=True, check=False, timeout=310,
    )
    if result.returncode == 0 and result.stdout.strip() == 'open':
        subprocess.run(launcher, check=False)
except (OSError, subprocess.SubprocessError) as error:
    print(f'No se pudo completar la notificación: {error}', file=sys.stderr)
"""


def _notify_incomplete(uid, launcher, result):
    names = {
        'upgrade': 'Actualizar los paquetes del sistema',
        'autoclean': 'Limpiar la caché de paquetes',
        'flatpak-update': 'Actualizar aplicaciones Flatpak',
        'snap-update': 'Actualizar aplicaciones Snap',
        'rebootcheck': 'Comprobar si hace falta reiniciar',
    }
    lines = [escape(result['detail'][:320])]
    for task, status in result['tasks'].items():
        if status != 'success':
            label = 'Error' if status == 'error' else 'Pendiente'
            lines.append(f'• {names[task]} · {label}')
    lines.append('Abre AiO Debian para revisar el resultado y ejecutar el mantenimiento manual.')
    _launch_in_session(uid, launcher, notification=(
        'Mantenimiento programado incompleto', '\n'.join(lines)))


def _launch_for_reboot(uid, launcher):
    _launch_in_session(uid, launcher)


def boot_id():
    """Identificador del arranque actual; vacío si no se puede leer."""
    try:
        return BOOT_ID_FILE.read_text(encoding='utf-8').strip()[:64]
    except OSError:
        return ''


def avisar_reinicio_una_vez(uid, launcher, result):
    """Abre AiO para el aviso de reinicio como mucho una vez por arranque.

    Sin la marca, cada ejecución programada vuelve a abrir la aplicación
    mientras el equipo siga pendiente de reiniciar. Devuelve True solo cuando
    se lanza la apertura en esta llamada.
    """
    uid = validate_uid(uid)
    if not isinstance(result, dict) or not result.get('reboot_required'):
        return False
    marca = STATE_DIR / (uid + '.reinicio-avisado')
    actual = boot_id()
    try:
        anterior = _read(marca, limit=128)
    except (OSError, ValueError):
        anterior = None
    if actual and anterior == actual:
        return False
    _launch_for_reboot(uid, launcher)
    if actual:
        try:
            _atomic(marca, json.dumps(actual) + '\n', owner=int(uid))
        except OSError as error:
            print(f'No se pudo recordar el aviso de reinicio: {error}', file=sys.stderr)
    return True


def _launch_in_session(uid, launcher, notification=None):
    uid = validate_uid(uid)
    runtime = USER_RUNTIME_DIR / uid
    bus = runtime / 'bus'
    runuser = shutil.which('runuser')
    if not runtime.is_dir() or not bus.is_socket():
        print('No hay una sesión de usuario activa para abrir AiO.', file=sys.stderr)
        return
    if not runuser:
        print('No se pudo abrir AiO: falta runuser.', file=sys.stderr)
        return
    try:
        username = pwd.getpwuid(int(uid)).pw_name
    except KeyError:
        print(f'No se pudo abrir AiO: no existe el usuario con UID {uid}.', file=sys.stderr)
        return
    env = [f'XDG_RUNTIME_DIR={runtime}',
           f'DBUS_SESSION_BUS_ADDRESS=unix:path={bus}']
    try:
        deb = '/usr/bin/aio-debian-gui'
        flatpak = shutil.which('flatpak')
        app_id = 'io.github.julioayusoalende_hue.aio_debian_gui'
        preferred = launcher['format'] if launcher else 'deb'
        if preferred == 'appimage' and os.access(launcher['path'], os.X_OK):
            command = [launcher['path']]
        elif preferred == 'deb' and os.access(deb, os.X_OK):
            command = [deb]
        else:
            installed = flatpak and subprocess.run(
                [runuser, '-u', username, '--', flatpak, 'info', app_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            ).returncode == 0
            if installed:
                command = [flatpak, 'run', app_id]
            elif os.access(deb, os.X_OK):
                command = [deb]
            else:
                print('No se encontró una edición instalada de AiO para abrir.', file=sys.stderr)
                return
        session_env = subprocess.run(
            [runuser, '-u', username, '--', '/usr/bin/env',
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
        if not any(value.startswith(('DISPLAY=', 'WAYLAND_DISPLAY=')) for value in env):
            print('No hay una sesión gráfica disponible para abrir AiO.', file=sys.stderr)
            return
        systemd_run = shutil.which('systemd-run')
        if not systemd_run:
            print('No se pudo abrir AiO: falta systemd-run.', file=sys.stderr)
            return
        launch = [runuser, '-u', username, '--', '/usr/bin/env', *env,
                  systemd_run, '--user', '--no-block', '--collect']
        launch.extend('--setenv=' + value for value in env)
        if notification:
            notify_send = shutil.which('notify-send')
            if not notify_send:
                print('No se pudo notificar el mantenimiento: falta notify-send.', file=sys.stderr)
                return
            launch.extend(['--', '/usr/bin/python3', '-c', _NOTIFICATION_ACTION,
                           notify_send, *notification, *command])
        else:
            launch.extend(['--', *command, '--scheduled-reboot-required'])
        result = subprocess.run(launch, capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            detail = (result.stderr or result.stdout or 'systemd-run falló.').strip()[-300:]
            print(f'No se pudo ejecutar la acción de AiO: {detail}', file=sys.stderr)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'No se pudo ejecutar la acción de AiO: {str(exc)[:300]}', file=sys.stderr)


def run_schedule(uid):
    _require_root()
    uid = validate_uid(uid)
    config = _read(CONFIG_DIR / (uid + '.json'))
    if config is None or not validate_config(config)['enabled']:
        return 0
    pwd.getpwuid(int(uid))
    config = validate_config(config)
    errors = {}
    result = {'started': datetime.now(timezone.utc).isoformat(), 'finished': None,
              'status': 'running', 'detail': '', 'reboot_required': False, 'tasks': {t: 'not-run' for t in config['tasks']}}
    path = STATE_DIR / (uid + '.json')

    def archive_previous():
        previous = _read(path)
        if isinstance(previous, dict) and previous.get('finished') and previous.get('started'):
            _archive_result(uid, previous, preserve=True)

    def finish(state, detail, private_detail=""):
        archive_previous()
        result.update(status=state, detail=detail, finished=datetime.now(timezone.utc).isoformat())
        _archive_result(uid, {**result, 'errors': errors,
                              'detail': private_detail or detail})
        _atomic(path, json.dumps(result) + '\n')
        if state == 'success':
            _notify_success(uid)
        else:
            _notify_incomplete(uid, config.get('launcher'), result)
        avisar_reinicio_una_vez(uid, config.get('launcher'), result)
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
        archive_previous()
        _atomic(path, json.dumps(result) + '\n')
        from aio_core import preflight
        if set(config['tasks']) - {'flatpak-update', 'snap-update'} and preflight._apt_locks() != []:
            return finish('skipped', 'APT/dpkg ocupado o no se pudo comprobar su bloqueo.')
        if 'flatpak-update' in config['tasks'] and not shutil.which('flatpak'):
            return finish('blocked', 'Flatpak no está instalado en el anfitrión.')
        if shutil.disk_usage('/').free < 1024**3:
            return finish('blocked', 'Espacio insuficiente en /: menos de 1 GiB disponible.')
        if 'upgrade' in config['tasks']:
            update = subprocess.run(['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, errors='replace', check=False)
            output = update.stdout or ''
            if output:
                print(output, end='', flush=True)
            if update.returncode:
                detail = 'No se pudieron actualizar los índices APT.'
                return finish('blocked', detail, detail + '\n' + mensaje_error(output[-1600:]))
        report = preflight._check_local(config['tasks'])
        if report.blocked:
            return finish('blocked', '\n'.join(report.messages)[:2000])
        command = [HELPER, '--lang', 'C.UTF-8', '--lock-fd', str(fd)]
        if report.upgrade_plan:
            command += ['--upgrade-plan', report.upgrade_plan]
        command += config['tasks']
        environment = {**os.environ, 'PKEXEC_UID': uid, 'LC_ALL': 'C'}
        messages = []
        active = None
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, errors='replace', env=environment, pass_fds=(fd,)) as process:
            for line in process.stdout:
                print(line, end='', flush=True)
                if line.startswith('##STEP:'):
                    step = line.split(':', 3)[1]
                    active = config['tasks'][int(step) - 1] if (
                        step.isdecimal() and 0 < int(step) <= len(config['tasks'])) else None
                    messages.clear()
                registrar_salida_error(messages, line)
                if line.strip() == '##REBOOT:1':
                    result['reboot_required'] = True
                match = re.fullmatch(r'##RESULT:([a-z-]+):([012])\n?', line)
                if match and match[1] in result['tasks']:
                    task, code = match.groups()
                    result['tasks'][task] = {'0': 'success', '1': 'error', '2': 'not-run'}[code]
                    if code == '1' and messages:
                        errors[task] = mensaje_error('\n'.join(messages))
                    active = None
                    messages.clear()
                    _atomic(path, json.dumps(result) + '\n')
            code = process.wait()
        if active:
            result['tasks'][active] = 'error'
            if messages:
                errors[active] = mensaje_error('\n'.join(messages))
        if code == 0 and all(v == 'success' for v in result['tasks'].values()):
            return finish('success', 'Mantenimiento completado.')
        if result['tasks'].get('rebootcheck') == 'error':
            return finish('error', 'No se pudo comprobar si hace falta reiniciar; revisa needrestart y el journal.')
        return finish('error', 'El mantenimiento terminó con errores; revisa los resultados de las tareas.',
                      mensaje_error('\n'.join(messages)) if not active else '')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return finish('error', str(exc)[:600])
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('--status', '--history', '--configure', '--remove', '--run'))
    # Acciones con prefijo -- se analizan después de un separador de opciones.
    parser.add_argument('uid')
    parser.add_argument('config', nargs='?')
    args = parser.parse_args(['--', *(sys.argv[1:] if argv is None else argv)])
    if args.action in ('--status', '--history'):
        print(json.dumps(status(args.uid, include_history=args.action == '--history')))
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
