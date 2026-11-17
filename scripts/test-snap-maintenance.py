#!/usr/bin/env python3
"""Host detection visibility and scheduled Snap task selection without real snapd."""
import ast
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest import mock
sys.path.insert(0, str(Path('package/usr/lib/aio-debian-gui').resolve()))
from aio_core import scheduler, preflight
source = ast.parse(Path('package/usr/bin/aio-debian-gui').read_text())
window = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'VentanaPrincipal')
visible = next(n for n in window.body if isinstance(n, ast.FunctionDef) and n.name == '_visible')
ns = {}
exec(compile(ast.Module(body=[visible], type_ignores=[]), '<visibility>', 'exec'), ns)
for installed in (False, True):
    assert ns['_visible'](SimpleNamespace(snapd_presente=installed), 'snap-update') is installed
steps = next(n.value for n in source.body if isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PASOS' for t in n.targets))
snap = next(p for p in ast.literal_eval(steps) if p[0]=='snap-update')
assert snap[3] is True
for tasks in (['snap-update'], ['flatpak-update', 'snap-update']):
    assert 'snap-update' in scheduler.validate_config({**scheduler.DEFAULT, 'tasks':tasks})['tasks']
    with mock.patch.object(preflight, '_apt_locks', side_effect=AssertionError('Snap does not use APT')):
        assert not preflight._check_local(tasks).blocked
assert scheduler.validate_config(scheduler.DEFAULT) == scheduler.DEFAULT
print('✔ Snap host visibility, default selection, scheduling and independent preflight')
