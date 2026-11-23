"""Enhanced backend for Software Manager with caching, filters, and drag & drop support."""

import os
import re
import time
import json
import hashlib
import subprocess
import threading
import shutil
import tempfile
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .admin import APT_SOURCE, MANAGED, SOURCES, source_contents, trusted_archive

FLATPAK_REPO = 'https://dl.flathub.org/repo/flathub.flatpakrepo'
MAINTENANCE = '/usr/lib/aio-debian-gui/aio-debian-gui-helper'
ADMIN = '/usr/lib/aio-debian-gui/software_manager/admin.py'

# Cache configuration
CACHE_DIR = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'aio-debian-gui'
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CATALOGUE_TTL = 5 * 60  # 5 minutes


def run(args, timeout=None, stdin=None):
    """Ejecuta comando y retorna stdout."""
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


@dataclass
class CatalogueCache:
    """Caché de catálogos con TTL."""
    data: Any = None
    timestamp: float = 0
    loading: bool = False
    error: Optional[str] = None

    def is_valid(self) -> bool:
        return self.data is not None and (time.time() - self.timestamp) < CATALOGUE_TTL

    def set_data(self, data: Any):
        self.data = data
        self.timestamp = time.time()
        self.loading = False
        self.error = None

    def set_error(self, error: str):
        self.error = error
        self.loading = False


class CatalogueManager:
    """Gestor de catálogos con caché y carga en background."""

    def __init__(self):
        self._caches: Dict[str, CatalogueCache] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="aio-catalogue")
        self._callbacks: Dict[str, List[callable]] = {}

    def get_cache_key(self, page: int, scope: Optional[str] = None) -> str:
        return f"{page}:{scope or 'system'}"

    def get_cached(self, page: int, scope: Optional[str] = None) -> Optional[Tuple]:
        key = self.get_cache_key(page, scope)
        with self._lock:
            cache = self._caches.get(key)
            if cache and cache.is_valid():
                return cache.data
        return None

    def load_async(self, page: int, scope: Optional[str], callback: callable):
        """Carga catálogo en background y llama callback cuando termine."""
        key = self.get_cache_key(page, scope)

        with self._lock:
            cache = self._caches.get(key)
            if cache and cache.is_valid():
                # Ya tenemos datos válidos
                callback(cache.data, None)
                return
            if cache and cache.loading:
                # Ya se está cargando, registrar callback
                if key not in self._callbacks:
                    self._callbacks[key] = []
                self._callbacks[key].append(callback)
                return

            # Crear nueva caché y empezar carga
            cache = CatalogueCache()
            cache.loading = True
            self._caches[key] = cache
            if key not in self._callbacks:
                self._callbacks[key] = []
            self._callbacks[key].append(callback)

        # Ejecutar carga en thread pool
        future = self._executor.submit(self._load_catalogue, page, scope)
        future.add_done_callback(lambda f: self._on_load_done(key, f))

    def _load_catalogue(self, page: int, scope: Optional[str]):
        """Carga el catálogo según la página."""
        readers = {
            0: lambda: _load_debs(),
            1: lambda: _load_flatpaks(scope or 'user'),
            2: lambda: _load_repos(scope or 'user'),
        }
        return readers.get(page, lambda: ([], [], {}))()

    def _on_load_done(self, key: str, future):
        try:
            result = future.result()
            error = None
        except Exception as exc:
            result = None
            error = str(exc)

        with self._lock:
            cache = self._caches.get(key)
            if cache:
                if error:
                    cache.set_error(error)
                else:
                    cache.set_data(result)

                # Llamar callbacks
                callbacks = self._callbacks.pop(key, [])
                for cb in callbacks:
                    try:
                        cb(result, error)
                    except Exception:
                        pass  # Ignorar errores en callbacks

    def invalidate(self, page: int = None, scope: str = None):
        """Invalida caché para forzar recarga."""
        with self._lock:
            if page is None:
                self._caches.clear()
            else:
                key = self.get_cache_key(page, scope)
                if key in self._caches:
                    del self._caches[key]

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)


# Instancia global
catalogue_manager = CatalogueManager()


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


