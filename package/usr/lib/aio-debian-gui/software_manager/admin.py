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


def main(args):
    if os.geteuid() != 0:
        raise ValueError('Esta operación requiere permisos de administración.')
    command, *values = args
    env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
    apt = ['/usr/bin/apt-get', '-y', '-o', 'Dpkg::Options::=--force-confold']
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
