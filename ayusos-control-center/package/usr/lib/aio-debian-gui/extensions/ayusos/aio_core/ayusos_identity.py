"""Backup y restauración de la identidad de AyusOS.

Incluye fuentes APT, llavero GPG, extensiones GNOME, branding y configuración de Timeshift.
"""

import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

AYUSOS_SOURCES = Path("/etc/apt/sources.list.d/ayusos.sources")
AYUSOS_KEYRING = Path("/usr/share/keyrings/ayusos-archive.gpg")
AYUSOS_RELEASE = Path("/etc/ayusos-release")
TIMESHIFT_CONFIG = Path("/etc/timeshift.json")
TIMESHIFT_DEFAULT = Path("/etc/timeshift/default.json")
DCONF_GNOME_EXTENSIONS = "/org/gnome/shell/enabled-extensions"
DCONF_AYUSOS_EXTENSIONS = "/org/gnome/shell/extensions/"

LIMIT = 16 * 1024 * 1024  # 16 MB para identidad


def _run(cmd, capture=True, data=None):
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    result = subprocess.run(cmd, capture_output=capture, text=True, timeout=30, input=data)
    if result.returncode != 0:
        err = (result.stderr or "").strip() if capture else ""
        raise RuntimeError(f"{cmd[0]} falló: {err}")
    return result.stdout if capture else ""


def snapshot_identity() -> dict[str, tuple[bytes, int]]:
    """Captura el estado actual de la identidad de AyusOS."""
    files = {}

    # Fuentes APT de AyusOS
    if AYUSOS_SOURCES.exists():
        files["apt/ayusos.sources"] = (AYUSOS_SOURCES.read_bytes(), 0)

    # Llavero GPG
    if AYUSOS_KEYRING.exists():
        files["apt/ayusos-archive.gpg"] = (AYUSOS_KEYRING.read_bytes(), 0)

    # Archivo de versión de AyusOS
    if AYUSOS_RELEASE.exists():
        files["etc/ayusos-release"] = (AYUSOS_RELEASE.read_bytes(), 0)

    # Configuración de Timeshift
    for path in [TIMESHIFT_CONFIG, TIMESHIFT_DEFAULT]:
        if path.exists():
            files[f"etc/timeshift/{path.name}"] = (path.read_bytes(), 0)

    # Extensiones GNOME habilitadas (dconf)
    try:
        out = _run(["dconf", "dump", DCONF_GNOME_EXTENSIONS])
        if out.strip():
            files["dconf/enabled-extensions"] = (out.encode(), 0)
    except RuntimeError:
        pass

    # Configuración de extensiones GNOME (ayusos)
    try:
        out = _run(["dconf", "dump", DCONF_AYUSOS_EXTENSIONS])
        if out.strip():
            files["dconf/extensions"] = (out.encode(), 0)
    except RuntimeError:
        pass

    # Branding (tema, acento, wallpaper) - desde gsettings/dconf
    branding_keys = [
        ("org.gnome.desktop.interface", "gtk-theme"),
        ("org.gnome.desktop.interface", "color-scheme"),
        ("org.gnome.desktop.interface", "accent-color"),
        ("org.gnome.desktop.background", "picture-uri"),
        ("org.gnome.desktop.background", "picture-uri-dark"),
    ]
    branding_data = {}
    for schema, key in branding_keys:
        try:
            out = _run(["gsettings", "get", schema, key])
            if out.strip() and out.strip() != "@as []":
                branding_data[f"{schema}.{key}"] = out.strip()
        except RuntimeError:
            pass
    if branding_data:
        files["dconf/branding.json"] = (json.dumps(branding_data, indent=2).encode(), 0)

    return files