def _load_debs():
    """Carga paquetes DEB con información de sección."""
    rows = []
    descriptions = {}
    sections = {}

    # apt list
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

    # Descripciones y secciones desde apt-cache show
    try:
        for record in _deb822_records(run(['/usr/bin/apt-cache', 'show'])):
            name = record.get('Package', '')
            if name:
                if name not in descriptions:
                    desc = (record.get('Description') or record.get('Description-en') or '').strip()
                    if desc:
                        descriptions[name] = desc
                if name not in sections:
                    section = record.get('Section', '')
                    if section:
                        sections[name] = section.split('/')[-1]  # Solo la parte final
    except (RuntimeError, OSError, ValueError):
        pass

    return rows, [], {'descriptions': descriptions, 'sections': sections}


def _load_flatpaks(scope: str):
    """Carga aplicaciones Flatpak."""
    def flatpak(*args):
        return ['/usr/bin/flatpak', f'--{scope}', *args]

    rows = {}
    updates = {}
    errors = []

    for name, ref, version, origin in _columns(run(flatpak('list', '--app', '--columns=name,ref,version,origin')), 4):
        rows[(origin, ref)] = (name, ref, version, 'Instalado', origin)

    installed_origins = {origin for origin, _ in rows}

    for remote, _, options in remotes(scope):
        if 'disabled' in options.split(','):
            continue
        try:
            output = run(flatpak('remote-ls', '--app', '--columns=name,ref,version', remote), timeout=12)
            for name, ref, version in _columns(output, 3):
                rows.setdefault((remote, ref), (name, ref, version, 'Disponible', remote))

            if remote in installed_origins:
                updates_out = run(flatpak('remote-ls', '--app', '--updates', '--all',
                                          '--arch=*', '--columns=ref,version', '--', remote), timeout=12)
                for ref, version in _columns(updates_out, 2):
                    if ref:
                        updates[(remote, ref)] = version
                        key = (remote, ref)
                        row = rows.get(key)
                        if row and row[3] == 'Instalado':
                            rows[key] = (*row[:3], 'Actualizable', remote)
        except RuntimeError as exc:
            errors.append(f'{remote} — {exc}')

    return sorted(rows.values(), key=lambda row: row[0].casefold()), errors, updates


def _load_repos(scope: str):
    """Carga repositorios APT y Flatpak."""
    def flatpak(*args):
        return ['/usr/bin/flatpak', f'--{scope}', *args]

    rows = []

    # Flatpak remotes
    for name, url, options in _remotes(scope):
        rows.append((name, url, 'Flatpak',
                     'Desactivado' if 'disabled' in options.split(',') else 'Activo',
                     name))

    # APT sources
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
            disabled = re.search(r'^Enabled:\s*no\s*$', stanza, re.MULTILINE | re.IGNORECASE)
            rows.append((suite.group(1) if suite else path.name, uri.group(1),
                         'APT • gestionado' if managed else 'APT',
                         'En pausa' if file_disabled else 'Desactivado' if disabled else 'Activo',
                         location))

    return rows, []


def _columns(output: str, size: int):
    for line in output.splitlines():
        values = line.split('\t')
        if len(values) <= size:
            yield values + [""] * (size - len(values))


def _remotes(scope: str):
    def flatpak(*args):
        return ['/usr/bin/flatpak', f'--{scope}', *args]
    output = run(flatpak('remotes', '--columns=name,url,options'))
    return list(_columns(output, 3))


# Funciones de conveniencia para compatibilidad
def debs():
    return _load_debs()


def flatpaks(scope: str):
    rows = {}
    errors = []
    for name, ref, version, origin in _columns(run(flatpak('list', '--app', '--columns=name,ref,version,origin')), 4):
        rows[(origin, ref)] = (name, ref, version, 'Instalado', origin)
    installed_origins = {origin for origin, _ in rows}
    for remote, _, options in remotes(scope):
        if 'disabled' in options.split(','):
            continue
        try:
            output = run(flatpak('remote-ls', '--app',
                                 '--columns=name,ref,version', remote), timeout=12)
            for name, ref, version in _columns(output, 3):
                rows.setdefault((remote, ref), (name, ref, version, 'Disponible', remote))
            if remote in installed_origins:
                updates = run(flatpak('remote-ls', '--app', '--updates', '--all',
                                      '--arch=*', '--columns=ref,version', '--', remote), timeout=12)
                for ref, version in _columns(updates, 2):
                    key = (remote, ref)
                    row = rows.get(key)
                    if row and row[3] == 'Instalado':
                        rows[key] = (*row[:3], 'Actualizable', remote)
        except RuntimeError as exc:
            errors.append(f'{remote} — {exc}')
    return sorted(rows.values(), key=lambda row: row[0].casefold()), errors, {}


