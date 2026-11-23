"""Tests for software_manager admin (privileged operations)."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'package', 'usr', 'lib', 'aio-debian-gui'))

from software_manager import admin


class TestAdmin:
    """Tests para funciones de administración."""

    def test_source_contents_valid(self):
        """Test creación de contenido sources válido."""
        with tempfile.NamedTemporaryFile(suffix='.asc', delete=False) as f:
            f.write(b'fake key')
            key_path = f.name

        try:
            content = admin.source_contents(
                'https://example.com/repo',
                'trixie',
                'main contrib',
                key_path
            )
            assert 'Types: deb' in content
            assert 'URIs: https://example.com/repo' in content
            assert 'Suites: trixie' in content
            assert 'Components: main contrib' in content
            assert f'Signed-By: {key_path}' in content
        finally:
            os.unlink(key_path)

    def test_source_contents_invalid_url(self):
        """Test rechazo de URLs inválidas."""
        with tempfile.NamedTemporaryFile(suffix='.asc', delete=False) as f:
            key_path = f.name

        try:
            # HTTP en lugar de HTTPS
            with pytest.raises(ValueError, match='HTTPS'):
                admin.source_contents('http://example.com/repo', 'trixie', 'main', key_path)

            # Con credenciales
            with pytest.raises(ValueError, match='credenciales'):
                admin.source_contents('https://user:pass@example.com/repo', 'trixie', 'main', key_path)
        finally:
            os.unlink(key_path)

    def test_source_contents_invalid_suite(self):
        """Test rechazo de suite inválida."""
        with tempfile.NamedTemporaryFile(suffix='.asc', delete=False) as f:
            key_path = f.name

        try:
            with pytest.raises(ValueError, match='distribución'):
                admin.source_contents('https://example.com/repo', 'invalid/suite', 'main', key_path)
        finally:
            os.unlink(key_path)

    def test_source_contents_invalid_key(self):
        """Test rechazo de clave inválida."""
        # Clave en directorio no permitido
        with tempfile.NamedTemporaryFile(suffix='.asc', delete=False) as f:
            key_path = f.name

        try:
            with pytest.raises(ValueError, match='directorio de llaves'):
                admin.source_contents('https://example.com/repo', 'trixie', 'main', key_path)
        finally:
            os.unlink(key_path)

    def test_package_regex(self):
        """Test regex de validación de paquetes."""
        valid = ['package', 'libfoo', 'pkg-name', 'pkg:name', 'pkg123', 'libfoo-dev:amd64']
        invalid = ['', '-package', 'package-', 'pkg..name', 'pkg/name', 'PACKAGE']

        for pkg in valid:
            assert admin.PACKAGE.fullmatch(pkg), f"Debería ser válido: {pkg}"

        for pkg in invalid:
            assert not admin.PACKAGE.fullmatch(pkg), f"Debería ser inválido: {pkg}"

    def test_token_regex(self):
        """Test regex de tokens."""
        valid = ['token', 'token-name', 'token_name', 'token.name', 'token123', 'TOKEN']
        invalid = ['', '-token', 'token-', 'tok..en']

        for tok in valid:
            assert admin.TOKEN.fullmatch(tok), f"Debería ser válido: {tok}"

        for tok in invalid:
            assert not admin.TOKEN.fullmatch(tok), f"Debería ser inválido: {tok}"

    def test_apt_source_regex(self):
        """Test regex de archivos APT."""
        valid = ['pkg.list', 'pkg.sources', 'pkg.list.disabled', 'pkg.sources.disabled']
        invalid = ['pkg', 'pkg.txt', '.list', '.sources']

        for src in valid:
            assert admin.APT_SOURCE.fullmatch(src), f"Debería ser válido: {src}"

        for src in invalid:
            assert not admin.APT_SOURCE.fullmatch(src), f"Debería ser inválido: {src}"

    def test_managed_regex(self):
        """Test regex de archivos gestionados."""
        valid = ['ayusos-manager-abcdef1234567890.sources', 'ayusos-manager-abcdef1234567890.sources.disabled']
        invalid = ['ayusos-manager-abc.sources', 'pkg.sources', 'ayusos-manager-abcdef1234567890.list']

        for src in valid:
            assert admin.MANAGED.fullmatch(src), f"Debería ser válido: {src}"

        for src in invalid:
            assert not admin.MANAGED.fullmatch(src), f"Debería ser inválido: {src}"

    @patch('software_manager.admin.subprocess.call')
    def test_main_refresh(self, mock_call):
        """Test comando refresh."""
        mock_call.return_value = 0
        result = admin.main(['refresh'])
        assert result == 0
        mock_call.assert_called_once()
        args = mock_call.call_args[0][0]
        assert 'apt-get' in args[0]
        assert 'update' in args

    @patch('software_manager.admin.subprocess.call')
    def test_main_install(self, mock_call):
        """Test comando install."""
        mock_call.return_value = 0
        result = admin.main(['install', 'pkg1', 'pkg2'])
        assert result == 0
        args = mock_call.call_args[0][0]
        assert 'apt-get' in args[0]
        assert 'install' in args
        assert 'pkg1' in args
        assert 'pkg2' in args

    @patch('software_manager.admin.subprocess.call')
    def test_main_upgrade(self, mock_call):
        """Test comando upgrade."""
        mock_call.return_value = 0
        result = admin.main(['upgrade', 'pkg1'])
        assert result == 0
        args = mock_call.call_args[0][0]
        assert 'install' in args
        assert '--only-upgrade' in args

    @patch('software_manager.admin.subprocess.call')
    def test_main_remove(self, mock_call):
        """Test comando remove."""
        mock_call.return_value = 0
        result = admin.main(['remove', 'pkg1'])
        assert result == 0
        args = mock_call.call_args[0][0]
        assert 'remove' in args
        assert 'pkg1' in args

    @patch('software_manager.admin.subprocess.call')
    def test_main_add_source(self, mock_call):
        """Test comando add-source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / 'key.asc'
            key_path.write_text('fake key')

            # Mock SOURCES directory
            with patch('software_manager.admin.SOURCES', Path(tmpdir)):
                result = admin.main(['add-source', 'https://example.com/repo', 'trixie', 'main', str(key_path)])
                assert result == 0

    def test_write_source_creates_file(self):
        """Test que write_source crea archivo con nombre hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sources_dir = Path(tmpdir)
            sources_dir.mkdir()

            with patch('software_manager.admin.SOURCES', sources_dir):
                content = admin.source_contents('https://example.com/repo', 'trixie', 'main', '/fake/key.asc')
                admin.write_source('https://example.com/repo', 'trixie', 'main', '/fake/key.asc')

                # Verificar que se creó archivo
                files = list(sources_dir.glob('ayusos-manager-*.sources'))
                assert len(files) == 1
                assert files[0].read_text() == content

    def test_system_flatpak_args_valid(self):
        """Test validación de args Flatpak del sistema."""
        # update simple
        args = admin.system_flatpak_args(['update', '-y'])
        assert args == ['/usr/bin/flatpak', '--system', 'update', '-y']

        # update con refs
        args = admin.system_flatpak_args(['update', '-y', '--', 'org.app1', 'org.app2'])
        assert args[:4] == ['/usr/bin/flatpak', '--system', 'update', '-y']
        assert 'org.app1' in args
        assert 'org.app2' in args

        # install
        args = admin.system_flatpak_args(['install', '-y', '--', 'flathub', 'org.app1', 'org.app2'])
        assert args[:5] == ['/usr/bin/flatpak', '--system', 'install', '-y', '--']
        assert 'flathub' in args
        assert 'org.app1' in args

    def test_system_flatpak_args_invalid(self):
        """Test rechazo de args Flatpak inválidos."""
        with pytest.raises(ValueError):
            admin.system_flatpak_args(['invalid'])

        with pytest.raises(ValueError):
            admin.system_flatpak_args(['install', '-y'])  # Falta ref

        with pytest.raises(ValueError):
            admin.system_flatpak_args(['remote-add', '--if-not-exists', '--'])  # Faltan args


class TestTrustedArchive:
    """Tests para verificación de archivo confiable."""

    @patch('software_manager.admin.apt_pkg')
    def test_trusted_archive_found(self, mock_apt_pkg):
        """Test cuando el archivo está en índice confiable."""
        # Configurar mock
        mock_cache = MagicMock()
        mock_version = MagicMock()
        mock_version.file_list = [('index1', 'file1')]
        mock_cache.__getitem__.return_value.version_list = [mock_version]

        mock_indexes = MagicMock()
        mock_index = MagicMock()
        mock_index.is_trusted = True
        mock_indexes.find_index.return_value = mock_index

        mock_records = MagicMock()
        mock_records.lookup.return_value = True
        mock_records.sha256_hash = 'abc123'

        mock_apt_pkg.Cache.return_value = mock_cache
        mock_apt_pkg.SourceList.return_value = mock_indexes
        mock_apt_pkg.PackageRecords.return_value = mock_records
        mock_apt_pkg.config.find_dir.return_value = '/etc/apt/sources.list.d'
        mock_apt_pkg.config.find_file.return_value = '/etc/apt/sources.list'

        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value=''):
                result = admin.trusted_archive('test-pkg', 'abc123')
                assert result is True

    @patch('software_manager.admin.apt_pkg', None)
    def test_trusted_archive_no_apt_pkg(self):
        """Test cuando apt_pkg no está disponible."""
        result = admin.trusted_archive('test-pkg', 'abc123')
        assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])