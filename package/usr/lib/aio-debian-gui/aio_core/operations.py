"""Coordinación global de operaciones administrativas de la interfaz."""

import threading


class OperationCoordinator:
    """Impede que dos operaciones privilegiadas se solapen en la aplicación."""

    def __init__(self):
        self._active = {}
        self._listeners = []
        self._lock = threading.RLock()

    def try_acquire(self, name):
        """Registra una operación si no hay otra activa."""
        with self._lock:
            if self._active:
                return None
            token = object()
            self._active[token] = name
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener()
        return token

    def release(self, token):
        """Libera una operación previamente registrada."""
        with self._lock:
            removed = self._active.pop(token, None)
            listeners = tuple(self._listeners)
        if removed is not None:
            for listener in listeners:
                listener()

    def busy(self):
        with self._lock:
            return bool(self._active)

    def names(self):
        with self._lock:
            return tuple(self._active.values())

    def add_listener(self, listener):
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener):
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)


coordinator = OperationCoordinator()
