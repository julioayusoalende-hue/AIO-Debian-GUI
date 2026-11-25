"""Instalación segura de extensiones de GNOME desde una lista blanca."""

import io
import json
import os
import sys
import zipfile
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'package', 'usr', 'lib', 'aio-debian-gui'))

from aio_core import gnome_extensions

TASK = 'gnome-ext-appindicator'
UUID = 'appindicatorsupport@rgcjonas.gmail.com'


def bundle(metadata=None, nested=False):
    data = io.BytesIO()
    metadata = metadata or {'uuid': UUID}
    with zipfile.ZipFile(data, 'w') as archive:
        prefix = f'{UUID}/' if nested else ''
        archive.writestr(prefix + 'metadata.json', json.dumps(metadata))
        archive.writestr(prefix + 'extension.js', '// test')
    return data.getvalue()


def test_allowlist_has_expected_extensions():
    assert gnome_extensions.EXTENSIONS == {
        'gnome-ext-appindicator': 'appindicatorsupport@rgcjonas.gmail.com',
        'gnome-ext-blur-shell': 'blur-my-shell@aunetx',
        'gnome-ext-caffeine': 'caffeine@patapon.info',
        'gnome-ext-clipboard-indicator': 'clipboard-indicator@tudmotu.com',
        'gnome-ext-dash-to-dock': 'dash-to-dock@micxgx.gmail.com',
        'gnome-ext-places-status': 'places-menu@gnome-shell-extensions.gcampax.github.com',
        'gnome-ext-tiling-shell': 'tilingshell@ferrarodomenico.com',
    }


def test_unknown_task_is_rejected():
    with pytest.raises(ValueError, match='no permitida'):
        gnome_extensions.uuid_for('gnome-ext-arbitrary')


def test_validate_root_metadata(tmp_path):
    path = tmp_path / 'extension.zip'
    path.write_bytes(bundle())
    gnome_extensions.validate(TASK, path)


def test_validate_nested_metadata(tmp_path):
    path = tmp_path / 'extension.zip'
    path.write_bytes(bundle(nested=True))
    gnome_extensions.validate(TASK, path)


def test_validate_rejects_wrong_uuid(tmp_path):
    path = tmp_path / 'extension.zip'
    path.write_bytes(bundle({'uuid': 'other@example.com'}))
    with pytest.raises(ValueError, match='UUID'):
        gnome_extensions.validate(TASK, path)


def test_validate_rejects_missing_metadata(tmp_path):
    path = tmp_path / 'extension.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('extension.js', '// test')
    with pytest.raises(ValueError, match='metadata.json'):
        gnome_extensions.validate(TASK, path)


def test_download_uses_compatible_version_from_extensions_site(tmp_path):
    content = bundle()
    info = io.BytesIO(json.dumps({
        "uuid": UUID,
        "download_url": f"/download-extension/{UUID}.shell-extension.zip?version_tag=123",
    }).encode())
    response = io.BytesIO(content)
    output = tmp_path / 'extension.zip'
    with patch.object(gnome_extensions, 'shell_version', return_value='48.7'), \
         patch.object(gnome_extensions.urllib.request, 'urlopen', side_effect=[info, response]) as open_url:
        gnome_extensions.download(TASK, output)
    info_request = open_url.call_args_list[0][0][0]
    download_request = open_url.call_args_list[1][0][0]
    assert info_request.full_url.startswith('https://extensions.gnome.org/extension-info/?')
    assert f'uuid={UUID.replace("@", "%40")}' in info_request.full_url
    assert download_request.full_url == (
        f'https://extensions.gnome.org/download-extension/{UUID}.shell-extension.zip?version_tag=123')
    assert output.read_bytes() == content


def test_download_url_rejects_external_host(tmp_path):
    info = io.BytesIO(json.dumps({
        "uuid": UUID,
        "download_url": "https://evil.example/extension.zip",
    }).encode())
    with patch.object(gnome_extensions, 'shell_version', return_value='48.7'), \
         patch.object(gnome_extensions.urllib.request, 'urlopen', return_value=info):
        with pytest.raises(ValueError, match='origen'):
            gnome_extensions.download_url(TASK)


def test_install_uses_gnome_extensions_as_user(tmp_path):
    path = tmp_path / 'extension.zip'
    path.write_bytes(bundle())
    with patch.object(gnome_extensions.subprocess, 'run') as run:
        gnome_extensions.install(TASK, path)
    args, kwargs = run.call_args
    assert args[0] == ['gnome-extensions', 'install', '--force', str(path)]
    assert kwargs['check'] is True
    assert kwargs['stdin'] is gnome_extensions.subprocess.DEVNULL


def test_installed_parses_uuid_lines():
    result = type('Result', (), {
        'returncode': 0,
        'stdout': f'{UUID}\nother@example.com\n',
        'stderr': '',
    })()
    with patch.object(gnome_extensions.subprocess, 'run', return_value=result):
        assert gnome_extensions.installed() == {UUID, 'other@example.com'}


def test_validate_rejects_unsafe_paths(tmp_path):
    path = tmp_path / 'extension.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('../metadata.json', json.dumps({'uuid': UUID}))
    with pytest.raises(ValueError, match='rutas no seguras'):
        gnome_extensions.validate(TASK, path)


def test_validate_enforces_unpacked_size_limit(tmp_path, monkeypatch):
    path = tmp_path / 'extension.zip'
    path.write_bytes(bundle())
    monkeypatch.setattr(gnome_extensions, 'MAX_UNPACKED_BYTES', 1)
    with pytest.raises(ValueError, match='límites de tamaño'):
        gnome_extensions.validate(TASK, path)


def test_validate_enforces_file_count_limit(tmp_path, monkeypatch):
    path = tmp_path / 'extension.zip'
    path.write_bytes(bundle())
    monkeypatch.setattr(gnome_extensions, 'MAX_FILES', 0)
    with pytest.raises(ValueError, match='límites de tamaño'):
        gnome_extensions.validate(TASK, path)
