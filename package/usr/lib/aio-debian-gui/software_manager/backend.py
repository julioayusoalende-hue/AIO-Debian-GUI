"""Read APT and Flatpak catalogues without elevation."""

from pathlib import Path
import os
import re
import subprocess

from .admin import APT_SOURCE, MANAGED, SOURCES, source_contents

FLATPAK_REPO = 'https://dl.flathub.org/repo/flathub.flatpakrepo'
ADMIN = '/usr/lib/aio-debian-gui/software_manager/admin.py'


def run(args, timeout=None):
    try:
        result = subprocess.run(args, timeout=timeout, text=True, encoding='utf-8', errors='replace',
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, 'LC_ALL': 'C.UTF-8'})
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('El catálogo tardó demasiado en responder.') from exc
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()
                           or f'{args[0]} terminó con código {result.returncode}')
    return result.stdout


def debs():
    rows = []
    for line in run(['/usr/bin/apt', 'list']).splitlines()[1:]:
        fields = line.split(maxsplit=3)
        if len(fields) < 3 or '/' not in fields[0]:
            continue
        package, version, arch = fields[0].split('/', 1)[0], fields[1], fields[2]
        apt_state = fields[3] if len(fields) == 4 else ''
        state = ('Actualizable' if '[upgradable' in apt_state else
                 'Instalado' if '[installed' in apt_state else 'Disponible')
        identifier = package if arch == 'all' else f'{package}:{arch}'
        rows.append((package, identifier, version, state, arch))
    return rows, []


def flatpak(scope, *args):
    return ['/usr/bin/flatpak', f'--{scope}', *args]


def columns(output, size):
    for line in output.splitlines():
        values = line.split('\t')
        if len(values) <= size:
            yield values + [""] * (size - len(values))


def remotes(scope):
    output = run(flatpak(scope, 'remotes', '--columns=name,url,options'))
    return list(columns(output, 3))


def flatpaks(scope):
    rows = {}
    errors = []
    for name, ref, version, origin in columns(run(flatpak(
            scope, 'list', '--app', '--columns=name,ref,version,origin')), 4):
        rows[(origin, ref)] = (name, ref, version, 'Instalado', origin)
    for remote, _, options in remotes(scope):
        if 'disabled' in options.split(','):
            continue
        try:
            output = run(flatpak(scope, 'remote-ls', '--app',
                                 '--columns=name,ref,version', remote), timeout=12)
            for name, ref, version in columns(output, 3):
                rows.setdefault((remote, ref), (name, ref, version, 'Disponible', remote))
        except RuntimeError as exc:
            errors.append(f'{remote} — {exc}')
    return sorted(rows.values(), key=lambda row: row[0].casefold()), errors


def repos(scope):
    rows = [(name, url, 'Flatpak', 'Desactivado' if 'disabled' in options.split(',')
             else 'Activo', name) for name, url, options in remotes(scope)]
    paths = [Path('/etc/apt/sources.list'), Path('/etc/apt/sources.list.disabled'),
             *sorted(SOURCES.glob('*'))]
    for path in paths:
        if not APT_SOURCE.fullmatch(path.name) and path.parent == SOURCES:
            continue
        try:
            contents = path.read_text()
        except OSError:
            continue
        managed = bool(MANAGED.fullmatch(path.name))
        file_disabled = path.suffix == '.disabled'
        location = str(path) if path.parent != SOURCES else path.name
        if path.name.endswith(('.list', '.list.disabled')):
            for line in contents.splitlines():
                match = re.match(r'^\s*(#\s*)?deb(?:-src)?\s+(?:\[[^\]]*\]\s+)?(\S+)(?:\s+(\S+))?', line)
                if match:
                    rows.append((match[3] or path.name, match[2], 'APT',
                                 'En pausa' if file_disabled else 'Desactivado' if match[1] else 'Activo',
                                 location))
            continue
        for stanza in re.split(r'\n\s*\n', contents):
            uri = re.search(r'^URIs:\s*(.+)$', stanza, re.MULTILINE | re.IGNORECASE)
            suite = re.search(r'^Suites:\s*(.+)$', stanza, re.MULTILINE | re.IGNORECASE)
            if not uri:
                continue
            disabled = re.search(
                r'^Enabled:\s*no\s*$', stanza, re.MULTILINE | re.IGNORECASE)
            rows.append((suite[1] if suite else path.name, uri[1],
                         'APT • gestionado' if managed else 'APT',
                         'En pausa' if file_disabled else 'Desactivado' if disabled else 'Activo',
                         location))
    return rows, []
