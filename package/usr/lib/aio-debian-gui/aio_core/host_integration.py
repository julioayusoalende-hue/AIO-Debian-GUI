"""Integración inicial en el anfitrión y guía manual."""
import base64
import hashlib
import json
import os
from pathlib import Path
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

def check_residual():
    directory("/etc")
    directory("/var/lib")
    for path in ("/etc/aio-debian-gui", "/var/lib/aio-debian-gui"):
        if os.path.lexists(path):
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
                                fail("Existe una dependencia anterior: " + base + "/" + entry.name + "/" + child.name)
    for subcommand in ("list-units", "list-unit-files"):
        p = command(["/usr/bin/systemctl", subcommand, "--all", "--plain", "--no-legend",
                     "--no-pager"])
        if p.returncode:
            fail("No se pudieron comprobar las unidades systemd: " + (p.stderr or p.stdout).strip()[-600:])
        for line in p.stdout.splitlines():
            fields = line.split()
            if fields and fields[0].startswith(("aio-debian-gui-maintenance@", "aio-debian-gui-maintenance-")):
                fail("Existen unidades o temporizadores de AiO en systemd.")
    p = command(["/usr/bin/systemctl", "list-units", "--all", "--plain", "--no-legend",
                 "--no-pager", "--type=timer"])
    if p.returncode:
        fail("No se pudieron enumerar los temporizadores: " + (p.stderr or p.stdout).strip()[-600:])
    timers = []
    for line in p.stdout.splitlines():
        fields = line.split()
        if not fields or not fields[0].endswith(".timer"):
            fail("Respuesta de systemd no válida al enumerar temporizadores.")
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
    check_residual()
    for _, path, _ in RESOURCES:
        absent(directory(os.path.dirname(path)), os.path.basename(path))
    directory("/run/aio-debian-gui", True)
    lock_file("/run/aio-debian-gui/maintenance.lock", create=True)
    check_residual()
    directories.clear()

    published = False
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
        # La integración no está disponible hasta publicar el helper completo.
        p = command(["/usr/bin/systemctl", "daemon-reload"])
        if p.returncode:
            fail("No se pudo recargar systemd: " + (p.stderr or p.stdout).strip()[-600:])
        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
        try:
            os.link("/proc/self/fd/" + str(helper_fd), os.path.basename(helper_path),
                    dst_dir_fd=helper_parent, follow_symlinks=True)
            published = True
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        created.append((helper_parent, os.path.basename(helper_path)))
    except BaseException as original:
        if published:
            raise
        errors = []
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
        if created:
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


def install(formato, appimage=None):
    """Instala solo una integración inicial; lanza RuntimeError si falla."""
    proc = None
    try:
        payload = json.dumps(_resources(formato, appimage)).encode("ascii")
        cmd = ["/usr/bin/pkexec", "/usr/bin/python3", "-I", "-c", _ROOT_PROGRAM]
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
