"""Coordinación global de operaciones administrativas."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'package', 'usr', 'lib', 'aio-debian-gui'))

from aio_core.operations import OperationCoordinator


def test_only_one_operation_can_be_active():
    coordinator = OperationCoordinator()
    token = coordinator.try_acquire('mantenimiento')

    assert token is not None
    assert coordinator.busy()
    assert coordinator.names() == ('mantenimiento',)
    assert coordinator.try_acquire('software') is None

    coordinator.release(token)

    assert not coordinator.busy()
    assert coordinator.try_acquire('software') is not None


def test_listeners_are_notified_when_state_changes():
    coordinator = OperationCoordinator()
    estados = []
    coordinator.add_listener(lambda: estados.append(coordinator.busy()))

    token = coordinator.try_acquire('diagnóstico')
    coordinator.release(token)

    assert estados == [True, False]


def test_releasing_unknown_token_does_not_change_state():
    coordinator = OperationCoordinator()
    token = coordinator.try_acquire('firmware')

    coordinator.release(object())

    assert coordinator.busy()
    assert coordinator.names() == ('firmware',)
    coordinator.release(token)
    assert not coordinator.busy()