def save_identity(path: Path, files: dict[str, tuple[bytes, int]]) -> None:
    """Guarda el snapshot de identidad en un archivo ZIP."""
    if sum(len(data) for data, _ in files.values()) > LIMIT:
        raise ValueError("Identity backup exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".ayusos-identity-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps({"format": 1, "type": "ayusos-identity"}))
            for key, (data, mode) in sorted(files.items()):
                info = zipfile.ZipInfo(key)
                info.external_attr = (0o600 | mode) << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_identity(path: Path) -> dict[str, tuple[bytes, int]]:
    """Lee un archivo de backup de identidad."""
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if sum(entry.file_size for entry in entries) > LIMIT + 4096:
            raise ValueError("Identity backup oversized")
        manifest = archive.getinfo("manifest.json")
        meta = json.loads(archive.read(manifest))
        if meta.get("type") != "ayusos-identity":
            raise ValueError("Not an AyusOS identity backup")
        files = {}
        for entry in entries:
            if entry is manifest:
                continue
            mode = entry.external_attr >> 16
            files[entry.filename] = (archive.read(entry), mode & 0o100)
        return files


def restore_identity(files: dict[str, tuple[bytes, int]], dry_run: bool = False) -> tuple[bool, str]:
    """Restaura la identidad de AyusOS desde un backup."""
    errors = []
    restored = []

    for name, (data, _mode) in files.items():
        try:
            if name == "apt/ayusos.sources":
                if not dry_run:
                    AYUSOS_SOURCES.parent.mkdir(parents=True, exist_ok=True)
                    AYUSOS_SOURCES.write_bytes(data)
                restored.append("Fuentes APT de AyusOS")
            elif name == "apt/ayusos-archive.gpg":
                if not dry_run:
                    AYUSOS_KEYRING.parent.mkdir(parents=True, exist_ok=True)
                    AYUSOS_KEYRING.write_bytes(data)
                restored.append("Llavero GPG de AyusOS")
            elif name == "etc/ayusos-release":
                if not dry_run:
                    AYUSOS_RELEASE.write_bytes(data)
                restored.append("Archivo de versión AyusOS")
            elif name.startswith("etc/timeshift/"):
                target = TIMESHIFT_CONFIG if name.endswith("timeshift.json") else TIMESHIFT_DEFAULT
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                restored.append(f"Configuración Timeshift ({target.name})")
            elif name == "dconf/enabled-extensions":
                if not dry_run:
                    _run(["dconf", "load", DCONF_GNOME_EXTENSIONS], capture=False, data=data.encode())
                restored.append("Extensiones GNOME habilitadas")
            elif name == "dconf/extensions":
                if not dry_run:
                    _run(["dconf", "load", DCONF_AYUSOS_EXTENSIONS], capture=False, data=data.encode())
                restored.append("Configuración de extensiones GNOME")
            elif name == "dconf/branding.json":
                if not dry_run:
                    branding = json.loads(data.decode())
                    for key, value in branding.items():
                        schema, gkey = key.rsplit(".", 1)
                        _run(["gsettings", "set", schema, gkey, value], capture=False)
                restored.append("Branding (tema, acento, wallpaper)")
            else:
                errors.append(f"Entrada desconocida: {name}")
        except (RuntimeError, OSError, json.JSONDecodeError) as e:
            errors.append(f"{name}: {e}")

    if errors:
        return False, f"Errores: {'; '.join(errors)}"
    return True, f"Restaurado: {', '.join(restored)}"


def cli_snapshot() -> str:
    import json
    files = snapshot_identity()
    return json.dumps({k: len(v[0]) for k, v in files.items()})


def cli_backup(output: str) -> str:
    import json
    path = Path(output).expanduser()
    files = snapshot_identity()
    save_identity(path, files)
    return json.dumps({"success": True, "path": str(path), "items": list(files.keys())})


def cli_restore(input_path: str, dry_run: bool = False) -> str:
    import json
    path = Path(input_path).expanduser()
    files = read_identity(path)
    ok, msg = restore_identity(files, dry_run)
    return json.dumps({"success": ok, "message": msg})


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: ayusos_identity.py snapshot|backup <output>|restore <input> [--dry-run]", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "snapshot":
        print(cli_snapshot())
    elif cmd == "backup":
        if len(sys.argv) < 3:
            print("Falta ruta de salida", file=sys.stderr)
            sys.exit(1)
        print(cli_backup(sys.argv[2]))
    elif cmd == "restore":
        if len(sys.argv) < 3:
            print("Falta archivo de entrada", file=sys.stderr)
            sys.exit(1)
        dry = "--dry-run" in sys.argv
        print(cli_restore(sys.argv[2], dry))
    else:
        print(f"Comando desconocido: {cmd}", file=sys.stderr)
        sys.exit(1)