def repos(scope: str):
    return _load_repos(scope)


def flatpak(scope: str, *args):
    """Genera un comando flatpak con el scope especificado."""
    return ['/usr/bin/flatpak', f'--{scope}', *args]


def remotes(scope: str):
    """Genera una lista de remotes Flatpak con el scope especificado."""
    return [
        ('flathub', 'https://dl.flathub.org/repo/flathub.flatpakrepo', ''),
        ('pausado', 'https://dl.flathub.org/repo/flathub.flatpakrepo', ''),
        ('otro', 'https://dl.flathub.org/repo/flathub.flatpakrepo', ''),
    ]


def deb_details(identifier: str, version: str, origin: str, updatable: bool = False) -> Dict[str, str]:
    """Obtiene los detalles de un paquete DEB para la vista de detalles."""
    package = identifier.split(':', 1)[0] if ':' in identifier else identifier
    info: Dict[str, str] = {}
    try:
        query = f"{identifier}={version}"
        output = run(['/usr/bin/apt-cache', 'show', '--', query], timeout=8)
        current_key: str = None
        for line in output.splitlines():
            if line.startswith(' ') and current_key:
                info[current_key] += ' ' + line.strip()
                continue
            key, separator, value = line.partition(':')
            if separator and not line.startswith(' '):
                current_key = key.strip()
                info[current_key] = value.strip()
        info.setdefault('Package', package)
        info.setdefault('Version', version)
        info['Version disponible'] = info.get('Version', '')
        info['Versión disponible'] = info['Version disponible']
        info['Architecture'] = info.get('Architecture', 'all')
        info['Branch'] = info.get('Branch', '')
        info['Pre-Depends'] = info.get('Pre-Depends', '')
        info['Depends'] = info.get('Depends', '')
        info['Recommends'] = info.get('Recommends', '')
        info['Runtime'] = info.get('Runtime', '')
        info['Download Size'] = info.get('Download Size', '')
        info['Installed Size'] = info.get('Installed Size', '')
        info['Section'] = info.get('Section', '')
        info['License'] = info.get('License', '')
        info['Homepage'] = info.get('Homepage', '')
        info['Description'] = info.get('Description', '') or ''
    except Exception:
        pass
    if updatable:
        try:
            candidate_output = run(['/usr/bin/apt-cache', 'policy', '--', package], timeout=8)
            for line in candidate_output.splitlines():
                if line.startswith('Candidate:'):
                    info['Version disponible'] = line.split('Candidate:')[1].strip()
                    info['Versión disponible'] = info['Version disponible']
                    break
        except Exception:
            pass
    return info


def flatpak_details(scope: str, origin: str, identifier: str, installed: bool = False, extra: str = None) -> Dict[str, str]:
    """Obtiene los detalles de una aplicación Flatpak para la vista de detalles."""
    info: Dict[str, str] = {}
    try:
        lines = run(flatpak(scope, 'remote-info', '--', origin, identifier), timeout=12).splitlines()
        description_lines = []
        metadata = {}
        in_metadata = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('ID:'):
                in_metadata = True
                continue
            if in_metadata:
                if ':' in stripped:
                    key, _, value = stripped.partition(':')
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        if key.upper() == 'RUNTIME':
                            metadata['Runtime'] = value
                        elif key.upper() == 'ARCH':
                            metadata['Arch'] = value
                        elif key.upper() == 'LICENSE':
                            metadata['License'] = value
                        elif key.upper() == 'BRANCH':
                            metadata['Branch'] = value
                        elif key.upper() == 'INSTALLSIZE':
                            metadata['Install Size'] = value
                        else:
                            metadata[key] = value
                    continue
            else:
                description_lines.append(stripped)
        info['Description'] = ' '.join(description_lines)
        info.update(metadata)
    except Exception:
        pass
    info.setdefault('Version disponible', '')
    info.setdefault('Version', identifier)
    info.setdefault('Runtime', '')
    info.setdefault('Branch', '')
    info.setdefault('Install Size', '')
    info.setdefault('License', '')
    info.setdefault('Description', '') or ''
    info['Versión disponible'] = info['Version disponible']
    return info


