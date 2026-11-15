"""Integración persistente del programador para AppImage y Flatpak.

La instalación se autoriza mediante pkexec Python y no crea reglas sin contraseña.
El manifiesto solo describe seis destinos fijos; nunca contiene órdenes ni rutas libres.
"""
import argparse
import ast
from contextlib import contextmanager
import configparser
import fcntl
import hashlib
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
from xml.etree import ElementTree

FILES = {
    'usr/lib/aio-debian-gui/aio-debian-gui-helper': 0o755,
    'usr/lib/aio-debian-gui/aio_core/__init__.py': 0o644,
    'usr/lib/aio-debian-gui/aio_core/scheduler.py': 0o644,
    'usr/lib/aio-debian-gui/aio_core/preflight.py': 0o644,
    'usr/share/polkit-1/actions/es.aiodebian.gui.policy': 0o644,
    'usr/lib/systemd/system/aio-debian-gui-maintenance@.service': 0o644,
}
MARKER = 'var/lib/aio-debian-gui/host-integration.json'
BACKUP = 'var/lib/aio-debian-gui/host-integration-backup'
MAX_FILE = 256 * 1024
MAX_PAYLOAD = 1024 * 1024
SYSTEM_PATH = '/usr/sbin:/usr/bin:/sbin:/bin'
SERVICE_NAME = 'aio-debian-gui-maintenance@*.service'


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', value):
        raise ValueError('Versión de integración no válida.')
    return value


def _uid():
    value = os.environ.get('PKEXEC_UID', '')
    if not re.fullmatch(r'[1-9][0-9]{0,9}', value) or int(value) >= 2**32 - 1:
        raise PermissionError('No se pudo identificar al usuario que autorizó la integración.')
    pwd.getpwuid(int(value))
    return int(value)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _trusted(st):
    return st.st_uid == 0 and not stat.S_IMODE(st.st_mode) & 0o7022


def _read_file(path, limit=MAX_PAYLOAD, owner=None, trusted=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            raise ValueError('Archivo de integración no válido.')
        if owner is not None and st.st_uid not in (owner, 0):
            raise PermissionError('El archivo no pertenece al usuario que autorizó la integración.')
        if trusted and not _trusted(st):
            raise PermissionError('La integración existente no está protegida por root.')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Archivo de integración demasiado grande.')
        return data, st
    finally:
        os.close(fd)


def _check_sources(payload):
    files, version = payload['files'], payload['version']
    helper = files['usr/lib/aio-debian-gui/aio-debian-gui-helper']['content']
    if not helper.startswith('#!/bin/bash\n') or not re.search(
            r'^HELPER_VERSION=' + re.escape(version) + r'$', helper, re.M):
        raise ValueError('La versión del asistente no coincide con la integración.')
    for name in FILES:
        if name.endswith('.py'):
            tree = ast.parse(files[name]['content'], filename=name)
            if name.endswith('/scheduler.py'):
                versions = [node.value.value for node in tree.body
                            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                            and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in node.targets)]
                if versions != [version]:
                    raise ValueError('La versión del programador no coincide con la integración.')
    policy = ElementTree.fromstring(files['usr/share/polkit-1/actions/es.aiodebian.gui.policy']['content'])
    actions = policy.findall('action')
    if (policy.tag != 'policyconfig' or len(actions) != 1 or actions[0].get('id') != 'es.aiodebian.gui.mantenimiento'
            or actions[0].findtext('defaults/allow_any') != 'no'
            or actions[0].findtext('defaults/allow_inactive') != 'no'
            or actions[0].findtext('defaults/allow_active') != 'auth_admin'):
        raise ValueError('Política de autorización de integración no válida.')
    annotations = {a.get('key'): a.text for a in actions[0].findall('annotate')}
    if annotations.get('org.freedesktop.policykit.exec.path') != '/usr/lib/aio-debian-gui/aio-debian-gui-helper':
        raise ValueError('La política no corresponde al asistente del anfitrión.')
    service = configparser.ConfigParser(interpolation=None, strict=True)
    service.read_string(files['usr/lib/systemd/system/aio-debian-gui-maintenance@.service']['content'])
    expected = {
        'Unit': {'description': 'AiO Debian GUI scheduled maintenance for UID %i',
                 'wants': 'network-online.target', 'after': 'network-online.target'},
        'Service': {'type': 'oneshot',
                    'execstart': '/usr/bin/python3 -I /usr/lib/aio-debian-gui/aio_core/scheduler.py --run %i',
                    'timeoutstartsec': 'infinity', 'nice': '10',
                    'ioschedulingclass': 'best-effort', 'ioschedulingpriority': '7',
                    'umask': '0022', 'standardoutput': 'journal', 'standarderror': 'journal'},
    }
    if service.defaults() or set(service.sections()) != set(expected) or any(
            dict(service[section]) != values for section, values in expected.items()):
        raise ValueError('Servicio de mantenimiento no válido.')


