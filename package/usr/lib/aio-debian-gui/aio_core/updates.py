"""Lógica de versiones y AppImage sin dependencias de GTK ni Polkit."""
import hashlib
import json
import os
import re
import tempfile
import urllib.request

HOMEPAGE = "https://github.com/julioayusoalende-hue/AIO-Debian-GUI"
RELEASE_API = "https://api.github.com/repos/julioayusoalende-hue/AIO-Debian-GUI/releases/latest"
MAX_APPIMAGE_SIZE = 256 * 1024 * 1024

def version_numerica(version):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    return tuple(map(int, match.groups())) if match else None


def obtener_release_actualizacion():
    request = urllib.request.Request(
        RELEASE_API, headers={"User-Agent": "aio-debian-gui-updater", "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(request, timeout=15) as respuesta:
        if respuesta.status != 200:
            raise RuntimeError("No se pudo consultar GitHub Releases.")
        datos = json.load(respuesta)
    version = str(datos.get("tag_name", "")).lstrip("v")
    if not version_numerica(version):
        raise RuntimeError("La versión de GitHub no tiene un formato válido.")
    archivos = {a.get("name"): a.get("browser_download_url") for a in datos.get("assets", [])}
    nombre = f"aio-debian-gui_{version}_x86_64.AppImage"
    url = archivos.get(nombre)
    url_hash = archivos.get("SHA256SUMS")
    if not (url and url_hash and url.startswith(HOMEPAGE + "/releases/download/") and
            url_hash.startswith(HOMEPAGE + "/releases/download/")):
        raise RuntimeError("La Release no contiene un AppImage y SHA256SUMS válidos.")
    return version, nombre, url, url_hash


def descargar_appimage_verificado(version, nombre, url, url_hash, directorio_descargas=None):
    with urllib.request.urlopen(
        urllib.request.Request(url_hash, headers={"User-Agent": "aio-debian-gui-updater"}), timeout=20
    ) as respuesta:
        checksums = respuesta.read(65536).decode("utf-8")
    esperada = None
    for linea in checksums.splitlines():
        partes = linea.split()
        if len(partes) == 2 and partes[1].lstrip("*") == nombre and re.fullmatch(r"[0-9a-fA-F]{64}", partes[0]):
            esperada = partes[0].lower()
    if not esperada:
        raise RuntimeError("No existe una suma SHA-256 verificable para el AppImage.")
    destino = os.path.join(directorio_descargas or os.path.expanduser("~/Downloads"), nombre)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    # Descarga a archivo temporal privado y renombrado atómico; nunca reemplaza el AppImage activo.
    fd, temporal = tempfile.mkstemp(prefix=".aio-debian-gui-", suffix=".part", dir=os.path.dirname(destino))
    try:
        resumen = hashlib.sha256()
        acumulado = 0
        with os.fdopen(fd, "wb") as archivo:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "aio-debian-gui-updater"}), timeout=45
            ) as respuesta:
                while True:
                    bloque = respuesta.read(1024 * 1024)
                    if not bloque:
                        break
                    acumulado += len(bloque)
                    if acumulado > MAX_APPIMAGE_SIZE:
                        raise RuntimeError("El AppImage excede el tamaño máximo permitido.")
                    resumen.update(bloque)
                    archivo.write(bloque)
        if resumen.hexdigest() != esperada:
            raise RuntimeError("La suma SHA-256 no coincide: se ha descartado la descarga.")
        os.chmod(temporal, 0o755)
        os.replace(temporal, destino)
        return destino
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