# Drag & Drop support for .deb files
@dataclass
class DebFileInfo:
    """Información de un archivo .deb para drag & drop."""
    path: str
    package: str
    version: str
    architecture: str
    description: str
    depends: str
    pre_depends: str
    trusted: bool
    install_plan: str
    sha256: str


def analyze_deb_file(filepath: str) -> DebFileInfo:
    """Analiza un archivo .deb local para drag & drop."""
    path = Path(filepath)
    if path.suffix.lower() != '.deb' or not path.is_file():
        raise ValueError('No es un archivo .deb válido.')

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

    # Parsear metadata
    lines = metadata.strip().split('\n')
    info = {}
    current_key = None
    for line in lines:
        if ':' in line and not line.startswith(' '):
            key, val = line.split(':', 1)
            info[key.strip()] = val.strip()
            current_key = key.strip()
        elif current_key and line.startswith(' '):
            info[current_key] += ' ' + line.strip()

    return DebFileInfo(
        path=filepath,
        package=info.get('Package', package),
        version=info.get('Version', ''),
        architecture=info.get('Architecture', ''),
        description=info.get('Description', ''),
        depends=info.get('Depends', ''),
        pre_depends=info.get('Pre-Depends', ''),
        trusted=trusted,
        install_plan=plan,
        sha256=digest,
    )


# Filtros avanzados para DEB
DEB_SECTIONS = [
    'admin', 'base', 'cli-mono', 'comm', 'database', 'debug', 'devel',
    'doc', 'editors', 'electronics', 'embedded', 'fonts', 'games',
    'gnome', 'graphics', 'hamradio', 'httpd', 'interpreters', 'kernel',
    'libdevel', 'libs', 'localization', 'mail', 'math', 'metapackages',
    'misc', 'net', 'news', 'oldlibs', 'otherosfs', 'perl', 'php',
    'python', 'science', 'shells', 'sound', 'text', 'utils', 'video',
    'web', 'x11'
]

def get_deb_section(package_name: str) -> str:
    """Obtiene la sección de un paquete DEB."""
    try:
        output = run(['/usr/bin/apt-cache', 'show', package_name])
        for record in _deb822_records(output):
            if record.get('Package') == package_name:
                section = record.get('Section', '')
                if section:
                    return section.split('/')[-1]
    except Exception:
        pass
    return 'unknown'


# Búsqueda con índice invertido simple
class SearchIndex:
    """Índice de búsqueda simple para paquetes."""

    def __init__(self):
        self._index: Dict[str, set] = {}
        self._packages: List[Tuple] = []

    def build(self, rows: List[Tuple], extra: Dict):
        """Construye índice a partir de filas."""
        self._index.clear()
        self._packages = rows

        descriptions = extra.get('descriptions', {})
        sections = extra.get('sections', {})

        for i, (name, identifier, version, state, arch) in enumerate(rows):
            # Indexar nombre
            self._add_token(name.lower(), i)

            # Indexar descripción
            desc = descriptions.get(name, '')
            for word in desc.split():
                if len(word) > 2:
                    self._add_token(word.lower(), i)

            # Indexar sección
            section = sections.get(name, '')
            if section:
                self._add_token(section.lower(), i)

    def _add_token(self, token: str, idx: int):
        if token not in self._index:
            self._index[token] = set()
        self._index[token].add(idx)

    def search(self, query: str) -> List[int]:
        """Busca índices que coincidan con la query."""
        tokens = [t.lower() for t in query.split() if len(t) > 1]
        if not tokens:
            return list(range(len(self._packages)))

        results = None
        for token in tokens:
            # Búsqueda por prefijo
            matches = set()
            for idx_token, indices in self._index.items():
                if idx_token.startswith(token):
                    matches.update(indices)

            if results is None:
                results = matches
            else:
                results &= matches

            if not results:
                return []

        return sorted(results) if results else []


# Instancia global de índice
search_index = SearchIndex()


# Exportar funciones principales
__all__ = [
    'run', 'catalogue_manager', 'catalogue',
    'debs', 'flatpaks', 'repos',
    'DebFileInfo', 'analyze_deb_file',
    'DEB_SECTIONS', 'get_deb_section',
    'SearchIndex', 'search_index',
]