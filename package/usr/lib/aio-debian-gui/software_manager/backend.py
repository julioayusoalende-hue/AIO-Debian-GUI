"""Read APT and Flatpak catalogues without elevation."""

from pathlib import Path
import hashlib
import shutil
import tempfile
import os
import re
import subprocess

from .admin import APT_SOURCE, MANAGED, SOURCES, source_contents, trusted_archive

FLATPAK_REPO = 'https://dl.flathub.org/repo/flathub.flatpakrepo'
MAINTENANCE = '/usr/lib/aio-debian-gui/aio-debian-gui-helper'
ADMIN = '/usr/lib/aio-debian-gui/software_manager/admin.py'


def run(args, timeout=None, stdin=None):
    try:
        result = subprocess.run(args, stdin=stdin, timeout=timeout, text=True, encoding='utf-8', errors='replace',
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, 'LC_ALL': 'C.UTF-8'})
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('El catálogo tardó demasiado en responder.') from exc
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()
                           or f'{args[0]} terminó con código {result.returncode}')
    return result.stdout


def preview_local_deb(filename):
    path = Path(filename)
    if path.suffix.lower() != '.deb' or not path.is_file():
        raise ValueError('Selecciona un archivo .deb local válido.')
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'package.deb'
        with path.open('rb') as source, archive.open('wb') as target:
            shutil.copyfileobj(source, target)
        with archive.open('rb') as source:
            checksum = hashlib.sha256()
            for block in iter(lambda: source.read(1024 * 1024), b''):
                checksum.update(block)
            digest = checksum.hexdigest()
        metadata = run(['/usr/bin/dpkg-deb', '-f', str(archive), 'Package', 'Version',
                        'Architecture', 'Description', 'Pre-Depends', 'Depends'])
        package = run(['/usr/bin/dpkg-deb', '-f', str(archive), 'Package']).strip()
        trusted = trusted_archive(package, digest)
        plan = run(['/usr/bin/apt-get', '-s', '--no-remove', 'install', '--', str(archive)])
    return digest, package, trusted, metadata + '\n' + plan


def install_local_deb(filename, command):
    with open(filename, 'rb') as source:
        return run(command, stdin=source)


def debs():
    rows = []
    descriptions = {}
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
    try:
        for record in _deb822_records(run(['/usr/bin/apt-cache', 'show'])):
            name = record.get('Package', '')
            if name and name not in descriptions:
                description = (record.get('Description') or record.get('Description-en') or '').strip()
                if description:
                    descriptions[name] = description
    except (RuntimeError, OSError, ValueError):
        pass
    return rows, [], descriptions


def _deb822_records(output):
    for stanza in re.split(r'\n[ \t]*\n', output):
        fields = {}
        key = None
        for line in stanza.splitlines():
            if line.startswith((' ', '\t')):
                if key in ('Pre-Depends', 'Depends', 'Recommends'):
                    fields[key] += ' ' + line.strip()
                continue
            key, separator, value = line.partition(':')
            if separator:
                fields[key] = value.strip()
            else:
                key = None
        if fields:
            yield fields


def deb_details(identifier, version, arch, updatable=False):
    name = identifier.split(':', 1)[0]

    def find_record(output):
        return next((record for record in _deb822_records(output)
                     if record.get('Package') == name and record.get('Version') == version
                     and record.get('Architecture') == arch), None)

    try:
        output = run(['/usr/bin/apt-cache', 'show', '--', f'{identifier}={version}'], timeout=8)
        record = find_record(output)
    except RuntimeError:
        record = None
    if record is None:
        record = find_record(run(['/usr/bin/dpkg-query', '-s', '--', identifier], timeout=8))
    if record is None:
        return {}
    details = {key: record[key] for key in
               ('Architecture', 'Version', 'Pre-Depends', 'Depends', 'Recommends', 'Section', 'Homepage')
               if record.get(key)}
    description = record.get('Description') or record.get('Description-en')
    if description:
        details['Description'] = description
    for source, field, unit in (('Size', 'Download Size', 'B'),
                                ('Installed-Size', 'Installed Size', 'KiB')):
        size = record.get(source, '')
        if size.isdecimal():
            details[field] = f'{size} {unit}'
    if updatable and details:
        try:
            output = run(['/usr/bin/apt-cache', 'policy', '--', name], timeout=8)
        except RuntimeError:
            output = ''
        match = re.search(r'^\s*Candidate:\s*(\S+)', output, re.MULTILINE)
        candidate = match.group(1) if match else ''
        if candidate and candidate not in ('(none)', '(ninguno)') and candidate != version:
            details['Versión disponible'] = candidate
    return details


def flatpak_details(scope, remote, ref, installed, new_version=None):
    args = ('info', '--', ref) if installed else ('remote-info', '--', remote, ref)
    output = run(flatpak(scope, *args), timeout=12).strip()
    # With LC_ALL=C.UTF-8, the human-readable report starts with an optional
    # AppStream summary and then prints the English field labels.
    report = re.search(r'^[ \t]*ID:', output, flags=re.MULTILINE)
    summary = output[:report.start()] if report else ''
    fields = output[report.end():] if report else output
    details = {}
    _, found, description = ' '.join(summary.split()).partition(' - ')
    if found and description not in ('(null)', '-'):
        details['Description'] = description
    keys = {'Runtime', 'Arch', 'Branch', 'Version', 'License', 'Download Size', 'Installed Size'}
    for line in fields.splitlines():
        key, _, value = line.strip().partition(':')
        if key in keys and value.strip() not in ('', '-'):
            details['Architecture' if key == 'Arch' else key] = value.strip()
    if installed and new_version and new_version.strip() not in ('', '-'):
        details['Versión disponible'] = new_version.strip()
    return details


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
    updates = {}
    errors = []
    for name, ref, version, origin in columns(run(flatpak(
            scope, 'list', '--app', '--columns=name,ref,version,origin')), 4):
        rows[(origin, ref)] = (name, ref, version, 'Instalado', origin)
    installed_origins = {origin for origin, _ in rows}
    for remote, _, options in remotes(scope):
        if 'disabled' in options.split(','):
            continue
        try:
            output = run(flatpak(scope, 'remote-ls', '--app',
                                 '--columns=name,ref,version', remote), timeout=12)
            for name, ref, version in columns(output, 3):
                rows.setdefault((remote, ref), (name, ref, version, 'Disponible', remote))
            if remote in installed_origins:
                updates_out = run(flatpak(scope, 'remote-ls', '--app', '--updates', '--all',
                                          '--arch=*', '--columns=ref,version', '--', remote), timeout=12)
                for ref, version in columns(updates_out, 2):
                    if ref:
                        updates[(remote, ref)] = version
                    key = (remote, ref)
                    row = rows.get(key)
                    if row and row[3] == 'Instalado':
                        rows[key] = (*row[:3], 'Actualizable', remote)
        except RuntimeError as exc:
            errors.append(f'{remote} — {exc}')
    return sorted(rows.values(), key=lambda row: row[0].casefold()), errors, updates


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
