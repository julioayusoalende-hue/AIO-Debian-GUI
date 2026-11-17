"""Lectura acotada de solicitudes locales autorizadas por el administrador."""
import os
from pathlib import Path
import re
import stat

CONFIG_DIR = Path("/etc/aio-debian-gui")
RUNTIME_DIR = Path("/run/user")
ROOT_UID = 0


def _uid(value):
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) >= 2**32 - 1:
        raise ValueError("UID autorizado no válido.")
    return int(value)


def authorized_users():
    directory = os.open(CONFIG_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory)
        if info.st_uid != ROOT_UID or info.st_mode & 0o022:
            raise RuntimeError("Directorio de autorización inseguro.")
        fd = os.open("host-users", os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                     dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != ROOT_UID
                or info.st_mode & 0o022 or info.st_nlink != 1):
            raise RuntimeError("Lista de usuarios autorizados insegura.")
        data = stream.read(4097)
    if len(data) > 4096:
        raise ValueError("Lista de usuarios autorizados demasiado grande.")
    lines = data.decode("ascii").splitlines()
    users = [_uid(line) for line in lines]
    if len(set(users)) != len(users):
        raise ValueError("Lista de usuarios autorizados duplicada.")
    return users


def read_request(uid):
    uid = _uid(str(uid))
    try:
        directory = os.open(RUNTIME_DIR / str(uid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(directory)
        if info.st_uid != uid or info.st_mode & 0o077:
            raise RuntimeError("Directorio de sesión inseguro.")
        try:
            fd = os.open("aio-debian-gui-host-version",
                         os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
        except FileNotFoundError:
            return None
    finally:
        os.close(directory)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise RuntimeError("Solicitud de actualización insegura.")
        data = stream.read(42)
    if not re.fullmatch(rb"[0-9]+\.[0-9]+\.[0-9]+\n", data) or len(data) > 41:
        raise ValueError("Versión solicitada no válida.")
    return data[:-1].decode("ascii")