def validate_payload(payload):
    if (not isinstance(payload, dict) or set(payload) != {'schema', 'version', 'files'}
            or type(payload['schema']) is not int or payload['schema'] != 1
            or not isinstance(payload['files'], dict) or set(payload['files']) != set(FILES)):
        raise ValueError('Manifiesto de integración no válido.')
    _version(payload['version'])
    for entry in payload['files'].values():
        if (not isinstance(entry, dict) or set(entry) != {'content', 'sha256'}
                or not isinstance(entry['content'], str) or '\x00' in entry['content']
                or len(entry['content'].encode('utf-8')) > MAX_FILE
                or not isinstance(entry['sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])
                or _digest(entry['content'].encode('utf-8')) != entry['sha256']):
            raise ValueError('Contenido o suma SHA-256 de integración no válidos.')
    if len(json.dumps(payload).encode('utf-8')) > MAX_PAYLOAD:
        raise ValueError('Manifiesto de integración demasiado grande.')
    _check_sources(payload)
    return payload


def build_payload(package_root, version):
    files = {}
    for relative in FILES:
        data, _st = _read_file(Path(package_root) / relative, MAX_FILE)
        files[relative] = {'sha256': _digest(data), 'content': data.decode('utf-8')}
    return validate_payload({'schema': 1, 'version': _version(version), 'files': files})


def default_bundle_dir():
    # PREFIX/lib/aio-debian-gui/aio_core -> PREFIX/share/aio-debian-gui/host-integration
    return Path(__file__).resolve().parents[3] / 'share/aio-debian-gui/host-integration'


def bundle_available(bundle_dir=None):
    directory = Path(bundle_dir) if bundle_dir is not None else default_bundle_dir()
    return (directory / 'payload.json').is_file() and (directory / 'host_integration.py').is_file()


# Esta etapa no tiene privilegios y usa Python del anfitrión también desde Flatpak.
_STAGE = r'''
import json, os, pathlib, shutil, sys, tempfile
value = json.load(sys.stdin)
if set(value) != {'installer', 'payload'}:
    raise ValueError('Invalid staging data')
directory = pathlib.Path(tempfile.mkdtemp(prefix='aio-debian-gui-host-', dir='/tmp'))
try:
    for name, key in [('host_integration.py','installer'), ('payload.json','payload')]:
        fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(value[key])
    print(str(directory))
except BaseException:
    shutil.rmtree(directory)
    raise
'''


def prepare(command_host, bundle_dir=None):
    directory = Path(bundle_dir) if bundle_dir is not None else default_bundle_dir()
    try:
        payload, _st = _read_file(directory / 'payload.json')
        validate_payload(json.loads(payload))
        installer, _st = _read_file(directory / 'host_integration.py', MAX_FILE)
    except (ValueError, KeyError, SyntaxError, configparser.Error, ElementTree.ParseError) as exc:
        raise RuntimeError('El paquete de integración no es válido.') from exc
    request = json.dumps({'installer': installer.decode('utf-8'), 'payload': payload.decode('utf-8')})
    try:
        result = subprocess.run(command_host('/usr/bin/python3', '-I', '-c', _STAGE),
                                input=request, capture_output=True, text=True, timeout=30)
    except subprocess.SubprocessError as exc:
        raise RuntimeError('No se pudo preparar la integración en el anfitrión.') from exc
    if result.returncode:
        raise RuntimeError('No se pudo preparar la integración en el anfitrión.')
    path = result.stdout.strip()
    if not re.fullmatch(r'/tmp/aio-debian-gui-host-[A-Za-z0-9_-]+', path):
        raise RuntimeError('El anfitrión devolvió una ruta temporal no válida.')
    return path


def install_command(command_host, directory):
    if not re.fullmatch(r'/tmp/aio-debian-gui-host-[A-Za-z0-9_-]+', directory):
        raise ValueError('Ruta temporal no válida.')
    return command_host('pkexec', '/usr/bin/python3', '-I', directory + '/host_integration.py',
                        '--install', directory + '/payload.json')


def uninstall_command(command_host, directory):
    return install_command(command_host, directory)[:-2] + ['--uninstall']


def cleanup(command_host, directory):
    if not re.fullmatch(r'/tmp/aio-debian-gui-host-[A-Za-z0-9_-]+', directory):
        raise ValueError('Ruta temporal no válida.')
    # rm recibe un único directorio temporal generado; jamás una ruta del manifiesto.
    result = subprocess.run(command_host('rm', '-rf', '--', directory),
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError('No se pudo retirar el directorio temporal del anfitrión.')


def _parent(root, relative):
    root = Path(root).resolve()
    current = root
    for part in Path(relative).parts[:-1]:
        current /= part
        try:
            st = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o755)
            os.chown(current, 0, 0)
            st = current.lstat()
        if not stat.S_ISDIR(st.st_mode) or not _trusted(st):
            raise PermissionError('Un directorio de integración no está protegido por root: '
                                  + str(current) + ' (uid=' + str(st.st_uid)
                                  + ', modo=' + oct(stat.S_IMODE(st.st_mode))
                                  + ', tipo=' + ('directorio' if stat.S_ISDIR(st.st_mode) else 'otro') + ').')
    return root / relative


def _atomic(root, relative, data, mode, gid=0):
    path = _parent(root, relative)
    fd, temporary = tempfile.mkstemp(prefix='.aio-integration-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, 0, gid)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _snapshot(root, relative):
    path = _parent(root, relative)
    try:
        data, st = _read_file(path, MAX_FILE, trusted=True)
        return data, stat.S_IMODE(st.st_mode), st.st_gid
    except FileNotFoundError:
        return None


def _restore(root, snapshots):
    for relative, snapshot in snapshots.items():
        if snapshot is None:
            _parent(root, relative).unlink(missing_ok=True)
        else:
            data, mode, gid = snapshot
            _atomic(root, relative, data, mode, gid)


def _systemctl(*args):
    result = subprocess.run(['/usr/bin/systemctl', *args], capture_output=True, text=True, timeout=30,
                            env={**os.environ, 'PATH': SYSTEM_PATH, 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or 'systemctl falló.').strip()[-600:])
    return result.stdout.strip()


def _dpkg_owned(relative):
    result = subprocess.run(['/usr/bin/dpkg-query', '-S', '--', '/' + relative],
                            capture_output=True, text=True, timeout=15,
                            env={**os.environ, 'PATH': SYSTEM_PATH, 'LC_ALL': 'C'})
    if result.returncode not in (0, 1):
        raise RuntimeError('No se pudo comprobar qué archivos gestiona dpkg.')
    return result.returncode == 0


def _check_host(root):
    if os.geteuid() != 0:
        raise PermissionError('Se necesita autorización de administrador.')
    values = {}
    for line in (Path(root) / 'etc/os-release').read_text().splitlines():
        key, _sep, value = line.partition('=')
        values[key] = value.strip().strip('"').strip("'")
    if not (values.get('ID') == 'debian' or values.get('ID') == 'ubuntu'
            and values.get('VERSION_ID') in ('24.04', '26.04')):
        raise RuntimeError('Sistema no compatible con la integración del programador.')
    if not (Path(root) / 'run/systemd/system').is_dir():
        raise RuntimeError('El anfitrión necesita systemd activo para programar mantenimientos.')
    for command in ('python3', 'systemctl', 'apt-get', 'dpkg-query', 'pkexec', 'flock', 'runuser'):
        if not shutil.which(command, path=SYSTEM_PATH):
            raise RuntimeError('Falta una herramienta necesaria en el anfitrión: ' + command)


@contextmanager
def _locks(root):
    descriptors = []
    try:
        for name in ('integration.lock', 'maintenance.lock'):
            path = _parent(root, 'run/aio-debian-gui/' + name)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            descriptors.append(fd)
            os.fchmod(fd, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('Hay un mantenimiento u otra integración de AiO en curso.') from exc
        yield
    finally:
        for fd in descriptors:
            os.close(fd)


def _marker(root):
    try:
        data, _st = _read_file(_parent(root, MARKER), trusted=True)
    except FileNotFoundError:
        return None
    marker = json.loads(data)
    if (not isinstance(marker, dict) or set(marker) != {'schema', 'version', 'files', 'owner_uid', 'previous'}
            or type(marker['schema']) is not int or marker['schema'] != 1 or type(marker['owner_uid']) is not int
            or not 0 < marker['owner_uid'] < 2**32 - 1
            or not isinstance(marker['files'], dict) or set(marker['files']) != set(FILES)
            or not isinstance(marker['previous'], dict) or not set(marker['previous']) <= set(FILES)):
        raise ValueError('Registro de propiedad de integración no válido.')
    _version(marker['version'])
    for digest in marker['files'].values():
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Registro de sumas de integración no válido.')
    for record in marker['previous'].values():
        if (not isinstance(record, dict) or set(record) != {'sha256', 'mode', 'gid'}
                or not isinstance(record['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', record['sha256'])
                or type(record['mode']) is not int or record['mode'] & ~0o755
                or record['mode'] & 0o022 or type(record['gid']) is not int or record['gid'] < 0):
            raise ValueError('Registro de copia previa no válido.')
    return marker


def _verify_managed(root, marker):
    for relative, digest in marker['files'].items():
        snapshot = _snapshot(root, relative)
        if snapshot is not None and _digest(snapshot[0]) != digest:
            raise RuntimeError('Hay archivos de integración modificados; no se sobrescribirán ni eliminarán.')
    for relative, record in marker['previous'].items():
        previous, _st = _read_file(_parent(root, BACKUP + '/' + relative), MAX_FILE, trusted=True)
        if _digest(previous) != record['sha256']:
            raise RuntimeError('La copia de la integración previa no es válida.')


def install(payload_path, root=Path('/')):
    _check_host(root)
    owner = _uid()
    raw, _st = _read_file(payload_path, owner=owner)
    # Los bytes se leen una vez y se validan en memoria de root. Ni el análisis
    # ni la activación vuelven a abrir una ruta mutable del usuario.
    payload = validate_payload(json.loads(raw))
    with _locks(root):
        if _systemctl('list-units', '--all', '--state=active,activating,deactivating',
                      '--no-legend', '--plain', SERVICE_NAME):
            raise RuntimeError('Hay un mantenimiento programado activo; espera a que termine.')
        snapshots = {p: _snapshot(root, p) for p in FILES}
        owned = {p: _dpkg_owned(p) for p in FILES}
        if any(owned.values()):
            if not all(owned.values()) or any(snapshots[p] is None or
                    _digest(snapshots[p][0]) != payload['files'][p]['sha256'] for p in FILES):
                raise RuntimeError('El paquete DEB gestiona estos componentes; actualízalo para mantener versiones compatibles.')
            return {'managed_by': 'deb', 'version': payload['version']}
        marker = _marker(root)
        if marker:
            installed_version = tuple(int(part) for part in marker['version'].split('.'))
            requested_version = tuple(int(part) for part in payload['version'].split('.'))
            if requested_version < installed_version:
                raise RuntimeError('La integración instalada es más reciente; actualiza la aplicación antes de continuar.')
            _verify_managed(root, marker)
        previous = dict(marker['previous']) if marker else {}
        created_backups = []
        old_marker = _snapshot(root, MARKER)
        try:
            if not marker:
                if any(snapshot is not None for snapshot in snapshots.values()):
                    _parent(root, BACKUP + '/.directory')
                    os.chmod(Path(root) / BACKUP, 0o700)
                for relative, snapshot in snapshots.items():
                    if snapshot is not None:
                        data, mode, gid = snapshot
                        backup = BACKUP + '/' + relative
                        if (Path(root) / backup).exists():
                            raise RuntimeError('Ya existe una copia previa sin registro de integración.')
                        _atomic(root, backup, data, 0o600)
                        created_backups.append(backup)
                        previous[relative] = {'sha256': _digest(data), 'mode': mode, 'gid': gid}
            for relative, mode in FILES.items():
                _atomic(root, relative, payload['files'][relative]['content'].encode('utf-8'), mode)
            _systemctl('daemon-reload')
            record = {'schema': 1, 'version': payload['version'],
                      'files': {p: payload['files'][p]['sha256'] for p in FILES},
                      'owner_uid': marker['owner_uid'] if marker else owner, 'previous': previous}
            _atomic(root, MARKER, (json.dumps(record) + '\n').encode(), 0o644)
        except BaseException:
            _restore(root, snapshots)
            _restore(root, {MARKER: old_marker})
            for backup in created_backups:
                _parent(root, backup).unlink(missing_ok=True)
            try:
                _systemctl('daemon-reload')
            except (OSError, RuntimeError, subprocess.SubprocessError):
                pass
            raise
    return {'managed_by': 'standalone', 'version': payload['version']}


def _assert_unused(root):
    checks = ('etc/aio-debian-gui/schedules/*.json',
              'etc/systemd/system/aio-debian-gui-maintenance-*.timer',
              'etc/systemd/system/timers.target.wants/aio-debian-gui-maintenance-*.timer',
              'etc/polkit-1/rules.d/*aiodebian-gui*.rules')
    if any(any(Path(root).glob(pattern)) for pattern in checks):
        raise RuntimeError('Elimina primero todas las programaciones y desactiva las excepciones de Polkit de AiO.')
    active = _systemctl('list-units', '--all', '--state=active,activating,deactivating',
                        '--no-legend', '--plain', SERVICE_NAME, 'aio-debian-gui-maintenance-*.timer')
    if active:
        raise RuntimeError('Hay un servicio o temporizador de AiO activo; no se retirará la integración.')


def uninstall(root=Path('/')):
    _check_host(root)
    owner = _uid()
    with _locks(root):
        marker = _marker(root)
        if not marker:
            raise RuntimeError('No hay una integración independiente que retirar.')
        if marker['owner_uid'] != owner:
            raise PermissionError('Solo el usuario que instaló la integración puede retirarla.')
        if any(_dpkg_owned(p) for p in FILES):
            raise RuntimeError('La integración está gestionada por un paquete DEB; no se retirará desde aquí.')
        _verify_managed(root, marker)
        _assert_unused(root)
        snapshots = {p: _snapshot(root, p) for p in FILES}
        old_marker = _snapshot(root, MARKER)
        try:
            for relative in FILES:
                previous = marker['previous'].get(relative)
                if previous:
                    data, _st = _read_file(_parent(root, BACKUP + '/' + relative), MAX_FILE, trusted=True)
                    _atomic(root, relative, data, previous['mode'], previous['gid'])
                else:
                    _parent(root, relative).unlink(missing_ok=True)
            _systemctl('daemon-reload')
            _parent(root, MARKER).unlink()
        except BaseException:
            _restore(root, snapshots)
            _restore(root, {MARKER: old_marker})
            try:
                _systemctl('daemon-reload')
            except (OSError, RuntimeError, subprocess.SubprocessError):
                pass
            raise
        for relative in marker['previous']:
            _parent(root, BACKUP + '/' + relative).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--build', nargs=3, metavar=('PACKAGE_ROOT', 'VERSION', 'OUTPUT_DIR'))
    actions.add_argument('--install', metavar='PAYLOAD_JSON')
    actions.add_argument('--uninstall', action='store_true')
    args = parser.parse_args(argv)
    if args.build:
        package, version, output = args.build
        payload = build_payload(package, version)
        directory = Path(output)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'payload.json').write_text(json.dumps(payload) + '\n', encoding='utf-8')
        shutil.copyfile(Path(__file__), directory / 'host_integration.py')
        (directory / 'payload.json').chmod(0o644)
        (directory / 'host_integration.py').chmod(0o644)
    else:
        if os.geteuid() != 0:
            raise PermissionError('Se necesita autorización de administrador.')
        _uid()
        print('##SCHEDULE:authorized', flush=True)
        if args.install:
            install(args.install)
        else:
            uninstall()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError, SyntaxError, configparser.Error,
            ElementTree.ParseError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
