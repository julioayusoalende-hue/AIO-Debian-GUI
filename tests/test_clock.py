"""El mantenimiento no espera la respuesta de un servidor NTP."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'package/usr/lib/aio-debian-gui'))
from aio_core import clock


@pytest.mark.parametrize(('state', 'starts'), [
    ('CanNTP=yes\nNTP=yes\n', False),
    ('CanNTP=no\nNTP=no\n', False),
    ('CanNTP=yes\nNTP=no\n', True),
])
def test_requests_ntp_only_if_needed(state, starts):
    result = subprocess.CompletedProcess([], 0, stdout=state)
    with patch.object(clock.subprocess, 'run', return_value=result) as run:
        clock.solicitar_sincronizacion(list_command)
    assert run.call_count == 1 + starts
    if starts:
        assert run.call_args.args[0] == ['/usr/bin/pkexec', '--disable-internal-agent', clock.ENABLE]


def list_command(*args):
    return list(args)


def test_unavailable_time_service_does_not_raise():
    with patch.object(clock.subprocess, 'run', side_effect=subprocess.TimeoutExpired('timedatectl', 5)):
        clock.solicitar_sincronizacion(Mock(return_value=['timedatectl']))
