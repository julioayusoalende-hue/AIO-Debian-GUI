#!/usr/bin/env python3
"""Comprueba el DEB host y el repositorio firmado sin instalar paquetes."""
import hashlib
import gzip
import fcntl
import importlib.util
import io
import lzma
import os
from pathlib import Path
import re
import select
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
WORK = ROOT / (".host-package-test-" + str(os.getpid()))
WORK.mkdir(mode=0o700)
GNUPG = WORK / "gnupg"
GNUPG.mkdir(mode=0o700)
(GNUPG / "gpg.conf").write_text("no-autostart\n")
# GnuPG limita la longitud de los sockets Unix; /proc mantiene corta la ruta
# sin sacar los archivos del árbol de pruebas.
GPG_HOME = f"/proc/{os.getpid()}/cwd/{WORK.name}/gnupg"
ENV = {**os.environ, "GNUPGHOME": GPG_HOME, "LC_ALL": "C"}
AGENT = None
AGENT_SOCKET = None


def run(*args, check=True, **kwargs):
    result = subprocess.run(args, cwd=ROOT, env=ENV, capture_output=True, **kwargs)
    if check and result.returncode:
        raise AssertionError(f"{args}: {result.stderr!r}")
    return result


def contents(deb, option):
    data = run("dpkg-deb", option, str(deb)).stdout
    with tarfile.open(fileobj=io.BytesIO(data), mode="r|*") as archive:
        return {member.name.removeprefix("./"): (member, archive.extractfile(member).read()
                if member.isfile() else None) for member in archive}


def field(deb, name):
    return run("dpkg-deb", "-f", str(deb), name, text=True).stdout.strip()


def make_version(deb, version, destination):
    stage = WORK / (field(deb, "Package") + "-" + version)
    run("dpkg-deb", "--raw-extract", str(deb), str(stage))
    control = stage / "DEBIAN/control"
    text = control.read_text()
    text, count = re.subn(r"^Version: .+$", "Version: " + version, text, flags=re.M)
    assert count == 1
    control.write_text(text)
    output = destination / (field(deb, "Package") + "_" + version + "_all.deb")
    run("dpkg-deb", "--root-owner-group", "--build", str(stage), str(output))
    return output


def conflict(existing, incoming):
    root = WORK / ("dpkg-" + existing)
    database = root / "var/lib/dpkg"
    database.mkdir(parents=True)
    conflicts = "Conflicts: aio-debian-gui\n" if existing == "aio-debian-gui-host" else ""
    (database / "status").write_text(
        f"Package: {existing}\nStatus: install ok installed\n"
        "Priority: optional\nSection: admin\nArchitecture: all\nVersion: 2.10.8\n"
        f"Maintainer: fixture\nDescription: fixture\n{conflicts}\n")
    result = run("dpkg", "--root=" + str(root), "--force-not-root", "--force-depends",
                 "--no-act", "--unpack", str(incoming), check=False, text=True)
    assert result.returncode != 0 and "conflict" in result.stderr.lower(), result.stderr


