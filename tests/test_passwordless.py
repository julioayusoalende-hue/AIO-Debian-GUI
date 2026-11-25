"""Detección persistente de la excepción de Polkit de AiO."""

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'package', 'usr', 'lib', 'aio-debian-gui'))

from aio_core import constants

VALID_RULE = '''polkit.addRule(function(action, subject) {
    if (action.id === "es.aiodebian.gui.mantenimiento" &&
        action.lookup("program") === "/usr/lib/aio-debian-gui/aio-debian-gui-helper" &&
        subject.user === "julio" &&
        subject.local &&
        subject.active) {
        return polkit.Result.YES;
    }
});
'''


def _paths():
    uid = 1000
    return (
        os.path.join(constants.POLKIT_RULES_DIR, f'50-aiodebian-gui-{uid}.rules'),
        os.path.join(constants.PASSWORDLESS_STATE_DIR, f'{uid}.rules'),
    )


def test_readable_valid_rule_is_active():
    rule, _ = _paths()
    with patch.object(constants.os, 'getuid', return_value=1000), \
         patch.object(constants.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='julio')), \
         patch.object(constants, 'leer_texto', side_effect=lambda path: VALID_RULE if path == rule else None):
        assert constants.autorizacion_sin_contrasena_activa() is True


def test_readable_invalid_rule_is_not_active():
    rule, _ = _paths()
    with patch.object(constants.os, 'getuid', return_value=1000), \
         patch.object(constants.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='julio')), \
         patch.object(constants, 'leer_texto', side_effect=lambda path: 'invalid' if path == rule else None):
        assert constants.autorizacion_sin_contrasena_activa() is False


def test_secure_rules_directory_uses_marker():
    _, marker = _paths()
    with patch.object(constants.os, 'getuid', return_value=1000), \
         patch.object(constants.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='julio')), \
         patch.object(constants, 'leer_texto', side_effect=lambda path: VALID_RULE if path == marker else None), \
         patch.object(constants, '_existe_en_anfitrion', return_value=False), \
         patch.object(constants, '_directorio_legible_en_anfitrion', return_value=False):
        assert constants.autorizacion_sin_contrasena_activa() is True


def test_secure_rules_directory_without_marker_is_not_active():
    with patch.object(constants.os, 'getuid', return_value=1000), \
         patch.object(constants.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='julio')), \
         patch.object(constants, 'leer_texto', return_value=None), \
         patch.object(constants, '_existe_en_anfitrion', return_value=False), \
         patch.object(constants, '_directorio_legible_en_anfitrion', return_value=False):
        assert constants.autorizacion_sin_contrasena_activa() is False


def test_missing_rule_in_accessible_directory_ignores_stale_marker():
    _, marker = _paths()
    with patch.object(constants.os, 'getuid', return_value=1000), \
         patch.object(constants.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='julio')), \
         patch.object(constants, 'leer_texto', side_effect=lambda path: VALID_RULE if path == marker else None), \
         patch.object(constants, '_existe_en_anfitrion', return_value=False), \
         patch.object(constants, '_directorio_legible_en_anfitrion', return_value=True):
        assert constants.autorizacion_sin_contrasena_activa() is False


def test_unreadable_existing_rule_uses_marker():
    _, marker = _paths()
    with patch.object(constants.os, 'getuid', return_value=1000), \
         patch.object(constants.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='julio')), \
         patch.object(constants, 'leer_texto', side_effect=lambda path: VALID_RULE if path == marker else None), \
         patch.object(constants, '_existe_en_anfitrion', return_value=True), \
         patch.object(constants, '_directorio_legible_en_anfitrion', return_value=True):
        assert constants.autorizacion_sin_contrasena_activa() is True


def test_invalid_marker_is_not_active():
    _, marker = _paths()
    with patch.object(constants.os, 'getuid', return_value=1000), \
         patch.object(constants.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='julio')), \
         patch.object(constants, 'leer_texto', side_effect=lambda path: 'invalid' if path == marker else None), \
         patch.object(constants, '_existe_en_anfitrion', return_value=False), \
         patch.object(constants, '_directorio_legible_en_anfitrion', return_value=False):
        assert constants.autorizacion_sin_contrasena_activa() is False
