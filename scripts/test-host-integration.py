#!/usr/bin/env python3
"""Prueba la guía sin ejecutar operaciones privilegiadas reales."""
import importlib.util
import base64
from contextlib import nullcontext
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

module = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui/aio_core/host_integration.py"
spec = importlib.util.spec_from_file_location("host_integration", module)
integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integration)

for formato, path in (("flatpak", None), ("appimage", "/home/user/AiO's $(touch bad).AppImage")):
    extract, install = integration.commands(formato, path)
    for command in (extract, install):
        subprocess.run(["bash", "-n"], input=command, text=True, check=True)
    assert "sudo " not in extract
    assert "sudo install" in install and "sudo systemctl daemon-reload" in install
    if path:
        assert "'\"'\"'" in extract

for formato, path in (("appimage", None), ("appimage", "relative"), ("appimage", "/bad\npath"), ("deb", None)):
    try:
        integration.commands(formato, path)
    except ValueError:
        pass
    else:
        raise AssertionError((formato, path))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    runtime = root / str(os.getuid())
    runtime.mkdir(mode=0o700)
    request_program = integration._REQUEST_PROGRAM.replace(
        '"/run/user/"', repr(str(root) + "/"))
    subprocess.run([sys.executable, "-I", "-c", request_program, "2.10.8"],
                   capture_output=True, check=True)
    request = runtime / "aio-debian-gui-host-version"
    assert request.read_text() == "2.10.8\n"
    assert stat.S_IMODE(request.stat().st_mode) == 0o600
    result = subprocess.run([sys.executable, "-I", "-c", request_program, "../../bad"],
                            capture_output=True)
    assert result.returncode and request.read_text() == "2.10.8\n"
    runtime.chmod(0o777)
    result = subprocess.run([sys.executable, "-I", "-c", request_program, "2.10.9"],
                            capture_output=True)
    assert result.returncode and request.read_text() == "2.10.8\n"
    runtime.chmod(0o700)

    installed = SimpleNamespace(returncode=0, stdout="installed", stderr="")
    done = SimpleNamespace(returncode=0, stdout="", stderr="")
    with mock.patch.object(subprocess, "run", side_effect=[installed, done]) as spawned:
        assert integration._request_legacy_host_update("flatpak", "2.10.8")
        query, command = (call.args[0] for call in spawned.call_args_list)
        assert query[:3] == ["flatpak-spawn", "--host", "--env=LC_ALL=C"]
        assert query[3] == "/usr/bin/dpkg-query"
        assert command[:2] == ["flatpak-spawn", "--host"]
        assert command[2:] == ["/usr/bin/python3", "-I", "-c", integration._REQUEST_PROGRAM, "2.10.8"]
    missing = SimpleNamespace(returncode=1, stdout="", stderr="dpkg-query: no packages found matching aio-debian-gui-host")
    with mock.patch.object(subprocess, "run", return_value=missing) as spawned:
        for formato in ("appimage", "flatpak"):
            assert not integration._request_legacy_host_update(formato, "2.10.8")
        assert spawned.call_count == 2
    with mock.patch.object(subprocess, "run", return_value=SimpleNamespace(
            returncode=2, stdout="", stderr="dpkg database failed")):
        try:
            integration._request_legacy_host_update("appimage", "2.10.8")
        except RuntimeError as exc:
            assert "dpkg database failed" in str(exc)
        else:
            raise AssertionError("El fallo de dpkg no se comunicó")
    with mock.patch.object(subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout="half-configured", stderr="")):
        try:
            integration._request_legacy_host_update("appimage", "2.10.8")
        except RuntimeError as exc:
            assert "half-configured" in str(exc)
        else:
            raise AssertionError("La instalación incompleta no se comunicó")
    stage_root = root / "stage"
    stage_runtime = stage_root / str(os.getuid())
    stage_runtime.mkdir(parents=True)
    stage = integration._STAGE_PROGRAM.replace("Path('/run/user')", f"Path({str(stage_root)!r})")
    for version in ("2.10.20", "2.10.19"):
        manifest = json.dumps({"version": version}).encode()
        envelope = json.dumps({"data": base64.b64encode(manifest).decode()})
        subprocess.run([sys.executable, "-I", "-c", stage], input=envelope, text=True, check=True)
    staged = json.loads((stage_runtime / "aio-portable-update").read_text())
    assert json.loads(base64.b64decode(staged["data"]))["version"] == "2.10.20"

    bin_dir = root / "bin"
    bin_dir.mkdir()
    (bin_dir / "flatpak").write_text('#!/bin/sh\nprintf "contenido de %s\\n" "$4"\n')
    (bin_dir / "app image").write_text("""#!/bin/sh
set -e
[ "$1" = --appimage-extract ]
mkdir -p squashfs-root/usr/lib/aio-debian-gui/aio_core squashfs-root/usr/lib/systemd/system squashfs-root/usr/share/polkit-1/actions
for f in usr/lib/aio-debian-gui/aio-debian-gui-helper usr/lib/aio-debian-gui/aio_core/__init__.py usr/lib/aio-debian-gui/aio_core/scheduler.py usr/lib/aio-debian-gui/aio_core/preflight.py usr/lib/systemd/system/aio-debian-gui-maintenance@.service usr/share/polkit-1/actions/es.aiodebian.gui.policy; do
  echo contenido > "squashfs-root/$f"
done
""")
    (bin_dir / "dpkg-query").write_text("""#!/bin/sh
if [ "$1" = -W ]; then
  [ "$MODE" = deb ] && { printf installed; exit 0; }
  exit 1
fi
case "$MODE" in
  owned) echo "package: $2"; exit 0 ;;
  error) echo "database unavailable" >&2; exit 2 ;;
  *) echo "dpkg-query: no path found matching pattern $2" >&2; exit 1 ;;
esac
""")
    (bin_dir / "sudo").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n')
    for path in bin_dir.iterdir():
        path.chmod(0o755)
    files = ("aio-debian-gui-helper", "es.aiodebian.gui.policy", "aio-debian-gui-maintenance@.service",
             "__init__.py", "scheduler.py", "preflight.py")
    for name in files:
        (root / name).write_text("contenido\n")
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "CALLS": str(root / "calls")}
    for formato, path in (("flatpak", None), ("appimage", str(bin_dir / "app image"))):
        result = subprocess.run(["bash", "-c", integration.commands(formato, path)[0]],
                                env={**env, "HOME": str(root)}, capture_output=True, text=True, check=True)
        directory = Path(next(line.removeprefix("Directorio: ") for line in result.stdout.splitlines()
                              if line.startswith("Directorio: ")))
        assert all((directory / name).stat().st_size for name in files)
    command = integration.commands("flatpak")[1]
    for mode in ("deb", "owned", "error"):
        result = subprocess.run(["bash", "-c", command], cwd=root,
                                env={**env, "MODE": mode}, capture_output=True, text=True)
        assert result.returncode != 0, (mode, result.stdout, result.stderr)
        assert not (root / "calls").exists()
    (root / "preflight.py").unlink()
    result = subprocess.run(["bash", "-c", command], cwd=root,
                            env={**env, "MODE": "ok"}, capture_output=True, text=True)
    assert result.returncode != 0 and not (root / "calls").exists()
    (root / "preflight.py").write_text("contenido\n")
    subprocess.run(["bash", "-c", command], cwd=root, env={**env, "MODE": "ok"},
                   capture_output=True, text=True, check=True)
    calls = (root / "calls").read_text().splitlines()
    assert len(calls) == 7 and calls[-1] == "systemctl daemon-reload"

    appdir = root / "mount"
    core = appdir / "usr/lib/aio-debian-gui/aio_core"
    core.mkdir(parents=True)
    paths = {
        **{name: core / name for name in integration._NAMES[:3]},
        "aio-debian-gui-helper": appdir / "usr/lib/aio-debian-gui/aio-debian-gui-helper",
        "es.aiodebian.gui.policy": appdir / "usr/share/polkit-1/actions/es.aiodebian.gui.policy",
        "aio-debian-gui-maintenance@.service": appdir / "usr/lib/systemd/system/aio-debian-gui-maintenance@.service",
    }
    for name, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("resource " + name).encode())
    module_path = core / "host_integration.py"
    module_path.touch()
    image = root / "image with spaces.AppImage"
    image.touch()
    with mock.patch.object(integration, "__file__", str(module_path)), \
         mock.patch.dict(os.environ, {"APPDIR": str(appdir), "APPIMAGE": str(image)}):
        resources = integration._resources("appimage", str(image))
        for name, item in resources.items():
            contents = base64.b64decode(item["data"])
            assert contents == paths[name].read_bytes()
            assert hashlib.sha256(contents).hexdigest() == item["sha256"]
        paths["scheduler.py"].unlink()
        paths["scheduler.py"].symlink_to("/etc/passwd")
        try:
            integration.install("appimage", str(image))
        except RuntimeError:
            pass
        else:
            raise AssertionError("El recurso enlazado no fue rechazado")
        paths["scheduler.py"].unlink()
        paths["scheduler.py"].write_bytes(b"resource scheduler.py")
        try:
            integration.install("appimage", str(root / "other.AppImage"))
        except RuntimeError:
            pass
        else:
            raise AssertionError("Se aceptó un AppImage distinto")
        for invalid in (None, "relative", "/bad\0image"):
            try:
                integration.install("appimage", invalid)
            except RuntimeError as exc:
                assert "ruta absoluta" in str(exc)
            else:
                raise AssertionError(("Ruta aceptada", invalid))

    flatpak = root / "flatpak"
    flat_core = flatpak / "lib/aio-debian-gui/aio_core"
    flat_shared = flatpak / "share/aio-debian-gui/host-integration"
    flat_core.mkdir(parents=True)
    flat_shared.mkdir(parents=True)
    for name in integration._NAMES:
        (flat_core if name in integration._NAMES[:3] else flat_shared).joinpath(name).write_bytes(
            base64.b64decode(resources[name]["data"]))
    flat_module = flat_core / "host_integration.py"
    flat_module.touch()
    marker = root / "flatpak-info"
    marker.touch()
    def fake_path(value):
        return flatpak if value == "/app" else marker if value == "/.flatpak-info" else Path(value)
    with mock.patch.object(integration, "__file__", str(flat_module)), \
         mock.patch.object(integration, "Path", side_effect=fake_path):
        assert integration._resources("flatpak", None) == resources

    real_popen = subprocess.Popen
    launched = []
    def fake_popen(args, **kwargs):
        launched.append(args)
        program = ('import sys; print("READY",flush=True); '
                   'data=sys.stdin.buffer.read(); sys.exit(0 if data else 1)')
        return real_popen([sys.executable, "-c", program], **kwargs)
    with mock.patch.object(integration, "_resources", return_value=resources), \
         mock.patch.object(subprocess, "Popen", side_effect=fake_popen):
        integration.install("flatpak")
    assert launched[0][:5] == ["flatpak-spawn", "--host", "/usr/bin/pkexec", "/usr/bin/python3", "-I"]
    assert launched[0][5:] == ["-c", integration._ROOT_PROGRAM]
    def cancelled(args, **kwargs):
        return real_popen([sys.executable, "-c", 'import sys; print("denied",file=sys.stderr); sys.exit(126)'], **kwargs)
    with mock.patch.object(integration, "_resources", return_value=resources), \
         mock.patch.object(subprocess, "Popen", side_effect=cancelled):
        try:
            integration.install("appimage", str(image))
        except RuntimeError as exc:
            assert "denied" in str(exc)
        else:
            raise AssertionError("No se notificó la cancelación")
    sleeping = []
    def waiting(args, **kwargs):
        process = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        sleeping.append(process)
        return process
    with mock.patch.object(integration, "_resources", return_value=resources), \
         mock.patch.object(subprocess, "Popen", side_effect=waiting), \
         mock.patch.object(integration, "time", SimpleNamespace(monotonic=mock.Mock(side_effect=[0, 121]))):
        try:
            integration.install("flatpak")
        except RuntimeError as exc:
            assert "autorización agotado" in str(exc)
        else:
            raise AssertionError("No se aplicó el timeout de autorización")
    assert sleeping[0].poll() is not None

    def root_test(mode):
        """Ejecuta el texto root contra un árbol simulado, sin pkexec ni sistema real."""
        sandbox = root / ("host-" + mode)
        sandbox.mkdir()
        for path in ("var/lib/dpkg/lock", "var/lib/dpkg/lock-frontend"):
            (sandbox / path).parent.mkdir(parents=True, exist_ok=True)
            (sandbox / path).touch()
        if mode != "missing-lock":
            lock_path = sandbox / "run/aio-debian-gui/maintenance.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.touch(mode=0o600)
        code = integration._ROOT_PROGRAM.rsplit("\ntry:\n    main()", 1)[0]
        code = code.replace('os.open("/", os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)',
                            f'os.open({str(sandbox)!r}, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)')
        code = code.replace('("/etc/aio-debian-gui", "/var/lib/aio-debian-gui")',
                            repr((str(sandbox / "etc/aio-debian-gui"), str(sandbox / "var/lib/aio-debian-gui"))))
        for path in ("/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock", "/run/aio-debian-gui/maintenance.lock"):
            code = code.replace('lock_file("' + path + '"', "lock_file(" + repr(str(sandbox) + path))
        code = code.replace('dir="/run/aio-debian-gui"', 'dir=' + repr(str(sandbox / "run/aio-debian-gui")))
        namespace = {}
        exec(compile(code, "<fixed-root-program-test>", "exec"), namespace)
        commands = []
        recovering = mode.startswith("recover-")
        if recovering:
            namespace["PORTABLE"] = True
            repair = mode == "recover-portable"
            if repair:
                namespace["RESOURCES"] = (namespace["RESOURCES"][:-1] + integration._PORTABLE_EXTRAS
                                          + namespace["RESOURCES"][-1:])
            config = {"enabled": mode != "recover-paused", "frequency": "daily",
                      "weekday": 6, "hour": 9, "minute": 0,
                      "tasks": ["upgrade", "autoclean", "flatpak-update", "rebootcheck"],
                      "launcher": {"format": "deb", "path": ""}}
            if mode == "recover-flatpak":
                config["launcher"] = {"format": "flatpak", "path": ""}
            elif mode == "recover-appimage":
                config["launcher"] = {"format": "appimage", "path": "/home/user/AiO.AppImage"}
            scheduler_file = module.with_name("scheduler.py")
            scheduler_data = scheduler_file.read_bytes()
            scheduler = {"__name__": "_test_scheduler"}
            exec(compile(scheduler_data, str(scheduler_file), "exec"), scheduler)
            config_file = sandbox / "etc/aio-debian-gui/schedules/1000.json"
            config_file.parent.mkdir(parents=True)
            original = json.dumps(config)
            config_file.write_text(original)
            state_file = sandbox / "var/lib/aio-debian-gui/schedules/1000.json"
            state_file.parent.mkdir(parents=True)
            state_file.write_text('{"status": "success"}')
            timer_name = scheduler["timer_name"](1000)
            timer = sandbox / "etc/systemd/system" / timer_name
            timer.parent.mkdir(parents=True)
            timer.write_text(scheduler["timer_text"](1000, config))
            if mode == "recover-missing-unit":
                timer.unlink()
            if mode == "recover-edited":
                timer.write_text(timer.read_text() + "OnBootSec=1s\n")


            if repair:
                (state_file.parent.parent / "portable-version").write_text("2.10.15\n")
                link = timer.parent / "timers.target.wants" / timer_name
                link.parent.mkdir()
                link.symlink_to("../" + timer_name)
                updater = sandbox / "usr/lib/aio-debian-gui/aio-portable-update"
                updater.parent.mkdir(parents=True)
                updater.write_text("previous updater")
                update_timer = sandbox / "usr/lib/systemd/system/aio-portable-update.timer"
                update_timer.parent.mkdir(parents=True)
                update_timer.write_text("previous timer")
                update_timer.with_name("aio-debian-gui-maintenance@.service").write_text("previous service")

        def fake_command(args):
            commands.append(args)
            if args[0].endswith("dpkg-query"):
                if mode == "dpkg-error":
                    return SimpleNamespace(returncode=2, stdout="", stderr="database unavailable")
                if args[1] == "-W":
                    text = "aio-debian-gui\tinstalled\n" if mode == "deb" else "other\tinstalled\n"
                    return SimpleNamespace(returncode=0, stdout=text, stderr="")
                if mode == "owned":
                    return SimpleNamespace(returncode=0, stdout="other: " + args[-1], stderr="")
                return SimpleNamespace(returncode=1, stdout="",
                                       stderr="dpkg-query: no path found matching pattern " + args[-1])
            if recovering and args[1] == "show":
                active = "active" if mode == "recover-active" or repair else "inactive"
                enabled = "enabled" if repair else "disabled"
                return SimpleNamespace(returncode=0, stderr="", stdout=(
                    f"ActiveState={active}\nUnitFileState={enabled}\nDropInPaths=\n"
                    f"FragmentPath=/etc/systemd/system/{timer_name}\n"))
            if recovering and timer.exists() and args[1] == "list-unit-files":
                status = "enabled" if repair else "disabled"
                units = f"{timer_name} {status} enabled\n"
                if repair:
                    units += "aio-debian-gui-maintenance@.service static -\n"
                return SimpleNamespace(returncode=0, stdout=units, stderr="")
            if mode == "recover-activation-error" and args[1:] == ["enable", "--now", timer_name]:
                return SimpleNamespace(returncode=1, stdout="", stderr="activation failed")
            if recovering and repair and args[1] == "list-units":
                return SimpleNamespace(returncode=0, stdout=f"{timer_name} loaded active waiting\n", stderr="")
            if mode == "unit" and args[1] == "list-units":
                return SimpleNamespace(returncode=0, stdout="aio-debian-gui-maintenance-1000.timer loaded active", stderr="")
            if mode == "foreign-timer" and "--type=timer" in args:
                return SimpleNamespace(returncode=0, stdout="custom.timer loaded active waiting", stderr="")
            if mode == "foreign-timer" and args[1] == "show":
                return SimpleNamespace(returncode=0, stdout="Id=custom.timer\nTriggers=aio-debian-gui-maintenance@1000.service\n", stderr="")
            if mode == "reload-error" and args[1] == "daemon-reload" and sum(
                    cmd[1] == "daemon-reload" for cmd in commands if cmd[0].endswith("systemctl")) == 1:
                return SimpleNamespace(returncode=1, stdout="", stderr="reload failed")
            if args[1] == "daemon-reload":
                assert not (sandbox / "usr/lib/aio-debian-gui/aio-debian-gui-helper").exists()
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        namespace["command"] = fake_command
        if mode == "stage-hash":
            real_open = open
            def corrupt_stage(path, access="r", *args, **kwargs):
                if access == "rb" and ".aio-integration-" in str(path):
                    with real_open(path, "ab") as stream:
                        stream.write(b"alterado")
                return real_open(path, access, *args, **kwargs)
            namespace["open"] = corrupt_stage
        if mode == "existing":
            destination = sandbox / "usr/lib/aio-debian-gui/aio_core/scheduler.py"
            destination.parent.mkdir(parents=True)
            destination.write_text("preexisting")
        if mode == "symlink":
            destination = sandbox / "usr/lib/aio-debian-gui/aio_core/scheduler.py"
            destination.parent.mkdir(parents=True)
            destination.symlink_to(sandbox / "missing")
        if mode == "residual":
            (sandbox / "etc/aio-debian-gui").mkdir(parents=True)
        if mode == "timer-file":
            timer = sandbox / "etc/systemd/system/timers.target.wants/aio-debian-gui-maintenance-1000.timer"
            timer.parent.mkdir(parents=True)
            timer.symlink_to(sandbox / "missing-timer")
        if mode == "unsafe":
            unsafe = sandbox / "usr/lib/aio-debian-gui"
            unsafe.mkdir(parents=True)
            unsafe.chmod(0o777)
        if mode == "parent-symlink":
            parent = sandbox / "usr/lib/aio-debian-gui"
            parent.parent.mkdir(parents=True)
            parent.symlink_to(sandbox / "outside", target_is_directory=True)
        held = None
        if mode == "maintenance":
            lock = sandbox / "run/aio-debian-gui/maintenance.lock"
            held = lock.open("w")
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        payload = json.loads(json.dumps(resources))
        if mode == "hash":
            payload["scheduler.py"]["sha256"] = "0" * 64
        if recovering:
            payload["scheduler.py"] = {"data": base64.b64encode(scheduler_data).decode(),
                                       "sha256": hashlib.sha256(scheduler_data).hexdigest()}
            if repair:
                for name, _, _ in integration._PORTABLE_EXTRAS:
                    value = b"2.10.16\n" if name == "portable-version" else name.encode()
                    payload[name] = {"data": base64.b64encode(value).decode(),
                                     "sha256": hashlib.sha256(value).hexdigest()}
        success = mode in ("ok", "missing-lock", "recover-enabled", "recover-paused", "recover-portable",
                           "recover-flatpak", "recover-appimage", "recover-missing-unit")
        stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode()))
        real_fstat = os.fstat

        def fake_fstat(fd):
            values = list(real_fstat(fd))
            values[4] = 0
            return os.stat_result(values)

        with mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "stdout", io.StringIO()), \
             mock.patch.object(os, "geteuid", return_value=0), mock.patch.object(os, "fstat", side_effect=fake_fstat), \
             mock.patch("signal.signal"), mock.patch("pwd.getpwuid"), \
             mock.patch.dict(os.environ, {"PKEXEC_UID": "1000"}), \
             (mock.patch.object(os, "link", side_effect=OSError("publicación fallida"))
              if mode == "link-error" else nullcontext()):
            try:
                namespace["main"]()
            except (OSError, ValueError, RuntimeError) as exc:
                if success:
                    raise
                assert str(exc), mode
            else:
                assert success, mode
            finally:
                for fd in reversed(namespace["handles"]):
                    os.close(fd)
                if held:
                    held.close()
        targets = [sandbox / path.lstrip("/") for _, path, _ in namespace["RESOURCES"]]
        if success:
            assert all(p.is_file() for p in targets)
            assert [name for _, name in namespace["created"]][-1] == "aio-debian-gui-helper"
            assert stat.S_IMODE(targets[-1].stat().st_mode) == 0o755
            assert all(path.read_bytes() == base64.b64decode(payload[name]["data"])
                       for (name, _, _), path in zip(namespace["RESOURCES"], targets))
            if not recovering:
                assert commands[-1][1] == "daemon-reload"
        elif mode == "existing":
            assert targets[1].read_text() == "preexisting"
            assert sum(p.exists() for p in targets) == 1
        elif mode == "symlink":
            assert targets[1].is_symlink()
            assert not any(p.exists() for p in targets)
        else:
            assert not any(p.exists() for p in targets), mode
        if (sandbox / "run/aio-debian-gui").exists():
            assert sorted(p.name for p in (sandbox / "run/aio-debian-gui").iterdir()) == ["maintenance.lock"]
        if mode in ("reload-error", "link-error"):
            assert not (sandbox / "usr/lib/aio-debian-gui").exists()
        if mode in ("deb", "owned", "dpkg-error", "unit", "foreign-timer", "residual", "timer-file",
                    "existing", "symlink", "parent-symlink", "hash", "stage-hash", "unsafe",
                    "maintenance"):
            assert not any(c[1] == "daemon-reload" for c in commands if c[0].endswith("systemctl"))

        if recovering:
            assert state_file.read_text() == '{"status": "success"}'
            assert config_file.read_text() == original
            if success:
                assert timer.exists()
                assert (["/usr/bin/systemctl", "enable", "--now", timer_name] in commands) == (config["enabled"] and not repair)
            else:
                if mode == "recover-activation-error":
                    assert ["/usr/bin/systemctl", "disable", "--now", timer_name] in commands
                    assert ["/usr/bin/systemctl", "disable", "--now", "aio-portable-update.timer"] in commands

    for mode in ("recover-enabled", "recover-paused", "recover-flatpak", "recover-appimage",
                 "recover-portable", "recover-missing-unit", "recover-activation-error", "recover-active", "recover-edited",
                 "ok", "deb", "owned", "dpkg-error", "unit", "foreign-timer", "residual", "timer-file", "existing",
                 "symlink", "parent-symlink", "hash", "stage-hash", "unsafe", "maintenance",
                 "missing-lock", "reload-error", "link-error"):
        root_test(mode)

    def package_test(mode):
        """Ejecuta el instalador del paquete host contra rutas temporales y órdenes simuladas."""
        sandbox = root / ("package-" + mode)
        (sandbox / "etc/aio-debian-gui/schedules").mkdir(parents=True)
        (sandbox / "etc/systemd/system").mkdir(parents=True)
        (sandbox / "run/systemd/system").mkdir(parents=True)
        (sandbox / "etc/aio-debian-gui/schedules/1000.json").write_text('{"enabled": true}')
        (sandbox / "etc/systemd/system/aio-debian-gui-maintenance-1000.timer").touch()
        conflict = sandbox / "conflict.txt"
        if mode == "conflict":
            conflict.write_text("ajeno")
        code = integration._PACKAGE_PROGRAM.rsplit("\nmain()", 1)[0]
        for path in ("/etc/aio-debian-gui", "/etc/systemd/system", "/run/systemd/system"):
            code = code.replace('"' + path + '"', repr(str(sandbox) + path))
        code = code.replace('RUN = "/run/aio-debian-gui"', "RUN = " + repr(str(sandbox / "run/aio-debian-gui")))
        namespace = {}
        exec(compile(code, "<package-program-test>", "exec"), namespace)
        commands = []
        state = {"host": "not-installed"}

        def fake_run(args, timeout=900):
            commands.append(args)
            ok = lambda out="": SimpleNamespace(returncode=0, stdout=out, stderr="")
            if args[0].endswith("dpkg-query") and args[1] == "-W":
                name = args[-1]
                value = "installed" if mode == "deb" and name == "aio-debian-gui" else \
                    state["host"] if name == "aio-debian-gui-host" else "not-installed"
                return SimpleNamespace(returncode=0 if value != "not-installed" else 1, stdout=value, stderr="")
            if args[0].endswith("dpkg-query"):
                return SimpleNamespace(returncode=1, stdout="", stderr="dpkg-query: no path found matching pattern " + args[-1])
            if args[0].endswith("apt-cache"):
                return ok("aio-debian-gui-host:\n  Candidate: 9.9.9\n" if mode == "foreign" else "")
            if args[0].endswith("dpkg-deb") and args[1] == "-f":
                return ok("Package: aio-debian-gui-host\nVersion: 2.10.8\nConflicts: aio-debian-gui\n")
            if args[0].endswith("dpkg-deb"):
                return ok("-rw-r--r-- root/root 1 2026-01-01 00:00 ." + str(conflict) + "\n"
                          if mode == "conflict" else "-rw-r--r-- root/root 1 2026-01-01 00:00 ./usr/new\n")
            if args[0].endswith("dpkg") and args[1] == "--force-confold":
                state["host"] = "installed"
            return ok()
        namespace["run"] = fake_run
        repository = ("def download_package(keyring):\n"
                      + ("    raise OSError('sin red')\n" if mode == "offline" else
                         "    return {'version': '2.10.8'}, b'deb'\n"))
        payload = {"repository": repository, "keyring": base64.b64encode(b"key").decode()}
        stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode()))
        real_fstat = os.fstat
        def fake_fstat(fd):
            values = list(real_fstat(fd))
            values[4] = 0
            return os.stat_result(values)
        outcome = None
        with mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "stdout", io.StringIO()), \
             mock.patch.object(sys, "stderr", io.StringIO()), mock.patch.dict(os.environ, {"PKEXEC_UID": "1000"}), \
             mock.patch.object(os, "geteuid", return_value=0), mock.patch.object(os, "fstat", side_effect=fake_fstat):
            try:
                namespace["main"]()
            except SystemExit as exc:
                outcome = exc.code
        installed = any(c[1:2] == ["--force-confold"] for c in commands)
        if mode == "ok":
            assert outcome is None and installed
            assert (sandbox / "etc/aio-debian-gui/host-users").read_text() == "1000\n"
            assert ["/usr/bin/systemctl", "enable", "--now", "aio-debian-gui-maintenance-1000.timer", ] in commands
        else:
            assert outcome == (75 if mode == "offline" else 1) and not installed, (mode, outcome)
            assert not (sandbox / "etc/aio-debian-gui/host-users").exists()

    for mode in ("ok", "deb", "foreign", "offline", "conflict"):
        package_test(mode)

    with mock.patch.object(integration, "_package_payload", return_value=b"{}"), \
         mock.patch.object(integration, "_privileged", side_effect=integration.RepositoryUnavailable("sin red")), \
         mock.patch.object(integration, "install") as legacy:
        integration._install_legacy_host("flatpak")
    legacy.assert_called_once_with("flatpak", None)
    with mock.patch.object(integration, "_package_payload", return_value=b"{}"), \
         mock.patch.object(integration, "_privileged", side_effect=RuntimeError("DEB")), \
         mock.patch.object(integration, "install") as legacy:
        try:
            integration._install_legacy_host("flatpak")
        except RuntimeError:
            legacy.assert_not_called()
        else:
            raise AssertionError("Error no propagado")

print("✔ Integración manual y automática: extracción, seguridad y reversión simuladas")
