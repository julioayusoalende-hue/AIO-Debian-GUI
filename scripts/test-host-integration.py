#!/usr/bin/env python3
"""Prueba la guía sin ejecutar operaciones privilegiadas reales."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

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

print("✔ Guía de integración: comandos separados, bloqueo DEB y autorización explícita")
