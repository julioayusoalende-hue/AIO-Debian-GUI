"""Instalación segura de una lista blanca de extensiones de GNOME Shell."""

import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request

INFO_URL = "https://extensions.gnome.org/extension-info/?{query}"
SHELL_BUS = "org.gnome.Shell"
SHELL_PATH = "/org/gnome/Shell"
SHELL_IFACE = "org.gnome.Shell.Extensions"

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


def shell_version():
    result = subprocess.run(
        ["gnome-shell", "--version"], capture_output=True, text=True,
        timeout=20, check=False,
    )
    match = re.search(r"([0-9]+\.[0-9]+)", result.stdout or result.stderr)
    if result.returncode or not match:
        raise RuntimeError("No se pudo determinar la versión de GNOME Shell.")
    return match.group(1)


def extension_info(task):
    """Comprueba que existe una versión compatible en el sitio oficial."""
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
    return info


def install_remote(task):
    """Usa la API oficial de GNOME Shell: descarga, confirma, instala y activa."""
    extension_info(task)
    uuid = uuid_for(task)
    result = subprocess.run(
        ["gdbus", "call", "--session", "--dest", SHELL_BUS,
         "--object-path", SHELL_PATH, "--timeout=600",
         "--method", f"{SHELL_IFACE}.InstallRemoteExtension", uuid],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=660, check=False,
    )
    success = result.returncode == 0 and "successful" in result.stdout
    if not success:
        # Algunas versiones de Shell responden tarde o la llamada expira
        # mientras el usuario confirma. El estado real manda sobre el timeout.
        try:
            success = uuid in installed()
        except RuntimeError:
            success = False
    if not success:
        if "cancelled" in result.stdout:
            raise RuntimeError("La instalación de la extensión se canceló.")
        raise RuntimeError((result.stderr or result.stdout).strip()
                           or "No se pudo instalar la extensión.")


def installed():
    result = subprocess.run(
        ["gnome-extensions", "list"], capture_output=True,
        text=True, timeout=20, check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()
                           or "No se pudo consultar las extensiones instaladas.")
    return set(result.stdout.splitlines())


def main(argv):
    if len(argv) == 2 and argv[0] == "install-remote":
        install_remote(argv[1])
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
