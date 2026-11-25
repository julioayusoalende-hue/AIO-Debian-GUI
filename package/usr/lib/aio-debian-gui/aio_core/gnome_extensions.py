"""Instalación segura de una lista blanca de extensiones de GNOME Shell."""

import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

INFO_URL = "https://extensions.gnome.org/extension-info/?{query}"
MAX_BYTES = 25 * 1024 * 1024
MAX_UNPACKED_BYTES = 50 * 1024 * 1024
MAX_FILES = 5000

EXTENSIONS = {
    "gnome-ext-appindicator": "appindicatorsupport@rgcjonas.gmail.com",
    "gnome-ext-blur-shell": "blur-my-shell@aunetx",
    "gnome-ext-caffeine": "caffeine@patapon.info",
    "gnome-ext-clipboard-indicator": "clipboard-indicator@tudmotu.com",
    "gnome-ext-dash-to-dock": "dash-to-dock@micxgx.gmail.com",
    "gnome-ext-places-status": "places-menu@gnome-shell-extensions.gcampax.github.com",
    "gnome-ext-tiling-shell": "tilingshell@ferrarodomenico.com",
}


def uuid_for(task):
    try:
        return EXTENSIONS[task]
    except KeyError as exc:
        raise ValueError("Extensión de GNOME no permitida.") from exc


def validate(task, bundle):
    """Comprueba integridad, metadata y UUID antes de instalar."""
    uuid = uuid_for(task)
    with zipfile.ZipFile(bundle) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES or sum(entry.file_size for entry in entries) > MAX_UNPACKED_BYTES:
            raise ValueError("El paquete de extensión supera los límites de tamaño.")
        for entry in entries:
            parts = entry.filename.replace("\\", "/").split("/")
            if entry.filename.startswith("/") or ".." in parts:
                raise ValueError("El paquete contiene rutas no seguras.")
        damaged = archive.testzip()
        if damaged:
            raise ValueError("El paquete de extensión está dañado.")
        names = archive.namelist()
        metadata_path = "metadata.json"
        if metadata_path not in names:
            candidates = [name for name in names
                          if name.count("/") == 1 and name.endswith("/metadata.json")]
            if len(candidates) != 1:
                raise ValueError("El paquete no contiene metadata.json.")
            metadata_path = candidates[0]
        try:
            metadata = json.loads(archive.read(metadata_path))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("metadata.json no es válido.") from exc
        if not isinstance(metadata, dict) or metadata.get("uuid") != uuid:
            raise ValueError("El UUID de la extensión no coincide.")


def shell_version():
    result = subprocess.run(
        ["gnome-shell", "--version"], capture_output=True, text=True,
        timeout=20, check=False,
    )
    match = re.search(r"([0-9]+\.[0-9]+)", result.stdout or result.stderr)
    if result.returncode or not match:
        raise RuntimeError("No se pudo determinar la versión de GNOME Shell.")
    return match.group(1)


def download_url(task):
    """Consulta una versión compatible y valida el origen de la descarga."""
    uuid = uuid_for(task)
    query = urllib.parse.urlencode({"uuid": uuid, "shell_version": shell_version()})
    request = urllib.request.Request(
        INFO_URL.format(query=query), headers={"User-Agent": "aio-debian-gui"})
    with urllib.request.urlopen(request, timeout=30) as response:
        info = json.load(response)
    if not isinstance(info, dict) or info.get("uuid") != uuid or not info.get("download_url"):
        raise ValueError("No hay una versión compatible de la extensión.")
    url = urllib.parse.urljoin("https://extensions.gnome.org", info["download_url"])
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "extensions.gnome.org":
        raise ValueError("El origen de la extensión no es seguro.")
    return url


def download(task, output):
    """Descarga un UUID permitido y valida el paquete resultante."""
    url = download_url(task)
    request = urllib.request.Request(url, headers={"User-Agent": "aio-debian-gui"})
    output = Path(output)
    total = 0
    with urllib.request.urlopen(request, timeout=60) as response, output.open("wb") as target:
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > MAX_BYTES:
                raise ValueError("La extensión supera el límite de tamaño.")
            target.write(block)
    validate(task, output)


def installed():
    result = subprocess.run(
        ["gnome-extensions", "list", "--user"], capture_output=True,
        text=True, timeout=20, check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()
                           or "No se pudo consultar las extensiones instaladas.")
    return set(result.stdout.splitlines())


def install(task, bundle):
    validate(task, bundle)
    subprocess.run(
        ["gnome-extensions", "install", "--force", str(bundle)],
        stdin=subprocess.DEVNULL, timeout=120, check=True,
    )


def main(argv):
    if len(argv) == 3 and argv[0] == "download":
        download(argv[1], argv[2])
    elif len(argv) == 3 and argv[0] == "validate":
        validate(argv[1], argv[2])
    elif len(argv) == 3 and argv[0] == "install":
        install(argv[1], argv[2])
    elif argv == ["list"]:
        for uuid in sorted(installed()):
            print(uuid)
    else:
        raise ValueError("Operación no válida.")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
