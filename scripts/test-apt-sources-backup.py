#!/usr/bin/env python3
"""Round trip and failure recovery against a temporary APT directory."""
from importlib.machinery import SourceFileLoader
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

path = Path("package/usr/lib/aio-debian-gui/aio-apt-sources-backup")
loader = SourceFileLoader("apt_backup", str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
backup = importlib.util.module_from_spec(spec)
loader.exec_module(backup)

with tempfile.TemporaryDirectory() as tmp:
    apt = Path(tmp)
    original = {
        "sources.list": (b"deb https://example.org/debian stable main\n", 0o644),
        "sources.list.d/local.sources": (b"Types: deb\n", 0o600),
        "keyrings/local.gpg": (b"\x00\x80\xff", 0o644),
    }
    for name, entry in original.items():
        backup.replace_file(apt / name, entry)
    copy = backup.decode(backup.encode(backup.snapshot(apt)))
    assert copy == original

    (apt / "sources.list").unlink()
    backup.replace_file(apt / "sources.list.d/after.list", (b"# newly added", 0o644))
    backup.replace_file(apt / "trusted.gpg.d/after.gpg", (b"new key", 0o644))
    replace_file = backup.replace_file

    def fail_on_source(path, entry):
        if path.name == "local.sources":
            raise OSError("simulated write failure")
        replace_file(path, entry)

    (apt / "sources.list.d/local.sources").unlink()
    before = backup.snapshot(apt)
    with patch.object(backup, "replace_file", fail_on_source):
        try:
            backup.restore(apt, copy)
        except OSError:
            pass
        else:
            raise AssertionError("Restore silently accepted a write failure")
    assert backup.snapshot(apt) == before

    backup.restore(apt, copy)
    assert backup.snapshot(apt) == {
        **original, "trusted.gpg.d/after.gpg": (b"new key", 0o644),
    }

    for name in ("../sources.list", "sources.list.d/../../passwd", "apt.conf.d/hook"):
        invalid = json.dumps({"version": 1, "files": {name: ["", 0o644]}}).encode()
        try:
            backup.decode(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted unsupported backup file {name}")

    source = apt / "sources.list"
    source.unlink()
    source.symlink_to(apt / "sources.list.d/local.sources")
    try:
        backup.restore(apt, copy)
    except ValueError:
        pass
    else:
        raise AssertionError("Accepted a symlink in the system APT sources")
    assert source.is_symlink()
