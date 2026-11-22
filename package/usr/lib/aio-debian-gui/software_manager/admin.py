#!/usr/bin/python3 -I
"""Privileged operations for AyusOS Software Manager."""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

SOURCES = Path('/etc/apt/sources.list.d')
KEY_DIRS = (Path('/etc/apt/keyrings'), Path('/usr/share/keyrings'))
PACKAGE = re.compile(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9][a-z0-9-]*)?')
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9+._/-]*')
APT_SOURCE = re.compile(r'[A-Za-z0-9_.-]+\.(?:list|sources)(?:\.disabled)?')
MANAGED = re.compile(r'ayusos-manager-[a-f0-9]{16}\.sources(?:\.disabled)?')


def source_contents(uri, suite, components, key):
    parsed = urlsplit(uri)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or any(ord(char) <= 32 or ord(char) == 127 for char in uri)):
        raise ValueError('Introduce una URL HTTPS sin credenciales ni espacios.')
    if not TOKEN.fullmatch(suite) or suite.endswith('/') or not components.split():
        raise ValueError('Indica la distribución y al menos un componente.')
    if not all(TOKEN.fullmatch(item) for item in components.split()):
        raise ValueError('Los componentes contienen caracteres no válidos.')
    key_path = Path(key).resolve(strict=True)
    if (key_path.parent not in KEY_DIRS or key_path.suffix not in ('.asc', '.gpg')
            or not key_path.is_file() or not TOKEN.fullmatch(key_path.name)):
        raise ValueError('Selecciona una clave .asc o .gpg de un directorio de llaves de APT.')
    return (f'Types: deb\nURIs: {uri}\nSuites: {suite}\n'
            f'Components: {" ".join(components.split())}\nSigned-By: {key_path}\n')


def write_source(uri, suite, components, key):
    contents = source_contents(uri, suite, components, key)
    name = hashlib.sha256(contents.encode()).hexdigest()[:16]
    path = SOURCES / f'ayusos-manager-{name}.sources'
    if path.with_suffix('.sources.disabled').exists():
        raise ValueError('Este repositorio ya existe y está desactivado.')
    with tempfile.NamedTemporaryFile(mode='w', dir=SOURCES, delete=False) as temp:
        temp_path = Path(temp.name)
        try:
            temp.write(contents)
            temp.flush()
            temp_path.chmod(0o644)
            os.link(temp_path, path)
        finally:
            temp_path.unlink()


def system_flatpak_args(values):
    # Reconstruir únicamente las operaciones que ofrece el gestor.
    identifier = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]*')
    for prefix, count in (
        (['update', '-y'], 0), (['update', '-y', '--'], 1),
        (['install', '-y', '--'], 2), (['uninstall', '-y', '--'], 1),
        (['remote-delete', '--'], 1), (['remote-modify', '--enable', '--'], 1),
        (['remote-modify', '--disable', '--'], 1),
        (['remote-add', '--if-not-exists', '--'], 2),
    ):
        if values[:len(prefix)] != prefix or len(values) != len(prefix) + count:
            continue
        operands = values[len(prefix):]
        if prefix[0] == 'remote-add':
            url = urlsplit(operands[-1])
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                break
            operands = operands[:-1]
        if all(identifier.fullmatch(item) and '..' not in item for item in operands):
            return ['/usr/bin/flatpak', '--system', *values]
    raise ValueError('Operación Flatpak del sistema no válida.')


