"""Tests for software_manager admin (privileged operations)."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ayusos-control-center', 'package', 'usr', 'lib', 'aio-debian-gui', 'extensions', 'ayusos'))

from software_manager import admin

DIGEST = 'a' * 64


@pytest.fixture
def keyring(tmp_path, monkeypatch):
    """Clave .asc dentro de un directorio de llaves permitido."""
    keys = tmp_path / 'keyrings'
    keys.mkdir()
    key = keys / 'aio-test.asc'
    key.write_text('fake key')
    monkeypatch.setattr(admin, 'KEY_DIRS', (keys.resolve(),))
    return key


@pytest.fixture
def sources_dir(tmp_path, monkeypatch):
    sources = tmp_path / 'sources.list.d'
    sources.mkdir()
    monkeypatch.setattr(admin, 'SOURCES', sources)
    return sources


class TestSourceContents:
    """Validación de repositorios APT gestionados."""

    def test_valid_source(self, keyring):
        content = admin.source_contents(
            'https://example.com/repo', 'trixie', 'main contrib', keyring)
        assert content == (
            'Types: deb\n'
            'URIs: https://example.com/repo\n'
            'Suites: trixie\n'
            'Components: main contrib\n'
            f'Signed-By: {keyring.resolve()}\n'
        )

    def test_rejects_insecure_or_credentialed_urls(self, keyring):
        with pytest.raises(ValueError, match='HTTPS'):
            admin.source_contents('http://example.com/repo', 'trixie', 'main', keyring)
        with pytest.raises(ValueError, match='credenciales'):
            admin.source_contents('https://user:pass@example.com/repo', 'trixie', 'main', keyring)
        with pytest.raises(ValueError, match='HTTPS'):
            admin.source_contents('https://example.com/repo?a=1', 'trixie', 'main', keyring)

    def test_rejects_invalid_suite(self, keyring):
        with pytest.raises(ValueError, match='distribución'):
            admin.source_contents('https://example.com/repo', 'invalid/suite', 'main', keyring)
        with pytest.raises(ValueError, match='componentes'):
            admin.source_contents('https://example.com/repo', 'trixie', 'main;rm -rf /', keyring)

    def test_rejects_key_outside_keyrings(self, tmp_path):
        key = tmp_path / 'outside.asc'
        key.write_text('fake key')
        with pytest.raises(ValueError, match='directorio de llaves'):
            admin.source_contents('https://example.com/repo', 'trixie', 'main', key)

    def test_rejects_missing_key(self, tmp_path):
        with pytest.raises((ValueError, OSError)):
            admin.source_contents(
                'https://example.com/repo', 'trixie', 'main', tmp_path / 'missing.asc')


class TestWriteSource:
    """Escritura atómica de los ficheros gestionados."""

    def test_creates_hashed_file(self, keyring, sources_dir):
        admin.write_source('https://example.com/repo', 'trixie', 'main', keyring)
        files = list(sources_dir.glob('ayusos-manager-*.sources'))
        assert len(files) == 1
        assert files[0].read_text().startswith('Types: deb\n')
        assert not list(sources_dir.glob('.tmp*'))

    def test_never_overwrites_an_existing_source(self, keyring, sources_dir):
        admin.write_source('https://example.com/repo', 'trixie', 'main', keyring)
        with pytest.raises(FileExistsError):
            admin.write_source('https://example.com/repo', 'trixie', 'main', keyring)


class TestRegexes:
    """Los patrones deben aceptar nombres reales y rechazar inyecciones."""

    def test_package_regex(self):
        valid = ['package', 'libfoo', 'pkg-name', 'pkg:name', 'pkg123',
                 'libfoo-dev:amd64', 'g++', 'g++-12', 'a-', 'pkg..name']
        invalid = ['', '-package', 'pkg/name', 'PACKAGE', 'pkg name',
                   'pkg;reboot', 'pkg\nreboot', 'pkg$(id)']

        for pkg in valid:
            assert admin.PACKAGE.fullmatch(pkg), f'Debería ser válido: {pkg!r}'
        for pkg in invalid:
            assert not admin.PACKAGE.fullmatch(pkg), f'Debería ser inválido: {pkg!r}'

    def test_token_regex(self):
        valid = ['token', 'token-name', 'token_name', 'token.name', 'token123', 'TOKEN']
        invalid = ['', '-token', 'token name', 'token;reboot', 'tok\nen']

        for tok in valid:
            assert admin.TOKEN.fullmatch(tok), f'Debería ser válido: {tok!r}'
        for tok in invalid:
            assert not admin.TOKEN.fullmatch(tok), f'Debería ser inválido: {tok!r}'

    def test_apt_source_regex(self):
        valid = ['pkg.list', 'pkg.sources', 'pkg.list.disabled', 'pkg.sources.disabled']
        invalid = ['pkg', 'pkg.txt', '.list', '.sources']

        for src in valid:
            assert admin.APT_SOURCE.fullmatch(src), f'Debería ser válido: {src!r}'
        for src in invalid:
            assert not admin.APT_SOURCE.fullmatch(src), f'Debería ser inválido: {src!r}'

    def test_managed_regex(self):
        valid = ['ayusos-manager-abcdef1234567890.sources',
                 'ayusos-manager-abcdef1234567890.sources.disabled']
        invalid = ['ayusos-manager-abc.sources', 'pkg.sources',
                   'ayusos-manager-abcdef1234567890.list']

        for src in valid:
            assert admin.MANAGED.fullmatch(src), f'Debería ser válido: {src!r}'
        for src in invalid:
            assert not admin.MANAGED.fullmatch(src), f'Debería ser inválido: {src!r}'


class TestMain:
    """Construcción de las órdenes APT que se ejecutan como root."""

    @pytest.fixture(autouse=True)
    def as_root(self):
        with patch.object(admin.os, 'geteuid', return_value=0):
            yield

    def test_requires_root(self):
        with patch.object(admin.os, 'geteuid', return_value=1000):
            with pytest.raises(ValueError, match='permisos de administración'):
                admin.main(['refresh'])

    @patch('software_manager.admin.subprocess.call')
    def test_refresh(self, mock_call):
        mock_call.return_value = 0
        assert admin.main(['refresh']) == 0
        args = mock_call.call_args[0][0]
        assert args[0] == '/usr/bin/apt-get'
        assert args[-1] == 'update'

    @patch('software_manager.admin.subprocess.call')
    def test_install(self, mock_call):
        mock_call.return_value = 0
        assert admin.main(['install', 'pkg1', 'pkg2']) == 0
        args = mock_call.call_args[0][0]
        assert 'install' in args
        assert args[-3:] == ['--', 'pkg1', 'pkg2']

    @patch('software_manager.admin.subprocess.call')
    def test_upgrade_uses_only_upgrade(self, mock_call):
        mock_call.return_value = 0
        assert admin.main(['upgrade', 'pkg1']) == 0
        args = mock_call.call_args[0][0]
        assert 'install' in args and '--only-upgrade' in args

    @patch('software_manager.admin.subprocess.call')
    def test_remove(self, mock_call):
        mock_call.return_value = 0
        assert admin.main(['remove', 'pkg1']) == 0
        args = mock_call.call_args[0][0]
        assert 'remove' in args and 'pkg1' in args

    @patch('software_manager.admin.subprocess.call')
    def test_rejects_invalid_package_names(self, mock_call):
        with pytest.raises(ValueError):
            admin.main(['install', 'pkg;reboot'])
        with pytest.raises(ValueError):
            admin.main(['install', 'PACKAGE'])
        mock_call.assert_not_called()

    def test_add_source(self, keyring, sources_dir):
        assert admin.main(['add-source', 'https://example.com/repo',
                           'trixie', 'main', str(keyring)]) == 0
        assert len(list(sources_dir.glob('ayusos-manager-*.sources'))) == 1

    def test_delete_only_removes_managed_files(self, sources_dir):
        managed = sources_dir / 'ayusos-manager-abcdef1234567890.sources'
        managed.write_text('Types: deb\n')
        foreign = sources_dir / 'debian.sources'
        foreign.write_text('Types: deb\n')
        assert admin.main(['delete', managed.name]) == 0
        assert not managed.exists()
        with pytest.raises(ValueError):
            admin.main(['delete', foreign.name])
        assert foreign.exists()

    def test_unknown_command(self):
        with pytest.raises(ValueError, match='no válida'):
            admin.main(['unknown'])


class TestFlatpakArgs:
    """Reconstrucción de las operaciones Flatpak del sistema."""

    def test_valid(self):
        assert admin.system_flatpak_args(['update', '-y']) == [
            '/usr/bin/flatpak', '--system', 'update', '-y']
        args = admin.system_flatpak_args(['update', '-y', '--', 'org.app1', 'org.app2'])
        assert args[:4] == ['/usr/bin/flatpak', '--system', 'update', '-y']
        args = admin.system_flatpak_args(
            ['install', '-y', '--', 'flathub', 'org.app1', 'org.app2'])
        assert args[:5] == ['/usr/bin/flatpak', '--system', 'install', '-y', '--']
        args = admin.system_flatpak_args(
            ['remote-add', '--if-not-exists', '--', 'flathub', 'https://dl.flathub.org/repo/flathub.flatpakrepo'])
        assert args[0] == '/usr/bin/flatpak'

    def test_invalid(self):
        for values in (
            ['invalid'],
            ['install', '-y'],
            ['remote-add', '--if-not-exists', '--'],
            ['remote-add', '--if-not-exists', '--', 'flathub', 'http://insecure.example'],
            ['update', '-y', '--', 'org.app;reboot'],
        ):
            with pytest.raises(ValueError):
                admin.system_flatpak_args(values)


class TestFlatpakRef:
    """Validación de archivos .flatpakref antes de instalarlos."""

    VALID = (
        '[Flatpak Ref]\n'
        'Title=Test\n'
        'Name=org.example.App\n'
        'Branch=stable\n'
        'Url=https://dl.flathub.org/repo/\n'
        'RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo\n'
        'IsRuntime=false\n'
    )

    def test_valid(self):
        fields = admin.parse_flatpakref(self.VALID.encode())
        assert fields['Name'] == 'org.example.App'
        assert fields['Branch'] == 'stable'

    def test_rejects_runtime(self):
        with pytest.raises(ValueError, match='runtime'):
            admin.parse_flatpakref(self.VALID.replace('IsRuntime=false', 'IsRuntime=true').encode())

    def test_rejects_invalid_name(self):
        with pytest.raises(ValueError, match='identificador'):
            admin.parse_flatpakref(self.VALID.replace('org.example.App', 'not-an-app-id').encode())

    def test_rejects_insecure_urls(self):
        with pytest.raises(ValueError, match='HTTPS'):
            admin.parse_flatpakref(self.VALID.replace(
                'Url=https://dl.flathub.org/repo/', 'Url=http://insecure.example/').encode())

    def test_rejects_oversized_file(self):
        with pytest.raises(ValueError, match='demasiado grande'):
            admin.parse_flatpakref(b'x' * (admin.FLATPAKREF_MAX + 1))


class TestTrustedArchive:
    """Verificación del SHA-256 contra los índices APT autenticados."""

    def _apt_pkg(self, sources, trusted_source=None):
        mock = MagicMock()
        mock.config.find_dir.return_value = str(sources)
        mock.config.find_file.return_value = str(sources / 'missing.list')
        if trusted_source:
            (sources / 'custom.sources').write_text(trusted_source)

        version = MagicMock()
        version.file_list = [('index', 'file')]
        cache = MagicMock()
        cache.__getitem__.return_value.version_list = [version]
        mock.Cache.return_value = cache

        index = MagicMock()
        index.is_trusted = True
        indexes = MagicMock()
        indexes.find_index.return_value = index
        mock.SourceList.return_value = indexes

        records = MagicMock()
        records.lookup.return_value = True
        records.sha256_hash = DIGEST
        mock.PackageRecords.return_value = records
        return mock

    def test_found_in_authenticated_index(self, tmp_path):
        with patch.dict(sys.modules, {'apt_pkg': self._apt_pkg(tmp_path)}):
            assert admin.trusted_archive('test-pkg', DIGEST) is True

    def test_rejects_source_with_trusted_override(self, tmp_path):
        mock = self._apt_pkg(tmp_path, 'Types: deb\nTrusted: yes\n')
        with patch.dict(sys.modules, {'apt_pkg': mock}):
            assert admin.trusted_archive('test-pkg', DIGEST) is False

    def test_rejects_invalid_digest(self):
        assert admin.trusted_archive('test-pkg', 'abc123') is False

    def test_without_apt_pkg(self):
        with patch.dict(sys.modules, {'apt_pkg': None}):
            assert admin.trusted_archive('test-pkg', DIGEST) is False


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
