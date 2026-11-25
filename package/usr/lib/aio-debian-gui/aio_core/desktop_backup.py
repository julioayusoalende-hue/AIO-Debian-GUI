"""Backup and restore user-owned GNOME and Plasma settings."""
import json
import os
import stat
import subprocess
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

LABELS = {"gnome": "GNOME", "plasma": "KDE Plasma"}
COMMANDS = {"gnome": "gnome-shell", "plasma": "plasmashell"}
DCONF = {
    "desktop": "/org/gnome/desktop/",
    "shell": "/org/gnome/shell/",
    "mutter": "/org/gnome/mutter/",
    "media-keys": "/org/gnome/settings-daemon/plugins/media-keys/",
    "desktop-icons": "/org/gnome/nautilus/desktop/",
}
PLASMA_CONFIG = (
    "plasma-org.kde.plasma.desktop-appletsrc", "plasmashellrc", "plasmarc",
    "kdeglobals", "kwinrc", "kwinrulesrc", "kglobalshortcutsrc", "khotkeysrc",
)
LOCAL_ADDONS = {"gnome": "gnome-shell/extensions", "plasma": "plasma/plasmoids"}
SHELL_SERVICE = "plasma-plasmashell.service"
LIMIT = 64 * 1024 * 1024
FILE_LIMIT = 8192


def detect(session=None):
    names = set((session if session is not None else
                 os.environ.get("XDG_CURRENT_DESKTOP", "")).lower().split(":"))
    if names & {"kde", "plasma"}:
        return "plasma"
    if "gnome" in names:
        return "gnome"
    return None


def run(*args, data=None):
    command = (("flatpak-spawn", "--host") + args if os.environ.get("FLATPAK_ID") else args)
    result = subprocess.run(command, input=data, capture_output=True, timeout=25)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip()
                           or f"{args[0]} exited with status {result.returncode}")
    return result.stdout


def version(desktop):
    return run(COMMANDS[desktop], "--version").decode(errors="replace").strip()


def user_dirs():
    home = Path.home()
    if os.environ.get("FLATPAK_ID"):
        values = run("printenv", "HOME").decode().strip()
        home = Path(values)
        # User files are accessed through the sandbox's existing permissions.
        return {"config": home / ".config", "data": home / ".local/share",
                "state": home / ".local/state"}
    return {kind: Path(os.environ.get(f"XDG_{kind.upper()}_HOME") or home / default)
            for kind, default in (("config", ".config"), ("data", ".local/share"),
                                  ("state", ".local/state"))}


def allowed(desktop, name):
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts) or "\\" in name or "\0" in name:
        return False
    if desktop == "gnome" and len(parts) == 2:
        return parts[0] == "settings" and parts[1] in DCONF
    if desktop == "plasma" and len(parts) == 2:
        return parts[0] == "config" and parts[1] in PLASMA_CONFIG
    return name.startswith("data/" + LOCAL_ADDONS[desktop] + "/") and len(parts) >= 5


def file_path(name, dirs):
    kind, *parts = name.split("/")
    path = dirs[kind]
    for part in parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f"Symbolic link: {path}")
    return path


def snapshot(desktop, dirs):
    files = {}
    if desktop == "gnome":
        for key, path in DCONF.items():
            files[f"settings/{key}"] = (run("dconf", "dump", path), 0)
    else:
        for name in PLASMA_CONFIG:
            path = file_path(f"config/{name}", dirs)
            if path.is_file():
                files[f"config/{name}"] = (path.read_bytes(), 0)
    prefix = "data/" + LOCAL_ADDONS[desktop]
    addons = file_path(prefix, dirs)
    size = sum(len(data) for data, _ in files.values())
    for root, directories, names in os.walk(addons, followlinks=False):
        directories[:] = [name for name in sorted(directories)
                          if not (Path(root) / name).is_symlink()]
        for name in sorted(names):
            path = Path(root) / name
            mode = path.lstat().st_mode
            key = "data/" + path.relative_to(dirs["data"]).as_posix()
            if stat.S_ISREG(mode) and allowed(desktop, key):
                with path.open("rb") as stream:
                    data = stream.read(max(0, LIMIT - size) + 1)
                files[key] = (data, mode & 0o100)
                size += len(data)
                if size > LIMIT or len(files) > FILE_LIMIT:
                    raise ValueError("Desktop backup exceeds its size limit")
    return files


def save(path, desktop, release, files):
    if sum(len(data) for data, _ in files.values()) > LIMIT or len(files) > FILE_LIMIT:
        raise ValueError("Desktop backup exceeds its size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".desktop-backup-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps({
                "format": 1, "desktop": desktop, "version": release,
            }))
            for key, (data, mode) in sorted(files.items()):
                info = zipfile.ZipInfo(key)
                info.external_attr = (stat.S_IFREG | 0o600 | mode) << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read(path, desktop):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if (len(entries) > FILE_LIMIT + 1 or sum(entry.file_size for entry in entries) > LIMIT + 4096
                or len({entry.filename for entry in entries}) != len(entries)):
            raise ValueError("Invalid or oversized desktop backup")
        manifest = archive.getinfo("manifest.json")
        if manifest.file_size > 4096:
            raise ValueError("Invalid desktop backup manifest")
        meta = json.loads(archive.read(manifest))
        if (not isinstance(meta, dict) or meta.get("format") != 1 or meta.get("desktop") != desktop
                or not isinstance(meta.get("version"), str) or not meta["version"].strip()):
            raise ValueError("The backup format or desktop does not match this session")
        files = {}
        for entry in entries:
            if entry is manifest:
                continue
            mode = entry.external_attr >> 16
            if not allowed(desktop, entry.filename) or not stat.S_ISREG(mode):
                raise ValueError(f"Unexpected backup entry: {entry.filename!r}")
            files[entry.filename] = (archive.read(entry), mode & 0o100)
        return meta["version"], files


def write_file(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".desktop-restore-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), 0o600 | mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def pause_plasma(desktop):
    if desktop == "plasma":
        run("systemctl", "--user", "stop", SHELL_SERVICE)
    try:
        yield
    finally:
        if desktop == "plasma":
            run("systemctl", "--user", "start", SHELL_SERVICE)


def restore(desktop, release, files, dirs):
    # Resolve destinations before changing either files or settings.
    targets = {name: file_path(name, dirs) for name in files if not name.startswith("settings/")}
    with pause_plasma(desktop):
        before = snapshot(desktop, dirs)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        recovery = dirs["state"] / "aio-debian-gui" / "desktop-backups" / f"{desktop}-{stamp}.zip"
        save(recovery, desktop, release, before)
        changed = []
        try:
            # Install add-ons before applying settings that can enable them.
            for name in sorted(files):
                data, mode = files[name]
                changed.append(name)
                if name in targets:
                    write_file(targets[name], data, mode)
                else:
                    run("dconf", "load", DCONF[name.split("/")[1]], data=data)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            failed = []
            for name in reversed(changed):
                try:
                    if name in targets:
                        if name in before:
                            write_file(targets[name], *before[name])
                        else:
                            targets[name].unlink(missing_ok=True)
                    else:
                        path = DCONF[name.split("/")[1]]
                        run("dconf", "reset", "-f", path)
                        run("dconf", "load", path, data=before[name][0])
                except (OSError, RuntimeError, subprocess.SubprocessError):
                    failed.append(name)
            if failed:
                raise RuntimeError(f"{error}\nRollback incomplete. {recovery}") from error
            raise
    return recovery
