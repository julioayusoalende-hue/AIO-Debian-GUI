"""Integración inicial en el anfitrión y guía manual."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shlex
import stat
import subprocess
import time

APP_ID = "io.github.julioayusoalende_hue.aio_debian_gui"

# Este programa es texto fijo: nunca se ejecuta como root un archivo del usuario.
_ROOT_PROGRAM = r'''
import base64, binascii, fcntl, hashlib, json, os, re, signal, stat, subprocess, sys, tempfile
from pathlib import Path

RESOURCES = (
    ("__init__.py", "/usr/lib/aio-debian-gui/aio_core/__init__.py", 0o644),
    ("scheduler.py", "/usr/lib/aio-debian-gui/aio_core/scheduler.py", 0o644),
    ("preflight.py", "/usr/lib/aio-debian-gui/aio_core/preflight.py", 0o644),
    ("es.aiodebian.gui.policy", "/usr/share/polkit-1/actions/es.aiodebian.gui.policy", 0o644),
    ("aio-debian-gui-maintenance@.service", "/usr/lib/systemd/system/aio-debian-gui-maintenance@.service", 0o644),
    ("aio-debian-gui-helper", "/usr/lib/aio-debian-gui/aio-debian-gui-helper", 0o755),
)
LIMIT = 2 * 1024 * 1024
PORTABLE = False
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC
created = []
directories = []
handles = []

def fail(message):
    raise RuntimeError(message)

def command(args):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, timeout=5, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
    return p

def check_dir(fd, name):
    s = os.fstat(fd)
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
        fail("Directorio inseguro: " + name)

def directory(path, make=False):
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    handles.append(fd)
    check_dir(fd, "/")
    current = ""
    for component in path.strip("/").split("/"):
        if not component:
            continue
        current += "/" + component
        try:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=fd)
        except FileNotFoundError:
            if not make:
                return None
            os.mkdir(component, 0o755, dir_fd=fd)
            directories.append((fd, component))
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=fd)
        handles.append(child)
        check_dir(child, current)
        fd = child
    return fd

def absent(parent, name):
    if parent is None:
        return
    try:
        os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    fail("Ya existe un destino de integración: " + name)

def read_existing(parent, name, limit=32768):
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or info.st_nlink != 1):
            fail("Archivo de programación inseguro: " + name)
        data = stream.read(limit + 1)
        if len(data) > limit:
            fail("Archivo de programación demasiado grande: " + name)
        return data

def retained_schedules(decoded, portable_state):
    """Read only known, root-owned data left by an earlier AiO installation."""
    if not PORTABLE:
        return None
    config_root = directory("/etc/aio-debian-gui")
    state = directory("/var/lib/aio-debian-gui")
    if config_root is None and state is None:
        return None
    if config_root is not None:
        entries = set(os.listdir(config_root))
        if entries - {"schedules", "host-users"}:
            fail("La integración anterior contiene archivos que no se pueden atribuir al programador.")
        if "host-users" in entries:
            users = read_existing(config_root, "host-users").decode().splitlines()
            if any(not re.fullmatch(r"[1-9][0-9]{0,9}", user) for user in users):
                fail("La lista antigua de usuarios de AiO no es válida.")
    if state is not None:
        allowed = {"schedules", "portable-version"} if portable_state else {"schedules"}
        if set(os.listdir(state)) - allowed:
            fail("El estado anterior contiene archivos que no se pueden atribuir al programador.")
    configs = directory("/etc/aio-debian-gui/schedules")
    history = directory("/var/lib/aio-debian-gui/schedules")
    for parent in (configs, history):
        if parent is None:
            continue
        for name in os.listdir(parent):
            if not re.fullmatch(r"[1-9][0-9]{0,9}\.json", name):
                fail("Archivo de programación anterior no reconocido: " + name)
            if not isinstance(json.loads(read_existing(parent, name)), dict):
                fail("Archivo de programación anterior no válido: " + name)
    if configs is None:
        return {}
    scheduler = {"__name__": "_aio_recovery_scheduler"}
    exec(compile(decoded["scheduler.py"], "<scheduler>", "exec"), scheduler)
    units = directory("/etc/systemd/system")
    schedules = {}
    from pwd import getpwuid
    for name in sorted(os.listdir(configs)):
        uid = scheduler["validate_uid"](name.removesuffix(".json"))
        config = scheduler["validate_config"](json.loads(read_existing(configs, name)))
        timer = scheduler["timer_name"](uid)
        definition = scheduler["timer_text"](uid, config)
        try:
            getpwuid(int(uid))
            enabled = config["enabled"]
        except KeyError:
            enabled = False
        try:
            existing = read_existing(units, timer).decode() if units is not None else None
        except FileNotFoundError:
            existing = None
        already_active = False
        if existing is not None:
            if existing != definition:
                fail("El temporizador anterior tiene cambios locales: " + timer)
            p = command(["/usr/bin/systemctl", "show", timer,
                         "--property=ActiveState,UnitFileState,FragmentPath,DropInPaths"])
            fields = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
            active_state = fields.pop("ActiveState", "")
            file_state = fields.pop("UnitFileState", "")
            already_active = enabled and (active_state, file_state) == ("active", "enabled")
            if (p.returncode or fields != {"DropInPaths": "", "FragmentPath": "/etc/systemd/system/" + timer}
                    or not (already_active or (active_state, file_state) == ("inactive", "disabled"))):
                fail("El estado del temporizador anterior requiere revisión: " + timer)
        schedules[timer] = (existing is not None, definition, enabled, already_active)
    return schedules

def portable_repair(decoded):
    if not PORTABLE:
        return False
    parent = directory("/var/lib/aio-debian-gui")
    if parent is None:
        return False
    try:
        previous = read_existing(parent, "portable-version").decode().strip()
    except FileNotFoundError:
        return False
    release = decoded["portable-version"].decode().strip()
    if any(not re.fullmatch(r"[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}", value)
           for value in (previous, release)):
        fail("No se pudo verificar la versión de la integración portable.")
    if tuple(map(int, release.split("."))) < tuple(map(int, previous.split("."))):
        fail("Abre la versión más reciente de AiO para reparar la integración.")
    return True

def replace_resource(parent, name, content, mode):
    temporary = ".aio-integration-" + os.urandom(16).hex()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, mode, dir_fd=parent)
    try:
        with os.fdopen(fd, "wb") as target:
            os.fchmod(target.fileno(), mode)
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
    finally:
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass

def check_residual(schedules=None, repair=False):
    legacy_timers = {name: active for name, (exists, _, _, active) in (schedules or {}).items() if exists}
    retained_services = {
        "aio-debian-gui-maintenance@" + name.removeprefix("aio-debian-gui-maintenance-").removesuffix(".timer") + ".service"
        for name in (schedules or {})
    }
    directory("/etc")
    directory("/var/lib")
    for path in ("/etc/aio-debian-gui", "/var/lib/aio-debian-gui"):
        if schedules is None and os.path.lexists(path):
            fail("Existe configuración o estado anterior: " + path)
    # Incluye unidades no cargadas, enlaces rotos, overrides y dependencias.
    for base in ("/etc/systemd/system", "/run/systemd/system", "/usr/local/lib/systemd/system",
                 "/usr/lib/systemd/system"):
        basefd = directory(base)
        if basefd is None:
            continue
        with os.scandir(basefd) as entries:
            for entry in entries:
                if entry.name.startswith(("aio-debian-gui-maintenance@", "aio-debian-gui-maintenance-")):
                    if not ((base == "/etc/systemd/system" and entry.name in legacy_timers)
                            or (repair and base == "/usr/lib/systemd/system"
                                and entry.name == "aio-debian-gui-maintenance@.service")):
                        fail("Existe una unidad o configuración anterior: " + base + "/" + entry.name)
                if entry.name.endswith((".wants", ".requires")):
                    if entry.is_symlink():
                        fail("Directorio de dependencias inseguro: " + base + "/" + entry.name)
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    childfd = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=basefd)
                    handles.append(childfd)
                    check_dir(childfd, base + "/" + entry.name)
                    with os.scandir(childfd) as children:
                        for child in children:
                            if child.name.startswith(("aio-debian-gui-maintenance@", "aio-debian-gui-maintenance-")):
                                if (base == "/etc/systemd/system" and entry.name == "timers.target.wants"
                                        and legacy_timers.get(child.name) and child.is_symlink()
                                        and os.readlink(child.name, dir_fd=childfd)
                                        in ("/etc/systemd/system/" + child.name, "../" + child.name)):
                                    continue
                                fail("Existe una dependencia anterior: " + base + "/" + entry.name + "/" + child.name)
    for subcommand in ("list-units", "list-unit-files"):
        p = command(["/usr/bin/systemctl", subcommand, "--all", "--plain", "--no-legend",
                     "--no-pager"])
        if p.returncode:
            fail("No se pudieron comprobar las unidades systemd: " + (p.stderr or p.stdout).strip()[-600:])
        for line in p.stdout.splitlines():
            fields = line.split()
            if fields and fields[0].startswith(("aio-debian-gui-maintenance@", "aio-debian-gui-maintenance-")):
                if (repair and subcommand == "list-unit-files"
                        and fields[:2] == ["aio-debian-gui-maintenance@.service", "static"]):
                    continue
                # systemd can keep the service instance loaded after a completed or failed run.
                if (subcommand == "list-units" and fields[0] in retained_services
                        and fields[2:3] in (["inactive"], ["failed"])):
                    continue
                active = legacy_timers.get(fields[0])
                expected = (["enabled" if active else "disabled"] if subcommand == "list-unit-files"
                            else ["active" if active else "inactive"])
                actual = fields[1:2] if subcommand == "list-unit-files" else fields[2:3]
                if active is None or actual != expected:
                    fail("Unidad de AiO en un estado inesperado (" + subcommand + "): " + " ".join(fields[:4]))
    p = command(["/usr/bin/systemctl", "list-units", "--all", "--plain", "--no-legend",
                 "--no-pager", "--type=timer"])
    if p.returncode:
        fail("No se pudieron enumerar los temporizadores: " + (p.stderr or p.stdout).strip()[-600:])
    timers = []
    for line in p.stdout.splitlines():
        fields = line.split()
        if not fields or not fields[0].endswith(".timer"):
            fail("Respuesta de systemd no válida al enumerar temporizadores.")
        if fields[0] not in legacy_timers:
            timers.append(fields[0])
    if timers:
        p = command(["/usr/bin/systemctl", "show", "--all", "--property=Id",
                     "--property=Triggers", "--", *timers])
        if p.returncode:
            fail("No se pudieron comprobar los temporizadores: " + (p.stderr or p.stdout).strip()[-600:])
        if "aio-debian-gui-maintenance@" in p.stdout:
            fail("Un temporizador existente puede iniciar el servicio de AiO.")

def check_packages():
    p = command(["/usr/bin/dpkg-query", "-W", "-f=${binary:Package}\t${db:Status-Status}\n"])
    if p.returncode:
        fail("No se pudo consultar dpkg: " + (p.stderr or p.stdout).strip()[-600:])
    for line in p.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            fail("Respuesta de dpkg no válida.")
        if parts[0].split(":")[0] == "aio-debian-gui" and parts[1] == "installed":
            fail("El paquete DEB de AiO está instalado.")
    for _, path, _ in RESOURCES:
        p = command(["/usr/bin/dpkg-query", "-S", "--", path])
        expected = "dpkg-query: no path found matching pattern " + path
        if p.returncode == 0:
            fail("Destino gestionado por un paquete: " + path)
        if p.returncode != 1 or p.stdout.strip() or p.stderr.strip() != expected:
            fail("No se pudo verificar el propietario de " + path + ": " + (p.stderr or p.stdout).strip()[-600:])

def lock_file(path, posix=False, create=False):
    flags = os.O_RDWR | NOFOLLOW | (os.O_CREAT if create else 0)
    fd = os.open(path, flags, 0o600)
    handles.append(fd)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022 or st.st_nlink != 1:
        fail("Bloqueo inseguro: " + path)
    try:
        if posix:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fail("Mantenimiento o gestión de paquetes en curso: " + path)

def main():
    if os.geteuid() != 0:
        fail("Se necesita autorización de administrador.")
    def interrupted(signum, frame):
        raise RuntimeError("Instalación interrumpida.")
    signal.signal(signal.SIGTERM, interrupted)
    print("READY", flush=True)
    data = sys.stdin.buffer.read(LIMIT * 12 + 1)
    if len(data) > LIMIT * 12:
        fail("Datos de integración demasiado grandes.")
    obj = json.loads(data)
    if not isinstance(obj, dict) or set(obj) != {item[0] for item in RESOURCES}:
        fail("Recursos de integración no válidos.")
    decoded = {}
    for name, _, _ in RESOURCES:
        item = obj[name]
        if not isinstance(item, dict) or set(item) != {"sha256", "data"}:
            fail("Metadatos no válidos: " + name)
        if not isinstance(item["sha256"], str) or not re.fullmatch("[0-9a-f]{64}", item["sha256"]):
            fail("Huella no válida: " + name)
        content = base64.b64decode(item["data"], validate=True)
        if not 0 < len(content) <= LIMIT or hashlib.sha256(content).hexdigest() != item["sha256"]:
            fail("La huella del recurso no coincide: " + name)
        decoded[name] = content

    directory("/var/lib/dpkg")
    directory("/usr/bin")
    lock_file("/var/lib/dpkg/lock-frontend", True)
    lock_file("/var/lib/dpkg/lock", True)
    check_packages()
    repair = portable_repair(decoded)
    schedules = retained_schedules(decoded, repair)
    check_residual(schedules, repair)
    previous = {}
    for _, path, _ in RESOURCES:
        parent, name = directory(os.path.dirname(path)), os.path.basename(path)
        if repair and parent is not None:
            try:
                content = read_existing(parent, name, LIMIT)
            except FileNotFoundError:
                continue
            mode = stat.S_IMODE(os.stat(name, dir_fd=parent, follow_symlinks=False).st_mode)
            previous[path] = (content, mode)
        else:
            absent(parent, name)
    directory("/run/aio-debian-gui", True)
    lock_file("/run/aio-debian-gui/maintenance.lock", create=True)
    check_residual(schedules, repair)
    directories.clear()

    activated = []
    replaced = []
    try:
        with tempfile.TemporaryDirectory(prefix=".aio-integration-", dir="/run/aio-debian-gui") as stage:
            for name, _, _ in RESOURCES:
                path = os.path.join(stage, name)
                with open(path, "xb") as stream:
                    stream.write(decoded[name])
                    stream.flush()
                    os.fsync(stream.fileno())
                with open(path, "rb") as stream:
                    if hashlib.sha256(stream.read()).hexdigest() != obj[name]["sha256"]:
                        fail("La verificación del staging falló: " + name)

            helper, helper_path, helper_mode = RESOURCES[-1]
            helper_parent = directory(os.path.dirname(helper_path), True)
            helper_fd = os.open(".", os.O_RDWR | os.O_TMPFILE | os.O_CLOEXEC, helper_mode, dir_fd=helper_parent)
            handles.append(helper_fd)
            with open(os.path.join(stage, helper), "rb") as source:
                helper_data = source.read()
            with os.fdopen(os.dup(helper_fd), "wb") as target:
                target.write(helper_data)
                target.flush()
                os.fchmod(target.fileno(), helper_mode)
                os.fsync(target.fileno())
            os.lseek(helper_fd, 0, os.SEEK_SET)
            if hashlib.sha256(os.read(helper_fd, LIMIT + 1)).hexdigest() != obj[helper]["sha256"]:
                fail("La verificación del helper falló.")

            for name, path, mode in RESOURCES[:-1]:
                parent = directory(os.path.dirname(path), True)
                name = os.path.basename(path)
                if path in previous:
                    replaced.append((parent, name, previous[path]))
                    replace_resource(parent, name, decoded[name], mode)
                    continue
                fd = os.open(os.path.basename(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW,
                             mode, dir_fd=parent)
                created.append((parent, os.path.basename(path)))
                with os.fdopen(fd, "wb") as target, open(os.path.join(stage, name), "rb") as source:
                    target.write(source.read())
                    target.flush()
                    os.fchmod(target.fileno(), mode)
                    os.fsync(target.fileno())
                fd = os.open(os.path.basename(path), os.O_RDONLY | NOFOLLOW, dir_fd=parent)
                with os.fdopen(fd, "rb") as target:
                    if hashlib.sha256(target.read()).hexdigest() != obj[name]["sha256"]:
                        fail("La verificación del destino falló: " + name)
        for timer, (exists, definition, _, _) in (schedules or {}).items():
            if not exists:
                parent = directory("/etc/systemd/system")
                fd = os.open(timer, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o644, dir_fd=parent)
                created.append((parent, timer))
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    os.fchmod(stream.fileno(), 0o644)
                    stream.write(definition)
                    stream.flush()
                    os.fsync(stream.fileno())
        # La integración no está disponible hasta publicar el helper completo.
        p = command(["/usr/bin/systemctl", "daemon-reload"])
        if p.returncode:
            fail("No se pudo recargar systemd: " + (p.stderr or p.stdout).strip()[-600:])
        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
        try:
            helper_name = os.path.basename(helper_path)
            if helper_path in previous:
                replaced.append((helper_parent, helper_name, previous[helper_path]))
                replace_resource(helper_parent, helper_name, helper_data, helper_mode)
            else:
                os.link("/proc/self/fd/" + str(helper_fd), helper_name,
                        dst_dir_fd=helper_parent, follow_symlinks=True)
                created.append((helper_parent, helper_name))
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        update_timer = "/usr/lib/systemd/system/aio-portable-update.timer"
        timers_to_start = ["aio-portable-update.timer"] if PORTABLE and update_timer not in previous else []
        timers_to_start.extend(name for name, (_, _, enabled, active) in (schedules or {}).items()
                               if enabled and not active)
        for unit in timers_to_start:
            activated.append(unit)
            p = command(["/usr/bin/systemctl", "enable", "--now", unit])
            if p.returncode:
                fail("No se pudo activar " + unit + ": " + (p.stderr or p.stdout).strip()[-600:])
    except BaseException as original:
        errors = []
        for unit in reversed(activated):
            try:
                p = command(["/usr/bin/systemctl", "disable", "--now", unit])
                if p.returncode:
                    errors.append("No se pudo desactivar " + unit)
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
        for parent, name, (content, mode) in reversed(replaced):
            try:
                replace_resource(parent, name, content, mode)
            except OSError as exc:
                errors.append(str(exc))
        for parent, name in reversed(created):
            try:
                os.unlink(name, dir_fd=parent)
            except OSError as exc:
                errors.append(str(exc))
        for parent, name in reversed(directories):
            try:
                os.rmdir(name, dir_fd=parent)
            except OSError as exc:
                errors.append(str(exc))
        if created or replaced:
            try:
                p = command(["/usr/bin/systemctl", "daemon-reload"])
                if p.returncode:
                    errors.append("No se pudo recargar systemd tras revertir.")
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(str(original) + "; reversión incompleta: " + "; ".join(errors)) from original
        raise

try:
    main()
except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError, binascii.Error) as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(1)
finally:
    for fd in reversed(handles):
        try:
            os.close(fd)
        except OSError:
            pass
'''

_LIMIT = 2 * 1024 * 1024
_NAMES = ("__init__.py", "scheduler.py", "preflight.py", "es.aiodebian.gui.policy",
          "aio-debian-gui-maintenance@.service", "aio-debian-gui-helper")

# Instala el paquete aio-debian-gui-host autenticado por el repositorio firmado y aislado.
_PACKAGE_PROGRAM = r'''
import base64, fcntl, json, os, re, shutil, stat, subprocess, sys, tempfile, types
from pathlib import Path

LEGACY = frozenset((
    "/usr/lib/aio-debian-gui/aio-debian-gui-helper",
    "/usr/lib/aio-debian-gui/aio_core/__init__.py",
    "/usr/lib/aio-debian-gui/aio_core/scheduler.py",
    "/usr/lib/aio-debian-gui/aio_core/preflight.py",
    "/usr/share/polkit-1/actions/es.aiodebian.gui.policy",
    "/usr/lib/systemd/system/aio-debian-gui-maintenance@.service",
))
RUN = "/run/aio-debian-gui"
CONFIG = "/etc/aio-debian-gui"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive"}
UNAVAILABLE = 75

def fail(message, code=1):
    print(message, file=sys.stderr)
    sys.exit(code)

def run(args, timeout=900):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=ENV)

def lock(name):
    os.makedirs(RUN, mode=0o755, exist_ok=True)
    directory = os.open(RUN, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory)
        if info.st_uid != 0 or info.st_mode & 0o022:
            fail("Directorio de bloqueos inseguro.")
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    finally:
        os.close(directory)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077 or info.st_nlink != 1:
        fail("Bloqueo inseguro: " + name)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fail("Hay un mantenimiento o una actualización en curso; inténtalo después.")
    return fd

def status(package):
    result = run(["/usr/bin/dpkg-query", "-W", "-f=${db:Status-Status}", package], 30)
    return result.stdout.strip() if result.returncode == 0 else "not-installed"

def owned(path):
    result = run(["/usr/bin/dpkg-query", "-S", path], 30)
    if result.returncode == 0:
        return True
    if result.stderr.strip() == "dpkg-query: no path found matching pattern " + path:
        return False
    fail("No se pudo verificar el propietario de " + path + ": " + result.stderr.strip())

def main():
    if os.geteuid() != 0:
        fail("Se necesita autorización de administrador.")
    uid = os.environ.get("PKEXEC_UID", "")
    if not re.fullmatch(r"[1-9][0-9]{0,9}", uid):
        fail("No se pudo determinar el usuario autorizado.")
    print("READY", flush=True)
    payload = json.loads(sys.stdin.buffer.read(1024 * 1024 + 1))
    module = types.ModuleType("host_repository")
    exec(compile(payload["repository"], "host_repository", "exec"), module.__dict__)
    handles = [lock("host-update.lock"), lock("maintenance.lock")]
    if status("aio-debian-gui") not in ("not-installed", "config-files"):
        fail("El paquete DEB está instalado. Usa su programador integrado y APT; no se instaló la integración portable.")
    if status("aio-debian-gui-host") == "installed":
        print("La integración del anfitrión ya está instalada.")
        users = None
    else:
        if status("aio-debian-gui-host") not in ("not-installed", "config-files"):
            fail("El paquete del anfitrión está en un estado inestable; repáralo con dpkg.")
        policy = run(["/usr/bin/apt-cache", "policy", "aio-debian-gui-host"], 60)
        candidates = re.findall(r"^\s*Candidate: (.*)$", policy.stdout, re.M)
        if policy.returncode or any(value.strip() != "(none)" for value in candidates):
            fail("Otra fuente APT anuncia aio-debian-gui-host; no se instalará.")
        keyring = base64.b64decode(payload["keyring"], validate=True)
        if not keyring or len(keyring) > 65536:
            fail("Clave de verificación no válida.")
        directory = Path(tempfile.mkdtemp(prefix="bootstrap-", dir=RUN))
        try:
            directory.chmod(0o700)
            key = directory / "keyring.gpg"
            key.write_bytes(keyring)
            try:
                metadata, data = module.download_package(str(key))
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                fail("Repositorio del anfitrión no disponible: " + str(exc), UNAVAILABLE)
            deb = directory / "host.deb"
            deb.write_bytes(data)
            deb.chmod(0o600)
            fields = run(["/usr/bin/dpkg-deb", "-f", str(deb), "Package", "Version", "Conflicts"], 60)
            if fields.returncode or fields.stdout.split()[:4] != ["Package:", "aio-debian-gui-host", "Version:", metadata["version"]]:
                fail("El paquete descargado no coincide con los metadatos firmados.")
            listing = run(["/usr/bin/dpkg-deb", "-c", str(deb)], 60)
            if listing.returncode:
                fail("No se pudo leer el contenido del paquete.")
            for line in listing.stdout.splitlines():
                if not line.startswith("-"):
                    continue
                path = line.split(" ./", 1)[-1].split(" -> ")[0]
                path = "/" + path.removeprefix("./").lstrip("/")
                if os.path.lexists(path) and path not in LEGACY and not owned(path):
                    fail("El archivo ya existe y no es de la integración anterior: " + path)
                if os.path.lexists(path) and path in LEGACY and owned(path):
                    fail("Archivo gestionado por otro paquete: " + path)
            result = run(["/usr/bin/dpkg", "--force-confold", "-i", str(deb)])
            if result.returncode:
                run(["/usr/bin/dpkg", "--configure", "aio-debian-gui-host"])
                fail("No se pudo instalar el paquete del anfitrión: " + (result.stderr or result.stdout).strip()[-1000:])
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        if status("aio-debian-gui-host") != "installed":
            fail("La integración del anfitrión no quedó instalada.")
    os.makedirs(CONFIG, mode=0o755, exist_ok=True)
    path = Path(CONFIG) / "host-users"
    current = []
    if path.exists():
        current = [line for line in path.read_text("ascii").splitlines() if re.fullmatch(r"[1-9][0-9]{0,9}", line)]
    if uid not in current:
        temporary = path.with_name(".host-users.tmp")
        temporary.write_text("\n".join([*current, uid]) + "\n", "ascii")
        temporary.chmod(0o644)
        os.replace(temporary, path)
    # El prerm del DEB desactiva los temporizadores; se restauran los horarios activos.
    schedules = Path(CONFIG) / "schedules"
    if os.path.isdir("/run/systemd/system") and schedules.is_dir():
        for config in sorted(schedules.glob("[0-9]*.json")):
            try:
                enabled = json.loads(config.read_text("utf-8")).get("enabled") is True
            except (OSError, ValueError):
                continue
            timer = "aio-debian-gui-maintenance-" + config.stem + ".timer"
            if enabled and re.fullmatch(r"[0-9]+", config.stem) and (Path("/etc/systemd/system") / timer).is_file():
                run(["/usr/bin/systemctl", "enable", "--now", timer], 60)
    for handle in handles:
        os.close(handle)
    print("Integración del anfitrión instalada.")

main()
'''

_REQUEST_PROGRAM = r'''
import os, re, secrets, stat, sys
version = sys.argv[1]
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or len(version) > 40:
    raise ValueError("Versión de AiO no válida.")
uid = os.getuid()
fd = os.open("/run/user/" + str(uid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    info = os.fstat(fd)
    if info.st_uid != uid or info.st_mode & 0o077:
        raise RuntimeError("Directorio de sesión inseguro.")
    temporary = ".aio-host-version-" + secrets.token_hex(16)
    out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                  0o600, dir_fd=fd)
    try:
        with os.fdopen(out, "w", encoding="ascii") as stream:
            stream.write(version + "\n")
        os.replace(temporary, "aio-debian-gui-host-version", src_dir_fd=fd, dst_dir_fd=fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass
finally:
    os.close(fd)
'''


def _request_legacy_host_update(formato, version):
    """Solicita una versión al servicio del anfitrión, sin elevar privilegios."""
    if formato not in ("appimage", "flatpak"):
        raise ValueError("Formato de integración no compatible.")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or len(version) > 40:
        raise ValueError("Versión de AiO no válida.")
    prefix = ["flatpak-spawn", "--host"] if formato == "flatpak" else []
    # HostCommand uses the host session environment unless explicitly overridden.
    query_prefix = [*prefix, "--env=LC_ALL=C"] if prefix else []
    query = subprocess.run(
        [*query_prefix, "/usr/bin/dpkg-query", "-W", "-f=${db:Status-Status}", "aio-debian-gui-host"],
        capture_output=True, text=True, timeout=15, env={**os.environ, "LC_ALL": "C"},
    )
    if query.returncode:
        if query.returncode == 1 and "no packages found matching" in query.stderr:
            return False
        raise RuntimeError("No se pudo consultar la integración del anfitrión: " +
                           (query.stderr or query.stdout).strip())
    status = query.stdout.strip()
    if status in ("not-installed", "config-files"):
        return False
    if status != "installed":
        raise RuntimeError("La integración del anfitrión no está configurada: " + status)
    result = subprocess.run(
        [*prefix, "/usr/bin/python3", "-I", "-c", _REQUEST_PROGRAM, version],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode:
        raise RuntimeError("No se pudo solicitar la actualización del programador: " +
                           (result.stderr or result.stdout).strip())
    return True


def _read_resource(prefix, path):
    parts = path.relative_to(prefix).parts
    fd = os.open(prefix, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in parts[:-1]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        resource = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(resource, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise RuntimeError("El recurso no es un archivo regular: " + parts[-1])
            return stream.read(_LIMIT + 1)
    finally:
        os.close(fd)


def _resources(formato, appimage):
    module = Path(__file__).resolve()
    if formato == "flatpak":
        prefix = Path("/app")
        if module != prefix / "lib/aio-debian-gui/aio_core/host_integration.py" or not Path("/.flatpak-info").is_file():
            raise RuntimeError("No se está ejecutando la versión Flatpak instalada.")
        shared = prefix / "share/aio-debian-gui/host-integration"
        paths = {name: shared / name for name in _NAMES[3:]}
        core = prefix / "lib/aio-debian-gui/aio_core"
    elif formato == "appimage":
        if (not isinstance(appimage, str) or not os.path.isabs(appimage)
                or any(c in appimage for c in ("\0", "\n", "\r"))):
            raise RuntimeError("No se pudo determinar la ruta absoluta del AppImage.")
        appdir, running = os.environ.get("APPDIR"), os.environ.get("APPIMAGE")
        if not appdir or not running or not os.path.samefile(appimage, running):
            raise RuntimeError("El AppImage indicado no es el que está en ejecución.")
        prefix = Path(appdir).resolve()
        core = prefix / "usr/lib/aio-debian-gui/aio_core"
        if module != core / "host_integration.py":
            raise RuntimeError("Los recursos no pertenecen al AppImage en ejecución.")
        paths = {
            "aio-debian-gui-helper": prefix / "usr/lib/aio-debian-gui/aio-debian-gui-helper",
            "es.aiodebian.gui.policy": prefix / "usr/share/polkit-1/actions/es.aiodebian.gui.policy",
            "aio-debian-gui-maintenance@.service": prefix / "usr/lib/systemd/system/aio-debian-gui-maintenance@.service",
        }
    else:
        raise RuntimeError("Formato de integración no compatible.")
    paths.update({name: core / name for name in _NAMES[:3]})
    result = {}
    for name in _NAMES:
        content = _read_resource(prefix, paths[name])
        if not content or len(content) > _LIMIT:
            raise RuntimeError("Recurso vacío o demasiado grande: " + name)
        result[name] = {"sha256": hashlib.sha256(content).hexdigest(),
                        "data": base64.b64encode(content).decode("ascii")}
    return result


def _stop_process(proc):
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream:
                stream.close()


class RepositoryUnavailable(RuntimeError):
    """El repositorio firmado del anfitrión no respondió; no se modificó el sistema."""


def install(formato, appimage=None):
    """Instala solo una integración inicial; lanza RuntimeError si falla."""
    try:
        payload = json.dumps(_resources(formato, appimage)).encode("ascii")
    except (OSError, ValueError) as exc:
        raise RuntimeError("No se pudo preparar la integración: " + str(exc)) from exc
    _privileged(formato, _ROOT_PROGRAM, payload)


def _package_payload():
    here = Path(__file__).resolve().parent
    keyrings = [here.parents[2] / "share/keyrings/aio-debian-gui.gpg", Path("/app/share/keyrings/aio-debian-gui.gpg")]
    keyring = next((path for path in keyrings if path.is_file()), None)
    if keyring is None:
        raise RuntimeError("No se encontró la clave de verificación del repositorio.")
    return json.dumps({
        "repository": (here / "host_repository.py").read_text("utf-8"),
        "keyring": base64.b64encode(keyring.read_bytes()).decode("ascii"),
    }).encode("ascii")


def _install_legacy_host(formato, appimage=None):
    """Instala el paquete del anfitrión con actualizaciones; si el repositorio no responde, usa la copia inicial."""
    if formato not in ("appimage", "flatpak"):
        raise ValueError("Formato de integración no compatible.")
    try:
        payload = _package_payload()
    except (OSError, ValueError) as exc:
        raise RuntimeError("No se pudo preparar la integración: " + str(exc)) from exc
    try:
        _privileged(formato, _PACKAGE_PROGRAM, payload)
    except RepositoryUnavailable:
        install(formato, appimage)



def _portable_directory(formato):
    return (Path('/app/share/aio-debian-gui/portable') if formato == 'flatpak' else
            Path(os.environ['APPDIR']) / 'usr/share/aio-debian-gui/portable')


_PORTABLE_EXTRAS = (
    ('aio-portable-update', '/usr/lib/aio-debian-gui/aio-portable-update', 0o644),
    ('aio-host-scheduler', '/usr/lib/aio-debian-gui/aio-host-scheduler', 0o755),
    ('aio-portable-update.service', '/usr/lib/systemd/system/aio-portable-update.service', 0o644),
    ('aio-portable-update.timer', '/usr/lib/systemd/system/aio-portable-update.timer', 0o644),
    ('aio-debian-gui-portable.gpg', '/usr/share/keyrings/aio-debian-gui-portable.gpg', 0o644),
    ('portable-version', '/var/lib/aio-debian-gui/portable-version', 0o644),
)


def compatible_helper(formato, helper):
    from .scheduler import HOST_PROTOCOL, compatible_version
    prefix = ["flatpak-spawn", "--host"] if formato == "flatpak" else []
    try:
        probe = subprocess.run([*prefix, helper, "--maintenance-api"],
                               capture_output=True, text=True, timeout=10)
        if probe.returncode == 0:
            return probe.stdout.strip() == str(HOST_PROTOCOL)
        legacy = subprocess.run([*prefix, helper, "--version"],
                                capture_output=True, text=True, timeout=10)
        return legacy.returncode == 0 and compatible_version(legacy.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def prepare_host(formato, version):
    """Queue signed updates even if an older packaged scheduler is incompatible."""
    request_host_update(formato, version)


def read_scheduler_report(command):
    from .scheduler import validate_config
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-500:]
        raise RuntimeError(detail or f"El programador terminó con código {result.returncode}.")
    report = json.loads(result.stdout)
    if not isinstance(report, dict):
        raise ValueError("La respuesta del programador no es válida.")
    if report.get("config") is not None:
        report["config"] = validate_config(report["config"])
    return report


_USER_SCHEDULER_PROGRAM = r'''import base64, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

request = json.load(sys.stdin)
files = request["files"]
directory = Path.home() / ".local/share/aio-debian-gui/scheduler/aio_core"
directory.mkdir(mode=0o700, parents=True, exist_ok=True)
for name in ("__init__.py", "preflight.py", "scheduler.py"):
    data = base64.b64decode(files[name]["data"], validate=True)
    if hashlib.sha256(data).hexdigest() != files[name]["sha256"]:
        raise ValueError("El archivo del programador no coincide con su huella.")
    fd, temporary = tempfile.mkstemp(prefix=".aio-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, directory / name)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
script = directory / "scheduler.py"
command = [sys.executable, "-I", str(script), request["action"], request["uid"]]
if "config" in request:
    command.append(json.dumps(request["config"], separators=(",", ":")))
result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
'''


def run_user_scheduler(formato, action, uid, config=None):
    """Run the user-owned scheduler on the host for DEB, AppImage and Flatpak."""
    if formato not in ("deb", "appimage", "flatpak", "snap", "dev"):
        raise ValueError("Formato de programación no compatible.")
    if action not in ("--status", "--configure", "--remove"):
        raise ValueError("Acción del programador no válida.")
    from .scheduler import validate_config, validate_uid
    uid = validate_uid(uid)
    request = {"action": action, "uid": uid}
    if action == "--configure":
        request["config"] = validate_config(config)
    elif config is not None:
        raise ValueError("Configuración inesperada para esta acción.")
    core = Path(__file__).resolve().parent
    request["files"] = {}
    for name in ("__init__.py", "preflight.py", "scheduler.py"):
        data = (core / name).read_bytes()
        request["files"][name] = {
            "data": base64.b64encode(data).decode("ascii"),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    prefix = ["flatpak-spawn", "--host"] if formato == "flatpak" else []
    result = subprocess.run(
        [*prefix, "/usr/bin/python3", "-I", "-c", _USER_SCHEDULER_PROGRAM],
        input=json.dumps(request), capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-1200:]
        raise RuntimeError(detail or f"El programador terminó con código {result.returncode}.")
    if action == "--status":
        return read_scheduler_report_from_text(result.stdout)
    return None


def read_scheduler_report_from_text(text):
    from .scheduler import validate_config
    report = json.loads(text)
    if not isinstance(report, dict):
        raise ValueError("La respuesta del programador no es válida.")
    if report.get("config") is not None:
        report["config"] = validate_config(report["config"])
    return report


def scheduler_problem(report):
    from .scheduler import compatible_host
    if report.get("available") is not True:
        return report.get("availability_error") or "El asistente del anfitrión informa de que la programación no está disponible."
    if not compatible_host(report):
        version = report.get("version") or "desconocida"
        return "El protocolo del programador del anfitrión no es compatible. Versión: " + str(version)
    return None


def host_scheduler_report(formato):
    prefix = ["flatpak-spawn", "--host"] if formato == "flatpak" else []
    return read_scheduler_report([*prefix, "/usr/lib/aio-debian-gui/aio-debian-gui-helper", "--schedule-status"])


def existing_scheduler(formato):
    """Reuse a compatible host installation without replacing package-owned files."""
    if formato not in ("appimage", "flatpak"):
        raise ValueError("Formato de integración no compatible.")
    try:
        return scheduler_problem(host_scheduler_report(formato)) is None
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError):
        return False


def install_host(formato, appimage=None):
    """Install the bundled scheduler without installing a DEB or using a repository."""
    if existing_scheduler(formato):
        return  # Already usable: never try to reinstall over dpkg's files.
    owners = host_package_owners(formato)
    if owners == {"aio-debian-gui-host"}:
        from .scheduler import VERSION
        if _request_legacy_host_update(formato, VERSION):
            raise RuntimeError("Se solicitó la actualización firmada del programador de Debian. "
                               "Puede tardar hasta unos minutos. Después, pulsa «Actualizar estado».")
    if owners:
        raise RuntimeError("El asistente lo gestiona un paquete de Debian (" + ", ".join(sorted(owners))
                           + "). Actualiza o repara ese paquete desde el gestor de software de Debian.")
    resources = _resources(formato, appimage)
    shared = _portable_directory(formato)
    # Verify the release payload before registering an automatic root updater.
    verifier = (shared / 'aio-portable-update').read_text().split("if __name__ == '__main__':", 1)[0]
    verifier += r"""
