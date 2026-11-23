"""Tests for software_manager backend."""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock, Mock

# Importar el módulo a testear
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'package', 'usr', 'lib', 'aio-debian-gui'))

from software_manager import backend


class TestBackend:
    """Tests para funciones del backend."""

    @patch('software_manager.backend.run')
    def test_debs_parsing(self, mock_run):
        """Test parsing de salida de apt list."""
        mock_run.return_value = """Listing...
package1/1.0 all [installed]
package2/2.0 amd64 [upgradable from: 1.9]
package3/3.0 all
"""
        rows, errors, descriptions = backend.debs()

        assert len(rows) == 3
        assert rows[0] == ('package1', 'package1', '1.0', 'Instalado', 'all')
        assert rows[1] == ('package2', 'package2:amd64', '2.0', 'Actualizable', 'amd64')
        assert rows[2] == ('package3', 'package3', '3.0', 'Disponible', 'all')
        assert errors == []

    @patch('software_manager.backend.run')
    def test_deb_details(self, mock_run):
        """Test obtención de detalles de paquete DEB."""
        mock_run.side_effect = [
            # apt-cache show
            """Package: test-pkg
Version: 1.0
Architecture: amd64
Depends: libc6, libstdc++6
Description: Test package
""",
            # apt-cache policy
            """test-pkg:
  Installed: 1.0
  Candidate: 1.1
"""
        ]

        details = backend.deb_details('test-pkg', '1.0', 'amd64', True)

        assert details['Package'] == 'test-pkg'
        assert details['Version'] == '1.0'
        assert details['Architecture'] == 'amd64'
        assert 'libc6' in details['Depends']
        assert details['Description'] == 'Test package'
        assert details['Versión disponible'] == '1.1'

    @patch('software_manager.backend.run')
    def test_flatpak_details_installed(self, mock_run):
        """Test detalles de Flatpak instalado."""
        mock_run.return_value = """    Ref: org.example.App/x86_64/stable
    ID: org.example.App
    Runtime: org.freedesktop.Platform/x86_64/23.08
    Version: 1.0
    Branch: stable
    License: MIT
    Download Size: 10.5 MB
    Installed Size: 45.2 MB
"""

        details = backend.flatpak_details('user', 'flathub', 'org.example.App', True)

        assert details['ID'] == 'org.example.App'
        assert details['Runtime'] == 'org.freedesktop.Platform/x86_64/23.08'
        assert details['Version'] == '1.0'
        assert details['Branch'] == 'stable'
        assert details['License'] == 'MIT'

    def test_columns_parsing(self):
        """Test parsing de columnas tab-separated."""
        output = "col1\tcol2\tcol3\nval1\tval2\tval3\n"
        result = list(backend.columns(output, 3))
        assert len(result) == 2
        assert result[0] == ['col1', 'col2', 'col3']
        assert result[1] == ['val1', 'val2', 'val3']

    def test_columns_missing_values(self):
        """Test parsing con valores faltantes."""
        output = "col1\tcol2\nval1\t"
        result = list(backend.columns(output, 3))
        assert result[0] == ['col1', 'col2', '']
        assert result[1] == ['val1', '', '']

    @patch('software_manager.backend.run')
    def test_preview_local_deb(self, mock_run):
        """Test análisis de .deb local."""
        # Crear archivo .deb temporal falso
        with tempfile.NamedTemporaryFile(suffix='.deb', delete=False) as f:
            f.write(b'fake deb content')
            deb_path = f.name

        try:
            mock_run.side_effect = [
                # dpkg-deb -f (metadata)
                "Package: test-pkg\nVersion: 1.0\nArchitecture: all\nDescription: Test\nDepends: libc6\n",
                # dpkg-deb -f (package name)
                "test-pkg",
                # apt-get -s install
                "Reading package lists...\nBuilding dependency tree...\nThe following NEW packages will be installed:\n  test-pkg\n"
            ]

            with patch('software_manager.backend.trusted_archive', return_value=False):
                digest, package, trusted, details = backend.preview_local_deb(deb_path)

            assert package == 'test-pkg'
            assert trusted is False
            assert 'test-pkg' in details
        finally:
            os.unlink(deb_path)


class TestDeb822Records:
    """Tests para parsing de registros deb822."""

    def test_simple_record(self):
        output = """Package: test
Version: 1.0
Description: A test package
"""
        records = list(backend._deb822_records(output))
        assert len(records) == 1
        assert records[0]['Package'] == 'test'
        assert records[0]['Version'] == '1.0'

    def test_multiline_description(self):
        output = """Package: test
Description: First line
 Second line
 Third line
"""
        records = list(backend._deb822_records(output))
        assert records[0]['Description'] == 'First line Second line Third line'

    def test_multiple_records(self):
        output = """Package: pkg1
Version: 1.0

Package: pkg2
Version: 2.0
"""
        records = list(backend._deb822_records(output))
        assert len(records) == 2
        assert records[0]['Package'] == 'pkg1'
        assert records[1]['Package'] == 'pkg2'

    def test_continuation_lines(self):
        output = """Package: test
Depends: libc6,
 libstdc++6,
 libgcc1
"""
        records = list(backend._deb822_records(output))
        assert 'libc6, libstdc++6, libgcc1' in records[0]['Depends']


class TestSearchIndex:
    """Tests para índice de búsqueda."""

    def test_build_and_search(self):
        index = backend.SearchIndex()
        rows = [
            ('pkg1', 'pkg1', '1.0', 'Instalado', 'all'),
            ('pkg2', 'pkg2', '2.0', 'Disponible', 'all'),
            ('libfoo', 'libfoo', '1.0', 'Instalado', 'all'),
        ]
        extra = {
            'descriptions': {'pkg1': 'Package one', 'pkg2': 'Package two', 'libfoo': 'Foo library'},
            'sections': {'pkg1': 'utils', 'pkg2': 'devel', 'libfoo': 'libs'},
        }
        index.build(rows, extra)

        # Búsqueda por nombre
        results = index.search('pkg1')
        assert results == [0]

        # Búsqueda por descripción
        results = index.search('package')
        assert set(results) == {0, 1}

        # Búsqueda por sección
        results = index.search('libs')
        assert results == [2]

        # Búsqueda sin resultados
        results = index.search('nonexistent')
        assert results == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])