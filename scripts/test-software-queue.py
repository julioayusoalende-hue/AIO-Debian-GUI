#!/usr/bin/env python3
"""Pruebas de la cola del gestor de software y de los lotes privilegiados."""
import sys
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "package/usr/lib/aio-debian-gui"))
from software_manager import admin
from software_manager.manager import SoftwareManagerPage

APT = ['/usr/bin/apt-get', '-y', '-o', 'Dpkg::Options::=--force-confold']
HELPER = ['/usr/bin/pkexec', '/usr/lib/aio-debian-gui/aio-debian-gui-helper', '--software']

# Flatpak del sistema: varias referencias en una sola operación.
refs = ['app/org.example.Uno/x86_64/stable', 'app/org.example.Dos/x86_64/stable']
assert admin.system_flatpak_args(['install', '-y', '--', 'flathub', *refs]) == [
    '/usr/bin/flatpak', '--system', 'install', '-y', '--', 'flathub', *refs]
assert admin.system_flatpak_args(['update', '-y', '--', *refs]) == [
    '/usr/bin/flatpak', '--system', 'update', '-y', '--', *refs]
assert admin.system_flatpak_args(['uninstall', '-y', '--', *refs]) == [
    '/usr/bin/flatpak', '--system', 'uninstall', '-y', '--', *refs]
assert admin.system_flatpak_args(['update', '-y']) == [
    '/usr/bin/flatpak', '--system', 'update', '-y']
for invalid in (
    ['install', '-y', '--', 'flathub'],
    ['uninstall', '-y', '--'],
    ['install', '-y', '--', 'flathub', '../evil'],
    ['update', '-y', '--', 'app/x;rm'],
):
    try:
        admin.system_flatpak_args(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f'Operación Flatpak aceptada: {invalid!r}')

# Lotes APT: los paquetes se validan uno a uno antes de llamar a apt-get.
calls = []


def fake_call(args, env=None, **kwargs):
    calls.append(args)
    return 0


with patch.object(admin.os, 'geteuid', return_value=0), \
        patch.object(admin.subprocess, 'call', side_effect=fake_call):
    admin.main(['install', 'uno', 'dos:amd64'])
    assert calls[-1] == APT + ['install', '--', 'uno', 'dos:amd64']
    admin.main(['upgrade', 'uno', 'dos'])
    assert calls[-1] == APT + ['install', '--only-upgrade', '--', 'uno', 'dos']
    admin.main(['remove', 'uno', 'dos'])
    assert calls[-1] == APT + ['remove', '--', 'uno', 'dos']
    before = len(calls)
    for invalid in (['install'], ['install', 'uno;rm'], ['install', *['p'] * 101]):
        try:
            admin.main(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Lote APT aceptado: {invalid[:2]!r}')
    assert len(calls) == before


class FakePage:
    def __init__(self, passwordless=False):
        self.passwordless = lambda: passwordless

    def admin(self, *args):
        return HELPER + list(args)


page = FakePage()
debs = [
    {'action': 'install', 'identifier': 'uno', 'name': 'Uno', 'origin': 'amd64',
     'page': 0, 'scope': None},
    {'action': 'install', 'identifier': 'dos', 'name': 'Dos', 'origin': 'amd64',
     'page': 0, 'scope': None},
    {'action': 'upgrade', 'identifier': 'tres', 'name': 'Tres', 'origin': 'amd64',
     'page': 0, 'scope': None},
    {'action': 'remove', 'identifier': 'cuatro', 'name': 'Cuatro', 'origin': 'amd64',
     'page': 0, 'scope': None},
]
assert SoftwareManagerPage.queue_commands(page, debs, 0, None) == [
    HELPER + ['install', 'uno', 'dos'],
    HELPER + ['upgrade', 'tres'],
    HELPER + ['remove', 'cuatro'],
]

flatpaks = [
    {'action': 'install', 'identifier': 'app/Uno/x86_64/stable', 'name': 'Uno',
     'origin': 'flathub', 'page': 1, 'scope': 'user'},
    {'action': 'install', 'identifier': 'app/Dos/x86_64/stable', 'name': 'Dos',
     'origin': 'flathub', 'page': 1, 'scope': 'user'},
    {'action': 'install', 'identifier': 'app/Tres/x86_64/stable', 'name': 'Tres',
     'origin': 'otro', 'page': 1, 'scope': 'user'},
    {'action': 'upgrade', 'identifier': 'app/Cuatro/x86_64/stable', 'name': 'Cuatro',
     'origin': 'flathub', 'page': 1, 'scope': 'user'},
    {'action': 'remove', 'identifier': 'app/Cinco/x86_64/stable', 'name': 'Cinco',
     'origin': 'flathub', 'page': 1, 'scope': 'user'},
]
assert SoftwareManagerPage.queue_commands(page, flatpaks, 1, 'user') == [
    ['/usr/bin/flatpak', '--user', 'install', '-y', '--', 'flathub',
     'app/Uno/x86_64/stable', 'app/Dos/x86_64/stable'],
    ['/usr/bin/flatpak', '--user', 'install', '-y', '--', 'otro',
     'app/Tres/x86_64/stable'],
    ['/usr/bin/flatpak', '--user', 'update', '-y', '--', 'app/Cuatro/x86_64/stable'],
    ['/usr/bin/flatpak', '--user', 'uninstall', '-y', '--', 'app/Cinco/x86_64/stable'],
]
assert SoftwareManagerPage.queue_commands(FakePage(True), flatpaks, 1, 'system') == [
    HELPER + ['flatpak-system', 'install', '-y', '--', 'flathub',
              'app/Uno/x86_64/stable', 'app/Dos/x86_64/stable'],
    HELPER + ['flatpak-system', 'install', '-y', '--', 'otro',
              'app/Tres/x86_64/stable'],
    HELPER + ['flatpak-system', 'update', '-y', '--', 'app/Cuatro/x86_64/stable'],
    HELPER + ['flatpak-system', 'uninstall', '-y', '--', 'app/Cinco/x86_64/stable'],
]

print('✔ Cola del gestor de software y lotes APT/Flatpak validados')