import sys
request = json.loads(sys.stdin.buffer.read(9 * 1024 * 1024))
with tempfile.TemporaryDirectory() as tmp:
    key = Path(tmp) / 'keyring.gpg'
    key.write_bytes(base64.b64decode(request['key'], validate=True))
    release, resources = verify(base64.b64decode(request['payload'], validate=True), key)
print(json.dumps({'version': release, 'files': {name: base64.b64encode(data).decode() for name, data in resources.items()}}))
"""
    prefix = ['flatpak-spawn', '--host'] if formato == 'flatpak' else []
    request = json.dumps({'key': base64.b64encode((shared / 'aio-debian-gui-portable.gpg').read_bytes()).decode(),
                          'payload': base64.b64encode((shared / 'payload.json').read_bytes()).decode()})
    result = subprocess.run([*prefix, '/usr/bin/python3', '-I', '-c', verifier],
                            input=request, capture_output=True, text=True, check=True, timeout=45)
    manifest = json.loads(result.stdout)
    release = manifest['version']
    decoded = {name: base64.b64decode(data, validate=True) for name, data in manifest['files'].items()}
    for name, content in decoded.items():
        resources[name] = {'data': base64.b64encode(content).decode(), 'sha256': hashlib.sha256(content).hexdigest()}
    for name, _, _ in _PORTABLE_EXTRAS:
        content = (release + '\n').encode() if name == 'portable-version' else (shared / name).read_bytes()
        resources[name] = {'data': base64.b64encode(content).decode(), 'sha256': hashlib.sha256(content).hexdigest()}
    # Keep the helper last: the installer publishes it only after all resources exist.
    program = _ROOT_PROGRAM.replace('LIMIT = 2 * 1024 * 1024',
        'RESOURCES = RESOURCES[:-1] + ' + repr(_PORTABLE_EXTRAS) + ' + RESOURCES[-1:]\nLIMIT = 2 * 1024 * 1024', 1)
    program = program.replace("PORTABLE = False", "PORTABLE = True", 1)
    try:
        _privileged(formato, program, json.dumps(resources).encode())
    except RuntimeError:
        if not existing_scheduler(formato):
            raise
    try:
        problem = scheduler_problem(host_scheduler_report(formato))
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        problem = str(exc)
    if problem:
        raise RuntimeError("Se instalaron los archivos, pero el programador aún no responde correctamente. " + problem)


_STAGE_PROGRAM = r'''import base64, fcntl, json, os, re, sys, tempfile
from pathlib import Path

MAXIMUM = 8 * 1024 * 1024
runtime = Path('/run/user') / str(os.getuid())
destination = runtime / 'aio-portable-update'

def version(data):
    if len(data) > MAXIMUM:
        raise ValueError('Paquete de integración demasiado grande.')
    manifest = json.loads(base64.b64decode(json.loads(data)['data'], validate=True))
    value = manifest['version']
    if not re.fullmatch(r'[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}', value):
        raise ValueError('Versión de integración no válida.')
    return tuple(map(int, value.split('.')))

data = sys.stdin.buffer.read(MAXIMUM + 1)
candidate = version(data)
fd = os.open(runtime / 'aio-portable-submit.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'wb') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        fd = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as staged:
            if version(staged.read(MAXIMUM + 1)) > candidate:
                sys.exit(0)
    except (OSError, KeyError, TypeError, ValueError):
        pass
    fd, name = tempfile.mkstemp(prefix='.aio-portable-', dir=runtime)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(name, destination)
    finally:
        if os.path.exists(name):
            os.unlink(name)
'''


def host_package_owners(formato):
    prefix = ["flatpak-spawn", "--host", "--env=LC_ALL=C"] if formato == "flatpak" else []
    paths = ("/usr/lib/aio-debian-gui/aio-debian-gui-helper",
             "/usr/lib/aio-debian-gui/aio_core/__init__.py")
    result = subprocess.run([*prefix, "/usr/bin/dpkg-query", "-S", "--", *paths],
                            capture_output=True, text=True, timeout=10,
                            env={**os.environ, "LC_ALL": "C"})
    missing = {"dpkg-query: no path found matching pattern " + path for path in paths}
    if result.returncode not in (0, 1) or set(result.stderr.splitlines()) - missing:
        raise RuntimeError("No se pudo determinar quién actualiza la integración del anfitrión.")
    owners = set()
    found = set()
    for line in result.stdout.splitlines():
        packages, separator, path = line.partition(": ")
        if not separator or path not in paths:
            raise RuntimeError("No se pudo identificar el paquete de la integración.")
        found.add(path)
        owners.update(name.strip().split(":")[0] for name in packages.split(","))
    if found | {path for path in paths if "dpkg-query: no path found matching pattern " + path
                in result.stderr.splitlines()} != set(paths):
        raise RuntimeError("No se pudo comprobar la propiedad de todos los archivos de la integración.")
    return owners


def request_host_update(formato, version):
    """Stage the signed payload for the root timer, without prompting or networking."""
    if formato not in ("flatpak", "appimage"):
        raise ValueError("Formato de integración no compatible.")
    prefix = ["flatpak-spawn", "--host"] if formato == "flatpak" else []
    owners = host_package_owners(formato)
    if owners:
        return owners == {"aio-debian-gui-host"} and _request_legacy_host_update(formato, version)
    exists = subprocess.run([*prefix, '/usr/bin/test', '-f', '/var/lib/aio-debian-gui/portable-version'],
                            timeout=10)
    if exists.returncode:
        return False
    payload = (_portable_directory(formato) / 'payload.json').read_bytes()
    subprocess.run([*prefix, '/usr/bin/python3', '-I', '-c', _STAGE_PROGRAM],
                   input=payload, check=True, timeout=30)
    return True


def _privileged(formato, program, payload):
    proc = None
    try:
        cmd = ["/usr/bin/pkexec", "/usr/bin/python3", "-I", "-c", program]
        if formato == "flatpak":
            cmd = ["flatpak-spawn", "--host", *cmd]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = b"", b""
        streams = [proc.stdout, proc.stderr]
        deadline = time.monotonic() + 120
        while b"\n" not in stdout:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _stop_process(proc)
                raise RuntimeError("Tiempo de autorización agotado; no se inició la instalación.")
            readable, _, _ = select.select(streams, [], [], remaining)
            if not readable:
                continue
            for stream in readable:
                part = os.read(stream.fileno(), 4096)
                if not part:
                    streams.remove(stream)
                    if not streams:
                        proc.wait(timeout=5)
                        raise RuntimeError("Autorización cancelada o fallida: " +
                                           (stderr.decode("utf-8", "replace").strip() or str(proc.returncode)))
                    continue
                if stream is proc.stdout:
                    stdout += part
                else:
                    stderr += part
        if stdout != b"READY\n":
            _stop_process(proc)
            raise RuntimeError("Respuesta inesperada del instalador privilegiado.")
        try:
            out, err = proc.communicate(payload, timeout=180)
        except subprocess.TimeoutExpired as exc:
            _stop_process(proc)
            raise RuntimeError("Tiempo de instalación agotado; comprueba el estado antes de reintentar.") from exc
        if proc.returncode:
            detail = (stderr + err + out).decode("utf-8", "replace").strip()
            if proc.returncode == 75:
                raise RepositoryUnavailable(detail)
            raise RuntimeError("No se pudo instalar la integración: " + (detail or str(proc.returncode)))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise RuntimeError("No se pudo preparar la integración: " + str(exc)) from exc
    finally:
        if proc is not None and proc.poll() is None:
            _stop_process(proc)


def commands(formato, appimage=None):
    """Devuelve comandos separados para extracción e instalación, sin ejecutarlos."""
    if formato == "flatpak":
        extract = f"""APP={APP_ID}
