"""Tests for software_manager backend."""

import os
import sys
import tempfile
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ayusos-control-center', 'package', 'usr', 'lib', 'aio-debian-gui', 'extensions', 'ayusos'))

from software_manager import backend

APT_LIST = """Listing...
package1/trixie 1.0 all [installed]
package2/trixie 2.0 amd64 [upgradable from: 1.9]
package3/trixie 3.0 all
"""


class TestDebs:
    """Catálogo de paquetes DEB a partir de apt list."""

    @patch('software_manager.backend.run')
    def test_parses_apt_list(self, mock_run):
        mock_run.return_value = APT_LIST
        rows, errors, descriptions = backend.debs()

        assert rows == [
            ('package1', 'package1', '1.0', 'Instalado', 'all'),
            ('package2', 'package2:amd64', '2.0', 'Actualizable', 'amd64'),
            ('package3', 'package3', '3.0', 'Disponible', 'all'),
        ]
        assert errors == []
        assert descriptions == {}

    @patch('software_manager.backend.run')
    def test_collects_descriptions(self, mock_run):
        mock_run.side_effect = [
            APT_LIST,
            'Package: package1\nDescription: First package\n long text\n\n'
            'Package: package2\nDescription: Second package\n',
        ]
        _, _, descriptions = backend.debs()

        assert descriptions['package1'] == 'First package long text'
        assert descriptions['package2'] == 'Second package'

    @patch('software_manager.backend.run')
    def test_ignores_malformed_lines(self, mock_run):
        mock_run.return_value = 'Listing...\nno-repo 1.0 all\nbroken/line\n'
        rows, _, _ = backend.debs()
        assert rows == []


class TestDebDetails:
    """Detalles de un paquete DEB concreto."""

    @patch('software_manager.backend.run')
    def test_includes_fields_and_candidate(self, mock_run):
        mock_run.side_effect = [
            'Package: test-pkg\n'
            'Version: 1.0\n'
            'Architecture: amd64\n'
            'Depends: libc6, libstdc++6\n'
            'Description: Test package\n'
            ' Long description\n',
            'test-pkg:\n  Installed: 1.0\n  Candidate: 1.1\n',
        ]

        details = backend.deb_details('test-pkg', '1.0', 'amd64', True)

        assert details['Version'] == '1.0'
        assert details['Architecture'] == 'amd64'
        assert details['Depends'] == 'libc6, libstdc++6'
        assert details['Description'] == 'Test package Long description'
        assert details['Versión disponible'] == '1.1'

    @patch('software_manager.backend.run')
    def test_falls_back_to_dpkg_for_installed_package(self, mock_run):
        mock_run.side_effect = [
            RuntimeError('not in the index'),
            'Package: test-pkg\nVersion: 1.0\nArchitecture: all\n',
        ]
        details = backend.deb_details('test-pkg', '1.0', 'all')
        assert details['Version'] == '1.0'

    @patch('software_manager.backend.run')
    def test_returns_empty_when_unknown(self, mock_run):
        mock_run.side_effect = [
            'Package: other\nVersion: 2.0\nArchitecture: all\n',
            'dpkg-query: no packages found',
        ]
        assert backend.deb_details('test-pkg', '1.0', 'all') == {}


class TestFlatpakDetails:
    """Detalles de aplicaciones Flatpak."""

    @patch('software_manager.backend.run')
    def test_installed_app(self, mock_run):
        mock_run.return_value = """Test application - Does useful things
    Ref: org.example.App/x86_64/stable
    ID: org.example.App
    Runtime: org.freedesktop.Platform/x86_64/23.08
    Version: 1.0
    Branch: stable
    License: MIT
    Download Size: 10.5 MB
    Installed Size: 45.2 MB
"""
        details = backend.flatpak_details('user', 'flathub', 'org.example.App', True)

        assert details['Description'] == 'Does useful things Ref: org.example.App/x86_64/stable'
        assert details['Runtime'] == 'org.freedesktop.Platform/x86_64/23.08'
        assert details['Version'] == '1.0'
        assert details['Branch'] == 'stable'
        assert details['License'] == 'MIT'
        assert details['Installed Size'] == '45.2 MB'

    @patch('software_manager.backend.run')
    def test_reports_new_version_when_installed(self, mock_run):
        mock_run.return_value = '    ID: org.example.App\n    Version: 1.0\n'
        details = backend.flatpak_details(
            'system', 'flathub', 'org.example.App', True, new_version='1.1')
        assert details['Versión disponible'] == '1.1'


class TestColumns:
    """Salida de Flatpak separada por tabuladores."""

    def test_columns_parsing(self):
        output = 'col1\tcol2\tcol3\nval1\tval2\tval3\n'
        result = list(backend.columns(output, 3))
        assert result == [['col1', 'col2', 'col3'], ['val1', 'val2', 'val3']]

    def test_columns_missing_values(self):
        output = 'col1\tcol2\nval1\t'
        result = list(backend.columns(output, 3))
        assert result == [['col1', 'col2', ''], ['val1', '', '']]


class TestPreviewLocalDeb:
    """Análisis de un .deb local antes de instalarlo."""

    @patch('software_manager.backend.run')
    def test_preview(self, mock_run):
        with tempfile.NamedTemporaryFile(suffix='.deb', delete=False) as stream:
            stream.write(b'fake deb content')
            deb_path = stream.name

        try:
            mock_run.side_effect = [
                'Package: test-pkg\nVersion: 1.0\nArchitecture: all\n'
                'Description: Test\nDepends: libc6\n',
                'test-pkg',
                'The following NEW packages will be installed:\n  test-pkg\n',
            ]

            with patch('software_manager.backend.trusted_archive', return_value=False):
                digest, package, trusted, details = backend.preview_local_deb(deb_path)

            assert len(digest) == 64
            assert package == 'test-pkg'
            assert trusted is False
            assert 'test-pkg' in details
        finally:
            os.unlink(deb_path)

    def test_rejects_non_deb_file(self, tmp_path):
        path = tmp_path / 'app.flatpakref'
        path.write_text('x')
        with pytest.raises(ValueError, match='\\.deb'):
            backend.preview_local_deb(path)


class TestDeb822Records:
    """Parser de registros deb822 (apt-cache show, dpkg-query -s)."""

    def test_simple_record(self):
        records = list(backend._deb822_records(
            'Package: test\nVersion: 1.0\nDescription: A test package\n'))
        assert records == [{'Package': 'test', 'Version': '1.0',
                            'Description': 'A test package'}]

    def test_multiline_description(self):
        records = list(backend._deb822_records(
            'Package: test\nDescription: First line\n Second line\n Third line\n'))
        assert records[0]['Description'] == 'First line Second line Third line'

    def test_multiple_records(self):
        records = list(backend._deb822_records(
            'Package: pkg1\nVersion: 1.0\n\nPackage: pkg2\nVersion: 2.0\n'))
        assert [record['Package'] for record in records] == ['pkg1', 'pkg2']

    def test_continuation_lines(self):
        records = list(backend._deb822_records(
            'Package: test\nDepends: libc6,\n libstdc++6,\n libgcc1\n'))
        assert records[0]['Depends'] == 'libc6, libstdc++6, libgcc1'


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