def trusted_archive(package, digest):
    """Match one SHA256 in one authenticated Packages index (never dpkg status)."""
    if not PACKAGE.fullmatch(package) or not re.fullmatch('[0-9a-f]{64}', digest):
        return False
    try:
        import apt_pkg
        apt_pkg.init()
        # APT also calls an index trusted when its source explicitly overrides
        # authentication. Require normal signature checking for the silent path.
        sources = Path(apt_pkg.config.find_dir('Dir::Etc::sourceparts'))
        paths = [*sources.glob('*.list'), *sources.glob('*.sources')]
        primary = Path(apt_pkg.config.find_file('Dir::Etc::sourcelist'))
        if primary.exists():
            paths.append(primary)
        for path in paths:
            if re.search(r'(?im)(?:^|[\s\[])trusted\s*[:=]', path.read_text()):
                return False
        cache = apt_pkg.Cache(None)
        indexes = apt_pkg.SourceList()
        indexes.read_main_list()
        records = apt_pkg.PackageRecords(cache)
        for version in cache[package].version_list:
            for entry in version.file_list:
                index = indexes.find_index(entry[0])
                if (index and index.is_trusted and records.lookup(entry)
                        and records.sha256_hash == digest):
                    return True
    except (ImportError, KeyError, OSError, ValueError, SystemError, UnicodeError):
        pass
    return False


def main(args):
    if os.geteuid() != 0:
        raise ValueError('Esta operación requiere permisos de administración.')
    command, *values = args
    env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
    apt = ['/usr/bin/apt-get', '-y', '-o', 'Dpkg::Options::=--force-confold']
    if command == 'flatpak-system':
        return subprocess.call(system_flatpak_args(values), env=env)
    if ((command == 'install-local' and len(values) == 1)
            or (command == 'install-trusted-local' and len(values) == 2)) and re.fullmatch('[a-f0-9]{64}', values[0]):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            archive = Path(directory) / 'package.deb'
            checksum = hashlib.sha256()
            with archive.open('wb') as target:
                for block in iter(lambda: sys.stdin.buffer.read(1024 * 1024), b''):
                    target.write(block)
                    checksum.update(block)
            if checksum.hexdigest() != values[0]:
                raise ValueError('El archivo ha cambiado. Vuelve a abrirlo para revisar la instalación.')
            if command == 'install-trusted-local' and not trusted_archive(values[1], checksum.hexdigest()):
                raise ValueError('APT no acredita este archivo. Vuelve a abrirlo para autenticarte.')
            archive.chmod(0o644)
            Path(directory).chmod(0o711)
            return subprocess.call(apt + ['--no-remove', 'install', '--', str(archive)],
                                   stdin=subprocess.DEVNULL, env=env)
    if command == 'refresh' and not values:
        return subprocess.call(apt + ['update'], env=env)
    if command in ('install', 'remove', 'upgrade') and len(values) == 1 and PACKAGE.fullmatch(values[0]):
        action = ['install', '--only-upgrade'] if command == 'upgrade' else [command]
        return subprocess.call(apt + action + ['--', values[0]], env=env)
    if command == 'add-source' and len(values) == 4:
        write_source(*values)
        return 0
    if command in ('enable', 'disable', 'delete') and len(values) == 1:
        name = values[0]
        if command == 'delete' and not MANAGED.fullmatch(name):
            raise ValueError('Solo se pueden quitar los archivos creados por el gestor.')
        if name in ('/etc/apt/sources.list', '/etc/apt/sources.list.disabled'):
            path = Path(name)
        elif APT_SOURCE.fullmatch(name):
            path = SOURCES / name
        else:
            raise ValueError('Nombre de archivo APT no válido.')
        if path.is_symlink() or not path.is_file():
            raise ValueError('El archivo del repositorio ya no está disponible.')
        if command == 'delete':
            path.unlink()
        elif command == 'disable' and path.suffix in ('.sources', '.list'):
            target = path.with_name(path.name + '.disabled')
            if target.exists():
                raise FileExistsError(target)
            path.rename(target)
        elif command == 'enable' and path.suffix == '.disabled':
            target = path.with_suffix('')
            if target.exists():
                raise FileExistsError(target)
            path.rename(target)
        else:
            raise ValueError('El repositorio ya está en ese estado.')
        return 0
    raise ValueError('Operación de administración no válida.')


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