for f in aio-debian-gui-helper es.aiodebian.gui.policy aio-debian-gui-maintenance@.service; do
  flatpak run --command=cat "$APP" "/app/share/aio-debian-gui/host-integration/$f" > "$f"
done
for f in __init__.py scheduler.py preflight.py; do
  flatpak run --command=cat "$APP" "/app/lib/aio-debian-gui/aio_core/$f" > "$f"
done"""
    elif formato == "appimage":
        if not appimage or not os.path.isabs(appimage) or "\n" in appimage or "\r" in appimage:
            raise ValueError("No se pudo determinar la ruta absoluta del AppImage.")
        extract = f"""APPIMAGE={shlex.quote(appimage)}
"$APPIMAGE" --appimage-extract >/dev/null
cp squashfs-root/usr/lib/aio-debian-gui/aio-debian-gui-helper .
cp squashfs-root/usr/lib/aio-debian-gui/aio_core/{{__init__,scheduler,preflight}}.py .
cp squashfs-root/usr/lib/systemd/system/aio-debian-gui-maintenance@.service .
cp squashfs-root/usr/share/polkit-1/actions/es.aiodebian.gui.policy ."""
    else:
        raise ValueError("Formato de integración no compatible.")

    extract = f"""(
set -e
INTEGRACION=$(mktemp -d "$HOME/aio-debian-gui-integracion.XXXXXXXX")
cd "$INTEGRACION"
echo "Directorio: $INTEGRACION"
{extract}
echo "Revisa los archivos en $INTEGRACION antes de instalar."
)"""

    install = """(
set -e
for f in aio-debian-gui-helper es.aiodebian.gui.policy aio-debian-gui-maintenance@.service __init__.py scheduler.py preflight.py; do
  test -s "$f" || { echo "Falta $f. Ejecuta este bloque desde el directorio de extracción." >&2; exit 1; }
done
if dpkg-query -W -f='${db:Status-Status}' aio-debian-gui 2>/dev/null | grep -qx installed; then
  echo "El DEB está instalado. Actualízalo con APT; no sobrescribas sus archivos." >&2
  exit 1
fi
for f in /usr/lib/aio-debian-gui/aio-debian-gui-helper /usr/lib/aio-debian-gui/aio_core/__init__.py /usr/lib/aio-debian-gui/aio_core/scheduler.py /usr/lib/aio-debian-gui/aio_core/preflight.py /usr/share/polkit-1/actions/es.aiodebian.gui.policy /usr/lib/systemd/system/aio-debian-gui-maintenance@.service; do
  if resultado=$(LC_ALL=C dpkg-query -S "$f" 2>&1); then
    echo "Archivo gestionado por un paquete: $f. No se instalará la integración." >&2
    exit 1
  elif [ "$resultado" != "dpkg-query: no path found matching pattern $f" ]; then
    echo "No se pudo verificar el propietario de $f: $resultado" >&2
    exit 1
  fi
done
sudo install -D -o root -g root -m 0755 aio-debian-gui-helper /usr/lib/aio-debian-gui/aio-debian-gui-helper
for f in __init__.py scheduler.py preflight.py; do
  sudo install -D -o root -g root -m 0644 "$f" "/usr/lib/aio-debian-gui/aio_core/$f"
done
sudo install -D -o root -g root -m 0644 es.aiodebian.gui.policy /usr/share/polkit-1/actions/es.aiodebian.gui.policy
sudo install -D -o root -g root -m 0644 aio-debian-gui-maintenance@.service /usr/lib/systemd/system/aio-debian-gui-maintenance@.service
sudo systemctl daemon-reload
)"""
    return extract, install
