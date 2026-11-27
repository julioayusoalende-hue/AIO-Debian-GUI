"""Backup y restauración de la identidad de AyusOS.

Incluye fuentes APT, llavero GPG, extensiones GNOME, branding y configuración de Timeshift.
"""

import ast
import configparser
import io
import json
import re
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

AYUSOS_SOURCES = Path("/etc/apt/sources.list.d/ayusos.sources")
AYUSOS_KEYRING = Path("/usr/share/keyrings/ayusos-archive.gpg")
AYUSOS_RELEASE = Path("/etc/ayusos-release")
TIMESHIFT_CONFIG = Path("/etc/timeshift/timeshift.json")
DCONF_GNOME_EXTENSIONS = "/org/gnome/shell/enabled-extensions"
DCONF_AYUSOS_EXTENSIONS = "/org/gnome/shell/extensions/"

LIMIT = 16 * 1024 * 1024
ARCHIVE_LIMIT = LIMIT + 65536
TIMESHIFT_ENTRY = "etc/timeshift/timeshift.json"
BRANDING_KEYS = {
    "org.gnome.desktop.interface.gtk-theme",
    "org.gnome.desktop.interface.color-scheme",
    "org.gnome.desktop.interface.accent-color",
    "org.gnome.desktop.background.picture-uri",
    "org.gnome.desktop.background.picture-uri-dark",
}
TIMESHIFT_FLAGS = {
    "btrfs_mode", "include_btrfs_home_for_backup", "include_btrfs_home_for_restore",
    *(f"schedule_{period}" for period in ("boot", "hourly", "daily", "weekly", "monthly")),
}
TIMESHIFT_COUNTS = {f"count_{period}" for period in ("boot", "hourly", "daily", "weekly", "monthly")}


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

    try:
        files[TIMESHIFT_ENTRY] = (TIMESHIFT_CONFIG.read_bytes(), 0)
    except FileNotFoundError:
        pass
    except PermissionError:
        # El perfil de usuario puede respaldarse aunque Timeshift sea privado.
        pass

    try:
        out = _run(["dconf", "read", DCONF_GNOME_EXTENSIONS])
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
    branding_data = {}
    for entry in sorted(BRANDING_KEYS):
        schema, key = entry.rsplit(".", 1)
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


