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

# Tope único: lo que la copia admite al leer es lo que admite al escribir.
LIMIT = 1024 * 1024
assert backup.size_limit() == backup.LIMIT
with tempfile.TemporaryDirectory() as tmp, \
        patch.object(backup, "LIMIT", LIMIT):
    assert backup.size_limit() == LIMIT
    apt = Path(tmp)
    (apt / "keyrings").mkdir()

    def fill(name, size):
        (apt / name).write_bytes(b"K" * size)

    # Un fichero que cabe justo en el tope no se rechaza al leer.
    fill("keyrings/justo.gpg", LIMIT - 2)
    assert backup.size_limit() == LIMIT
    backup.snapshot(apt)

    # Un byte de más se rechaza ya al leer, no más tarde al codificar.
    fill("keyrings/pasado.gpg", LIMIT - 1)
    try:
        backup.snapshot(apt)
    except ValueError as error:
        assert "size limit" in str(error), error
    else:
        raise AssertionError("Un fichero por encima del tope se aceptó al leer")

    # Varios ficheros que juntos se pasan tampoco entran.
    (apt / "keyrings/justo.gpg").unlink()
    fill("keyrings/a.gpg", LIMIT // 2 + 10)
    fill("keyrings/b.gpg", LIMIT // 2 + 10)
    try:
        backup.snapshot(apt)
    except ValueError as error:
        assert "size limit" in str(error), error
    else:
        raise AssertionError("Varios ficheros por encima del tope se aceptaron")

    # Ida y vuelta completa por el tope real del proyecto, con el fichero
    # grande pero dentro de límite.
    (apt / "keyrings/b.gpg").unlink()
    (apt / "keyrings/a.gpg").unlink()
    (apt / "keyrings/pasado.gpg").unlink()
    fill("sources.list", 1024)
    encoded = backup.encode(backup.snapshot(apt))
    assert len(encoded) <= backup.size_limit()
    restored, mode = backup.decode(encoded)["sources.list"]
    assert restored == b"K" * 1024
    assert mode == (apt / "sources.list").stat().st_mode & 0o777
    # Lo que se pasa del tope se rechaza al decodificar.
    for value in (b"{" + b" " * backup.size_limit(),
                  b" " * (backup.size_limit() + 1)):
        try:
            backup.decode(value)
        except ValueError:
            pass
        else:
            raise AssertionError("El decodificador aceptó más que el tope")

# El fichero grande (20 MiB) ya no se rechaza: cabía en el tope pero antes se
# cortaba en la mitad al leer.
with tempfile.TemporaryDirectory() as tmp:
    apt = Path(tmp)
    (apt / "keyrings").mkdir()
    (apt / "keyrings/grande.gpg").write_bytes(b"G" * (20 * 1024 * 1024))
    assert len(backup.snapshot(apt)["keyrings/grande.gpg"][0]) == 20 * 1024 * 1024
    (apt / "keyrings/justo.gpg").write_bytes(
        b"J" * (backup.size_limit() - 20 * 1024 * 1024))
    backup.snapshot(apt)
    (apt / "keyrings/pasado.gpg").write_bytes(b"P")
    try:
        backup.snapshot(apt)
    except ValueError as error:
        assert "size limit" in str(error), error
    else:
        raise AssertionError("El tope real del proyecto no se aplicó")
