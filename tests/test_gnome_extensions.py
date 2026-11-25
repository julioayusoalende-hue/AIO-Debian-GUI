"""Instalación de extensiones de GNOME mediante la API oficial de Shell."""

import io
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'package', 'usr', 'lib', 'aio-debian-gui'))

from aio_core import gnome_extensions

TASK = 'gnome-ext-appindicator'
UUID = 'appindicatorsupport@rgcjonas.gmail.com'


def info(download_url=None):
    return {
        'uuid': UUID,
        'download_url': download_url or f'/download-extension/{UUID}.shell-extension.zip?version_tag=123',
    }


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


def test_shell_version_is_parsed():
    result = type('Result', (), {'returncode': 0, 'stdout': 'GNOME Shell 48.7\n', 'stderr': ''})()
    with patch.object(gnome_extensions.subprocess, 'run', return_value=result):
        assert gnome_extensions.shell_version() == '48.7'


def test_extension_info_uses_installed_shell_version():
    response = io.BytesIO(json.dumps(info()).encode())
    with patch.object(gnome_extensions, 'shell_version', return_value='48.7'), \
         patch.object(gnome_extensions.urllib.request, 'urlopen', return_value=response) as open_url:
        assert gnome_extensions.extension_info(TASK)['uuid'] == UUID
    request = open_url.call_args[0][0]
    assert request.full_url.startswith('https://extensions.gnome.org/extension-info/?')
    assert 'shell_version=48.7' in request.full_url


def test_extension_info_rejects_external_download_host():
    response = io.BytesIO(json.dumps(info('https://evil.example/extension.zip')).encode())
    with patch.object(gnome_extensions, 'shell_version', return_value='48.7'), \
         patch.object(gnome_extensions.urllib.request, 'urlopen', return_value=response):
        with pytest.raises(ValueError, match='origen'):
            gnome_extensions.extension_info(TASK)


def test_install_remote_uses_shell_api():
    result = type('Result', (), {'returncode': 0, 'stdout': "('successful',)\n", 'stderr': ''})()
    with patch.object(gnome_extensions, 'extension_info', return_value=info()), \
         patch.object(gnome_extensions.subprocess, 'run', return_value=result) as run:
        gnome_extensions.install_remote(TASK)
    command = run.call_args.args[0]
    assert command == [
        'gdbus', 'call', '--session', '--dest', 'org.gnome.Shell.Extensions',
        '--object-path', '/org/gnome/Shell/Extensions',
        '--method', 'org.gnome.Shell.Extensions.InstallRemoteExtension', UUID,
    ]
    assert run.call_args.kwargs['timeout'] == 180


def test_install_remote_reports_cancelled_or_failed():
    result = type('Result', (), {'returncode': 0, 'stdout': "('cancelled',)\n", 'stderr': ''})()
    with patch.object(gnome_extensions, 'extension_info', return_value=info()), \
         patch.object(gnome_extensions.subprocess, 'run', return_value=result):
        with pytest.raises(RuntimeError, match='canceló'):
            gnome_extensions.install_remote(TASK)


def test_installed_parses_uuid_lines():
    result = type('Result', (), {
        'returncode': 0,
        'stdout': f'{UUID}\nother@example.com\n',
        'stderr': '',
    })()
    with patch.object(gnome_extensions.subprocess, 'run', return_value=result):
        assert gnome_extensions.installed() == {UUID, 'other@example.com'}
