"""Actualización desatendida y autenticada del paquete del anfitrión."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

from . import host_repository, host_requests

PACKAGE = host_repository.PACKAGE
RUN_DIR = Path("/run/aio-debian-gui")
ROOT_UID = 0
UPDATE_LOCK = "host-update.lock"
MAINTENANCE_LOCK = "maintenance.lock"
KEYRING = Path("/usr/share/keyrings/aio-debian-gui-host.gpg")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive"}


class Busy(Exception):
    """Otro proceso usa el programador, el mantenimiento o dpkg."""


def parse_version(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("Versión no válida.")
    return tuple(int(part) for part in value.split("."))


def _run(args, timeout=900):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=ENV)


def _open_lock(name):
    RUN_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
    directory = os.open(RUN_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory)
        if info.st_uid != ROOT_UID or info.st_mode & 0o022:
            raise RuntimeError("Directorio de bloqueos inseguro.")
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    finally:
        os.close(directory)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != ROOT_UID or info.st_mode & 0o077 or info.st_nlink != 1:
        os.close(fd)
        raise RuntimeError("Bloqueo inseguro: " + name)
    return fd


@contextmanager
def exclusive_locks():
    """Exige el uso exclusivo del programador y del mantenimiento, sin esperar."""
    fds = []
    try:
        for name in (UPDATE_LOCK, MAINTENANCE_LOCK):
            fd = _open_lock(name)
            fds.append(fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Busy(name) from exc
        yield
    finally:
        for fd in fds:
            os.close(fd)


def installed_state():
    """Devuelve (versión instalada o None, en retención)."""
    query = _run(["/usr/bin/dpkg-query", "-W", "-f=${db:Status-Status}\t${Version}\t${db:Status-Want}\n", PACKAGE], 30)
    if query.returncode:
        return None, False
    status, version, want = (query.stdout.strip().split("\t") + ["", "", ""])[:3]
    if status != "installed":
        raise RuntimeError("El paquete del anfitrión no está en un estado estable: " + status)
    parse_version(version)
    return version, want == "hold"


def requested_version():
    versions = []
    for uid in host_requests.authorized_users():
        try:
            version = host_requests.read_request(uid)
        except (OSError, RuntimeError, ValueError):
            continue
        if version:
            versions.append(version)
    return max(versions, key=parse_version) if versions else None


def update(download=None, keyring=KEYRING):
    """Instala la versión solicitada si es posterior. Devuelve un texto de estado."""
    requested = requested_version()
    if requested is None:
        return "sin solicitud"
    with exclusive_locks():
        current, hold = installed_state()
        if current is None:
            return "paquete no instalado"
        if hold:
            return "paquete retenido"
        if parse_version(requested) <= parse_version(current):
            return "actualizado"
        metadata, data = (download or host_repository.download_package)(keyring)
        if metadata["version"] != requested:
            return "repositorio sin la versión solicitada"
        directory = Path(tempfile.mkdtemp(prefix="update-", dir=RUN_DIR))
        try:
            directory.chmod(0o700)
            deb = directory / (PACKAGE + "_" + requested + "_all.deb")
            fd = os.open(deb, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            fields = _run(["/usr/bin/dpkg-deb", "-f", str(deb), "Package", "Version"], 60)
            if fields.returncode or fields.stdout.split() != ["Package:", PACKAGE, "Version:", requested]:
                raise RuntimeError("El paquete descargado no coincide con el solicitado.")
            result = _run(["/usr/bin/dpkg", "--force-confold", "-i", str(deb)])
            if result.returncode:
                _run(["/usr/bin/dpkg", "--configure", PACKAGE])
                raise RuntimeError("No se pudo instalar la actualización: " +
                                   (result.stderr or result.stdout).strip()[-1000:])
            after, _ = installed_state()
            if after != requested:
                raise RuntimeError("La actualización no quedó instalada.")
        finally:
            shutil.rmtree(directory, ignore_errors=True)
    return "actualizado a " + requested
