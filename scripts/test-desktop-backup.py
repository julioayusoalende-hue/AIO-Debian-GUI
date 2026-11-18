#!/usr/bin/env python3
"""Round-trip tests without an active desktop session."""
import os
from pathlib import Path
import stat
import sys
import tempfile
from unittest.mock import patch
import zipfile

sys.path.insert(0, os.path.abspath("package/usr/lib/aio-debian-gui"))
from aio_core import desktop_backup as backup

assert backup.detect("ubuntu:GNOME") == "gnome"
assert backup.detect("KDE") == "plasma"
assert backup.detect("X-Cinnamon") is None

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    dirs = {kind: root / kind for kind in ("data", "config", "state")}
    key = "data/gnome-shell/extensions/sample@example.org/extension.js"
    extension = backup.file_path(key, dirs)
    backup.write_file(extension, b"old", 0o100)
    with patch.object(backup, "run", return_value=b"[/]\nkey=true\n") as run:
        files = backup.snapshot("gnome", dirs)
        assert files[key] == (b"old", 0o100)
        path = root / "gnome.zip"
        backup.save(path, "gnome", "GNOME Shell 48", files)
        assert backup.read(path, "gnome") == ("GNOME Shell 48", files)
        try:
            backup.read(path, "plasma")
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted a backup of a different desktop")
        backup.write_file(extension, b"new", 0)
        recovery = backup.restore("gnome", "GNOME Shell 48", files, dirs)
        assert backup.read(recovery, "gnome")[1][key] == (b"new", 0)
        assert extension.read_bytes() == b"old"
        assert extension.stat().st_mode & stat.S_IXUSR
        run.assert_any_call("dconf", "load", "/org/gnome/shell/", data=b"[/]\nkey=true\n")

    panel = "config/plasma-org.kde.plasma.desktop-appletsrc"
    path = backup.file_path(panel, dirs)
    backup.write_file(path, b"old-panel", 0)
    files = backup.snapshot("plasma", dirs)
    backup.write_file(path, b"new-panel", 0)
    with patch.object(backup, "run") as run:
        recovery = backup.restore("plasma", "plasmashell 6", files, dirs)
        assert run.call_args_list[0].args == ("systemctl", "--user", "stop", backup.SHELL_SERVICE)
        assert run.call_args_list[-1].args == ("systemctl", "--user", "start", backup.SHELL_SERVICE)
        assert backup.read(recovery, "plasma")[1][panel] == (b"new-panel", 0)
        assert path.read_bytes() == b"old-panel"

    path = root / "invalid.zip"
    backup.save(path, "plasma", "plasmashell 6", {"config/../../escape": (b"bad", 0)})
    try:
        backup.read(path, "plasma")
    except ValueError:
        pass
    else:
        raise AssertionError("Accepted an out-of-scope archive member")
    assert zipfile.is_zipfile(path)