def start_agent():
    # La activación por socket mantiene gpg-agent en primer plano como hijo directo.
    launcher = (
        "import os,sys; fd=int(sys.argv[1]); os.dup2(fd,3); "
        "os.set_inheritable(3,True); os.environ['LISTEN_PID']=str(os.getpid()); "
        "os.environ['LISTEN_FDS']='1'; "
        "os.execvp('gpg-agent',['gpg-agent','--homedir',sys.argv[2],"
        "'--supervised','--disable-scdaemon'])"
    )
    # gpg puede usar /run/user/<uid>/gnupg en lugar del directorio personal; se le pregunta dónde.
    global AGENT_SOCKET
    path = AGENT_SOCKET = run("gpgconf", "--list-dirs", "agent-socket", text=True).stdout.strip()
    Path(path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.path.lexists(path):
        os.unlink(path)
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(path)
        listener.listen(16)
        return subprocess.Popen([sys.executable, "-I", "-c", launcher,
                                 str(listener.fileno()), GPG_HOME],
                                cwd=ROOT, env=ENV, pass_fds=(listener.fileno(),),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_agent(agent):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if agent.poll() is not None:
            raise RuntimeError(f"El agente GPG terminó prematuramente: {agent.returncode}")
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(0.5)
                client.connect(AGENT_SOCKET)
                if client.recv(128).startswith(b"OK"):
                    return
        except OSError:
            pass
        time.sleep(0.05)
    raise RuntimeError("El agente GPG no respondió.")


try:
    run("bash", "scripts/build-host-deb.sh", WORK.name + "/build-output")
    version = re.search(r"^Version: (.+)$", (ROOT / "package/DEBIAN/control").read_text(), re.M)[1]
    host = WORK / "build-output" / f"aio-debian-gui-host_{version}_all.deb"
    main = WORK / f"aio-debian-gui_{version}_all.deb"
    main_stage = WORK / "main-stage"
    shutil.copytree(ROOT / "package", main_stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("postinst", "prerm"):
        (main_stage / "DEBIAN" / name).chmod(0o755)
    run("dpkg-deb", "--root-owner-group", "--build", str(main_stage), str(main))
    assert field(host, "Package") == "aio-debian-gui-host"
    assert field(host, "Version") == version == field(main, "Version")
    assert field(host, "Conflicts") == "aio-debian-gui"
    assert field(host, "Replaces") == ""
    data = contents(host, "--fsys-tarfile")
    expected = {
        "usr/lib/aio-debian-gui/aio-debian-gui-helper",
        "usr/lib/aio-debian-gui/aio-host-scheduler",
        "usr/lib/aio-debian-gui/aio_core/__init__.py",
        "usr/lib/aio-debian-gui/aio_core/scheduler.py",
        "usr/lib/aio-debian-gui/aio_core/preflight.py",
        "usr/lib/aio-debian-gui/aio_core/host_repository.py",
        "usr/lib/aio-debian-gui/aio_core/host_requests.py",
        "usr/lib/aio-debian-gui/aio_core/host_updater.py",
        "usr/lib/aio-debian-gui/aio-host-update",
        "usr/lib/systemd/system/aio-debian-gui-host-update.service",
        "usr/lib/systemd/system/aio-debian-gui-host-update.timer",
        "usr/lib/systemd/system/aio-debian-gui-maintenance@.service",
        "usr/share/polkit-1/actions/es.aiodebian.gui.policy",
        "usr/share/keyrings/aio-debian-gui-host.gpg",
        "usr/share/doc/aio-debian-gui-host/copyright",
    }
    files = {path for path, (member, _) in data.items() if member.isfile()}
    assert files == expected, files
    for path in expected:
        member, payload = data[path]
        source_path = path.replace("usr/share/doc/aio-debian-gui-host/",
                                   "usr/share/doc/aio-debian-gui/")
        source_path = source_path.replace("usr/share/keyrings/aio-debian-gui-host.gpg",
                                          "usr/share/keyrings/aio-debian-gui.gpg")
        source = ("host-package" if path.endswith((
            "aio-host-scheduler", "aio-host-update", "host_requests.py", "host_updater.py",
            "aio-debian-gui-maintenance@.service", "aio-debian-gui-host-update.service",
            "aio-debian-gui-host-update.timer")) else "package")
        assert payload == (ROOT / source / source_path).read_bytes()
        assert member.uid == member.gid == 0
        assert member.mode == (0o755 if path.endswith(("aio-debian-gui-helper", "aio-host-scheduler", "aio-host-update")) else 0o644)
    assert all(not path.startswith(("etc/", "var/")) for path in data)

    # Prueba la puerta con rutas temporales y un programador simulado, sin systemd real.
    gate_dir = WORK / "gate"
    gate_dir.mkdir(mode=0o700)
    runtime = gate_dir / "runtime"
    fake_scheduler = gate_dir / "scheduler.py"
    fake_scheduler.write_text(
        'import sys\nprint("started", flush=True)\nsys.stdin.readline()\n')
    gate = gate_dir / "aio-host-scheduler"
    gate.write_text(
        (ROOT / "host-package/usr/lib/aio-debian-gui/aio-host-scheduler").read_text()
        .replace('DIRECTORY = "/run/aio-debian-gui"', f"DIRECTORY = {str(runtime)!r}")
        .replace('SCHEDULER = "/usr/lib/aio-debian-gui/aio_core/scheduler.py"',
                 f"SCHEDULER = {str(fake_scheduler)!r}")
        .replace("os.geteuid() != 0", f"os.geteuid() != {os.geteuid()}")
        .replace("info.st_uid != 0", f"info.st_uid != {os.geteuid()}"))
    runtime.mkdir(mode=0o755)
    lock_path = runtime / "host-update.lock"
    with lock_path.open("w") as lock:
        lock_path.chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        process = subprocess.Popen([sys.executable, "-I", str(gate), "--run", "1000"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            assert not select.select([process.stdout], [], [], 0.3)[0]
            assert process.poll() is None
            fcntl.flock(lock, fcntl.LOCK_UN)
            assert select.select([process.stdout], [], [], 5)[0]
            assert process.stdout.readline() == "started\n"
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("El programador no mantuvo el bloqueo compartido")
            process.communicate("\n", timeout=5)
            assert process.returncode == 0
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    lock_path.unlink()
    lock_path.symlink_to(fake_scheduler)
    rejected = subprocess.run([sys.executable, "-I", str(gate), "--run", "1000"],
                              capture_output=True, timeout=5)
    assert rejected.returncode != 0
    lock_path.unlink()
    runtime.chmod(0o777)
    rejected = subprocess.run([sys.executable, "-I", str(gate), "--run", "1000"],
                              capture_output=True, timeout=5)
    assert rejected.returncode != 0

    request_spec = importlib.util.spec_from_file_location(
        "host_requests", ROOT / "host-package/usr/lib/aio-debian-gui/aio_core/host_requests.py")
    request_reader = importlib.util.module_from_spec(request_spec)
    request_spec.loader.exec_module(request_reader)
    request_reader.ROOT_UID = os.geteuid()
    request_reader.CONFIG_DIR = WORK / "request-config"
    request_reader.RUNTIME_DIR = WORK / "request-runtime"
    request_reader.CONFIG_DIR.mkdir(mode=0o755)
    request_reader.RUNTIME_DIR.mkdir(mode=0o755)
    uid = os.getuid() or 65534
    authorized = request_reader.CONFIG_DIR / "host-users"
    authorized.write_text(f"{uid}\n")
    assert request_reader.authorized_users() == [uid]
    authorized.write_text(f"{uid}\n{uid}\n")
    try:
        request_reader.authorized_users()
    except ValueError:
        pass
    else:
        raise AssertionError("Se aceptaron usuarios autorizados duplicados")
    authorized.write_text(f"{uid}\n")
    authorized.chmod(0o666)
    try:
        request_reader.authorized_users()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Se aceptó una lista de autorización modificable")
    authorized.chmod(0o644)
    runtime = request_reader.RUNTIME_DIR / str(uid)
    assert request_reader.read_request(uid) is None
    runtime.mkdir(mode=0o700)
    if os.getuid() == 0:
        os.chown(runtime, uid, -1)
    request = runtime / "aio-debian-gui-host-version"
    request.write_text("2.10.8\n")
    request.chmod(0o600)
    if os.getuid() == 0:
        os.chown(request, uid, -1)
    assert request_reader.read_request(uid) == "2.10.8"
    for data in ("../../bad\n", "2.10.8\nextra", "9" * 42 + ".0.0\n"):
        request.write_text(data)
        try:
            request_reader.read_request(uid)
        except ValueError:
            pass
        else:
            raise AssertionError("Se aceptó una solicitud no válida")
    request.write_text("2.10.8\n")
    request.chmod(0o666)
    try:
        request_reader.read_request(uid)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Se aceptó una solicitud modificable por terceros")
    request.unlink()
    request.symlink_to(authorized)
    try:
        request_reader.read_request(uid)
    except OSError:
        pass
    else:
        raise AssertionError("Se aceptó una solicitud mediante enlace simbólico")

    controls = contents(host, "--ctrl-tarfile")
    assert {name for name, (entry, _) in controls.items() if entry.isfile()} == {
        "control", "postinst", "postrm"}
    for name in ("postinst", "postrm"):
        assert controls[name][0].mode == 0o755
        script = controls[name][1].decode()
        checked = script.replace("systemctl start aio-debian-gui-host-update.timer", "")
        assert "daemon-reload" in script and not re.search(
            r"\b(disable|enable|stop|start|restart|rm|unlink)\b", checked)
        run("sh", "-n", input=script, text=True)
    simulated = WORK / "systemd"
    simulated.mkdir()
    binaries = WORK / "bin"
    binaries.mkdir()
    systemctl = binaries / "systemctl"
    systemctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n')
    systemctl.chmod(0o755)
    calls = WORK / "systemctl-calls"
    state = WORK / "retained"
    for path in ("etc/aio-debian-gui/schedules/1000.json",
                 "var/lib/aio-debian-gui/schedules/1000.json",
                 "etc/systemd/system/aio-debian-gui-maintenance-1000.timer"):
        dest = state / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("unchanged\n")
    link = state / "etc/systemd/system/timers.target.wants/aio-debian-gui-maintenance-1000.timer"
    link.parent.mkdir()
    link.symlink_to("../aio-debian-gui-maintenance-1000.timer")
    scripts_env = {**ENV, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                   "SIMULATED_SYSTEMD": str(simulated), "CALLS": str(calls)}
    for name, actions in (("postinst", ("configure", "abort-upgrade")),
                          ("postrm", ("remove", "purge", "upgrade", "failed-upgrade"))):
        script = controls[name][1].decode().replace("/run/systemd/system", '"$SIMULATED_SYSTEMD"')
        for action in actions:
            subprocess.run(["sh", "-s", "--", action], input=script, text=True, env=scripts_env,
                           cwd=state, check=True, capture_output=True)
    assert calls.read_text().splitlines() == [
        "daemon-reload", "start aio-debian-gui-host-update.timer", "daemon-reload", "daemon-reload"]
    assert all(path.read_text() == "unchanged\n" for path in state.rglob("*") if path.is_file())
    assert link.is_symlink() and os.readlink(link) == "../aio-debian-gui-maintenance-1000.timer"
    conflict("aio-debian-gui", host)
    conflict("aio-debian-gui-host", main)

    failed_builder = binaries / "dpkg-deb"
    failed_builder.write_text('#!/bin/sh\nfor arg do last="$arg"; done\nprintf partial > "$last"\nexit 1\n')
    failed_builder.chmod(0o755)
    failure_dir = WORK / "build-failure"
    failure_dir.mkdir()
    existing_deb = failure_dir / host.name
    existing_deb.write_bytes(b"existing")
    failure = subprocess.run(["bash", "scripts/build-host-deb.sh", WORK.name + "/build-failure"],
                             cwd=ROOT, env=scripts_env, capture_output=True)
    assert failure.returncode != 0
    assert list(failure_dir.iterdir()) == [existing_deb]
    assert existing_deb.read_bytes() == b"existing"
    failed_builder.unlink()

    AGENT = start_agent()
    wait_agent(AGENT)
    run("gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "",
        "--quick-generate-key", "AiO fixture <fixture@example.invalid>", "ed25519", "sign", "0")
    source = WORK / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "package/usr/share/keyrings").mkdir(parents=True)
    for name in ("publish-apt-repo.sh", "site-index.html"):
        shutil.copyfile(ROOT / "scripts" / name, source / "scripts" / name)
    keyring = source / "package/usr/share/keyrings/aio-debian-gui.gpg"
    keyring.write_bytes(run("gpg", "--batch", "--export").stdout)
    site = WORK / "site"
    site.mkdir()
    fixtures = WORK / "fixtures"
    fixtures.mkdir()
    pairs = []
    for v in ("1.0.0", "1.0.1", "1.0.2"):
        pairs.append((make_version(main, v, fixtures), make_version(host, v, fixtures)))
    publish_env = {**ENV, "KEEP_VERSIONS": "2"}
    for main_deb, host_deb in pairs:
        subprocess.run(["bash", str(source / "scripts/publish-apt-repo.sh"),
                        str(main_deb), str(site), str(host_deb)],
                       env=publish_env, cwd=ROOT, check=True, capture_output=True)
        for repository in (site, site / "host-repo"):
            run("gpgv", "--keyring", str(keyring), str(repository / "dists/stable/InRelease"))
            run("gpgv", "--keyring", str(keyring), str(repository / "dists/stable/Release.gpg"),
                str(repository / "dists/stable/Release"))
    pool = site / "pool/main/a/aio-debian-gui"
    host_site = site / "host-repo"
    host_pool = host_site / "pool/main/a/aio-debian-gui"
    assert sorted(p.name for p in pool.glob("*.deb")) == [pair[0].name for pair in pairs[1:]]
    assert sorted(p.name for p in host_pool.glob("*.deb")) == [pair[1].name for pair in pairs[1:]]
    for repository, package in ((site, "aio-debian-gui"), (host_site, "aio-debian-gui-host")):
        packages = (repository / "dists/stable/main/binary-all/Packages").read_text()
        release = (repository / "dists/stable/Release").read_text()
        checksum = re.search(r"(?m)^ ([0-9a-f]{64})\s+(\d+) main/binary-all/Packages$", release)
        assert checksum and checksum[1] == hashlib.sha256(packages.encode()).hexdigest()
        assert int(checksum[2]) == len(packages.encode())
        binary = repository / "dists/stable/main/binary-all"
        assert gzip.decompress((binary / "Packages.gz").read_bytes()) == packages.encode()
        assert lzma.decompress((binary / "Packages.xz").read_bytes()) == packages.encode()
        entries = [dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
                   for block in packages.strip().split("\n\n")]
        assert [entry["Package"] for entry in entries] == [package]
        entry = entries[0]
        assert entry["Version"] == "1.0.2"
        deb = repository / entry["Filename"]
        assert entry["SHA256"] == hashlib.sha256(deb.read_bytes()).hexdigest()

    spec = importlib.util.spec_from_file_location(
        "host_repository", ROOT / "package/usr/lib/aio-debian-gui/aio_core/host_repository.py")
    repository_verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(repository_verifier)
    host_release = (host_site / "dists/stable/InRelease").read_bytes()
    host_index = (host_site / "dists/stable/main/binary-all/Packages").read_bytes()
    expected_index = repository_verifier.verify_release(host_release, keyring)
    host_metadata = repository_verifier.verify_index(host_index, expected_index)
    assert host_metadata["version"] == "1.0.2"
    host_bytes = (host_site / host_metadata["filename"]).read_bytes()
    repository_verifier.verify_package(host_bytes, host_metadata)
    requested = []
    responses = [host_release, host_index, host_bytes]

    class FixtureOpener:
        def open(self, request, timeout):
            requested.append((request.full_url, timeout, request.get_header("Accept-encoding")))
            return io.BytesIO(responses.pop(0))

    with mock.patch.object(repository_verifier.urllib.request, "build_opener",
                           return_value=FixtureOpener()):
        metadata, payload = repository_verifier.download_package(keyring)
    assert metadata == host_metadata and payload == host_bytes and not responses
    assert requested == [
        (repository_verifier.BASE_URL + "dists/stable/InRelease", 30, "identity"),
        (repository_verifier.BASE_URL + "dists/stable/" + repository_verifier.INDEX, 30, "identity"),
        (repository_verifier.BASE_URL + host_metadata["filename"], 30, "identity"),
    ]

    def reject(function, *args):
        try:
            function(*args)
        except ValueError:
            return
        raise AssertionError(f"Se aceptaron metadatos o paquetes no válidos: {function.__name__}")

    reject(repository_verifier.verify_release, host_release.replace(b"Origin:", b"OrigIn:"), keyring)
    reject(repository_verifier.verify_release, (site / "dists/stable/InRelease").read_bytes(), keyring)
    reject(repository_verifier.verify_index, host_index + b"bad", expected_index)
    reject(repository_verifier.verify_package, host_bytes + b"bad", host_metadata)
    responses[:] = [b"too large"]
    reject(repository_verifier._download, FixtureOpener(), "too-large", 1)
    responses[:] = [host_release.replace(b"Origin:", b"OrigIn:")]
    requested.clear()
    with mock.patch.object(repository_verifier.urllib.request, "build_opener",
                           return_value=FixtureOpener()):
        reject(repository_verifier.download_package, keyring)
    assert len(requested) == 1
    request = repository_verifier.urllib.request.Request(repository_verifier.BASE_URL)
    try:
        repository_verifier._NoRedirect().redirect_request(request, None, 302, "redirect", {}, "https://example.invalid/")
    except repository_verifier.urllib.error.HTTPError:
        pass
    else:
        raise AssertionError("Se aceptó una redirección del repositorio.")
    for bad_index in (
        host_index + b"\n" + host_index,
        host_index.replace(b"Package: aio-debian-gui-host\n",
                           b"Package: aio-debian-gui-host\nPackage: other\n"),
        host_index.replace(host_metadata["filename"].encode(), b"../../etc/passwd"),
        host_index.replace(b"Version: 1.0.2", b"Version: 1.0.2-evil"),
    ):
        reject(repository_verifier.verify_index, bad_index,
               (hashlib.sha256(bad_index).hexdigest(), len(bad_index)))
    signed = site / "dists/stable/InRelease"
    original = signed.read_bytes()
    signed.write_bytes(original.replace(b"Origin: aio-debian-gui", b"Origin: altered"))
    assert run("gpgv", "--keyring", str(keyring), str(signed), check=False).returncode != 0
    signed.write_bytes(original)
    # La interfaz antigua de dos argumentos no modifica el repositorio host.
    host_signature = (host_site / "dists/stable/InRelease").read_bytes()
    subprocess.run(["bash", str(source / "scripts/publish-apt-repo.sh"), str(pairs[-1][0]), str(site)],
                   env=publish_env, cwd=ROOT, check=True, capture_output=True)
    assert (host_pool / pairs[-1][1].name).is_file()
    assert (host_site / "dists/stable/InRelease").read_bytes() == host_signature
    before = (site / "dists/stable/InRelease").read_bytes()
    pool_before = {path.name: hashlib.sha256(path.read_bytes()).digest() for path in pool.glob("*.deb")}
    bad_stage = WORK / "bad-host"
    run("dpkg-deb", "--raw-extract", str(pairs[-1][1]), str(bad_stage))
    control = bad_stage / "DEBIAN/control"
    control.write_text(control.read_text() + "Replaces: aio-debian-gui\n")
    bad_dir = WORK / "bad-output"
    bad_dir.mkdir()
    bad_deb = bad_dir / pairs[-1][1].name
    run("dpkg-deb", "--root-owner-group", "--build", str(bad_stage), str(bad_deb))
    for args, env in (
        ([str(pairs[-1][0]), str(site), str(pairs[0][1])], publish_env),
        ([str(pairs[-1][0]), str(site), str(bad_deb)], publish_env),
        ([str(pairs[-1][0]), str(site), str(pairs[-1][1])],
         {**publish_env, "EXPECTED_FPR": "not-the-project-key"}),
    ):
        result = subprocess.run(["bash", str(source / "scripts/publish-apt-repo.sh"), *args],
                                env=env, cwd=ROOT, capture_output=True)
        assert result.returncode != 0
        assert (site / "dists/stable/InRelease").read_bytes() == before
        assert {path.name: hashlib.sha256(path.read_bytes()).digest()
                for path in pool.glob("*.deb")} == pool_before
    # Aunque tenga otro nombre de archivo, un host en el pool global bloquea la publicación.
    misplaced = pool / "unexpected_all.deb"
    shutil.copyfile(pairs[-1][1], misplaced)
    result = subprocess.run(["bash", str(source / "scripts/publish-apt-repo.sh"),
                             str(pairs[-1][0]), str(site), str(pairs[-1][1])],
                            env=publish_env, cwd=ROOT, capture_output=True)
    assert result.returncode != 0
    assert (site / "dists/stable/InRelease").read_bytes() == before
    assert (host_site / "dists/stable/InRelease").read_bytes() == host_signature
finally:
    if AGENT is not None and AGENT.poll() is None:
        AGENT.terminate()
        try:
            AGENT.wait(timeout=3)
        except subprocess.TimeoutExpired:
            AGENT.kill()
            AGENT.wait()
    shutil.rmtree(WORK)
print("Paquete host, conflictos dpkg y publicación APT firmada: OK")