def read_identity(data: bytes) -> dict[str, tuple[bytes, int]]:
    """Lee un archivo de backup de identidad."""
    if len(data) > ARCHIVE_LIMIT:
        raise ValueError("El respaldo supera el tamaño máximo.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if sum(entry.file_size for entry in entries) > LIMIT + 4096:
            raise ValueError("Identity backup oversized")
        if len({entry.filename for entry in entries}) != len(entries):
            raise ValueError("El respaldo contiene entradas duplicadas.")
        manifest = archive.getinfo("manifest.json")
        meta = json.loads(archive.read(manifest))
        if not isinstance(meta, dict) or meta.get("type") != "ayusos-identity" or meta.get("format") != 1:
            raise ValueError("Not an AyusOS identity backup")
        files = {}
        for entry in entries:
            if entry is manifest:
                continue
            mode = entry.external_attr >> 16
            files[entry.filename] = (archive.read(entry), mode & 0o100)
        return files


def read_archive(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(ARCHIVE_LIMIT + 1)
    if len(data) > ARCHIVE_LIMIT:
        raise ValueError("El respaldo supera el tamaño máximo.")
    return data


def validate_identity(files):
    protected = {
        "apt/ayusos.sources": AYUSOS_SOURCES,
        "apt/ayusos-archive.gpg": AYUSOS_KEYRING,
        "etc/ayusos-release": AYUSOS_RELEASE,
    }
    for name, (data, _) in files.items():
        if name in protected:
            try:
                matches = protected[name].read_bytes() == data
            except FileNotFoundError:
                matches = False
            if not matches:
                raise ValueError("El respaldo difiere de los archivos oficiales instalados. Reinstala el paquete oficial para recuperarlos.")
        elif name == TIMESHIFT_ENTRY:
            settings = json.loads(data)
            if not isinstance(settings, dict):
                raise ValueError("Configuración de Timeshift no válida.")
            uuid = settings.get("backup_device_uuid")
            if uuid is not None and (not isinstance(uuid, str) or not re.fullmatch(r"[a-fA-F0-9-]{1,64}", uuid)):
                raise ValueError("UUID de Timeshift no válido.")
            for key, value in settings.items():
                if key in TIMESHIFT_FLAGS and str(value).lower() not in {"true", "false"}:
                    raise ValueError(f"Opción de Timeshift no válida: {key}")
                if key in TIMESHIFT_COUNTS and not re.fullmatch(r"[0-9]{1,4}", str(value)):
                    raise ValueError(f"Retención de Timeshift no válida: {key}")
        elif name == "dconf/enabled-extensions":
            text = data.decode().strip()
            extensions = [] if text == "@as []" else ast.literal_eval(text)
            if not isinstance(extensions, list) or not all(isinstance(item, str) for item in extensions):
                raise ValueError("Lista de extensiones de GNOME no válida.")
        elif name == "dconf/extensions":
            configparser.RawConfigParser(interpolation=None).read_string(data.decode())
        elif name == "dconf/branding.json":
            branding = json.loads(data)
            if not isinstance(branding, dict) or not all(
                key in BRANDING_KEYS and isinstance(value, str) for key, value in branding.items()
            ):
                raise ValueError("Preferencias de apariencia no válidas.")
        else:
            raise ValueError(f"Entrada desconocida: {name}")


def restore_system_identity(files):
    """Comprueba las bases de confianza y actualiza la configuración atómicamente."""
    validate_identity(files)
    if TIMESHIFT_ENTRY not in files:
        return
    if os.geteuid() != 0:
        raise PermissionError("Se necesita autorización para restaurar Timeshift.")
    saved = json.loads(files[TIMESHIFT_ENTRY][0])
    try:
        current = json.loads(TIMESHIFT_CONFIG.read_bytes())
    except FileNotFoundError:
        current = {}
    if not isinstance(current, dict):
        raise ValueError("La configuración actual de Timeshift no es válida.")
    keys = TIMESHIFT_FLAGS | TIMESHIFT_COUNTS | {"backup_device_uuid"}
    current.update({key: saved[key] for key in keys & saved.keys()})
    TIMESHIFT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=TIMESHIFT_CONFIG.parent,
                                     prefix=".timeshift-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(current, stream, indent=2)
            stream.write("\n")
            stream.close()
            temporary.replace(TIMESHIFT_CONFIG)
        finally:
            temporary.unlink(missing_ok=True)


def restore_user_identity(files):
    """Aplica las preferencias GNOME en el bus de la sesión solicitante."""
    if os.geteuid() == 0:
        raise PermissionError("Las preferencias de GNOME requieren una sesión de usuario.")
    if "dconf/enabled-extensions" in files:
        value = files["dconf/enabled-extensions"][0].decode().strip()
        _run(["dconf", "write", DCONF_GNOME_EXTENSIONS, value])
    if "dconf/extensions" in files:
        _run(["dconf", "load", DCONF_AYUSOS_EXTENSIONS], data=files["dconf/extensions"][0])
    if "dconf/branding.json" in files:
        for key, value in json.loads(files["dconf/branding.json"][0]).items():
            schema, setting = key.rsplit(".", 1)
            _run(["gsettings", "set", schema, setting, value])


def restore_identity(files, dry_run=False):
    validate_identity(files)
    if not dry_run:
        if os.geteuid() == 0:
            restore_system_identity(files)
        else:
            if TIMESHIFT_ENTRY in files:
                raise PermissionError("Restaura Timeshift desde el Centro de Control para solicitar autorización.")
            restore_user_identity(files)
    return True, "Respaldo válido." if dry_run else "Identidad restaurada correctamente."


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
    files = read_identity(read_archive(path))
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
