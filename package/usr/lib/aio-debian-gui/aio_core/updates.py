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




def estado_actualizacion_app(formato, version_instalada, app_id):
    """Consulta solo la disponibilidad; no instala ni actualiza índices.

    El formato determina la fuente efectiva. APT y Flatpak consultan sus
    repositorios configurados (posiblemente con caché antigua). AppImage
    consulta la última publicación verificada en GitHub.
    """
    import subprocess

    def resultado(estado, detalle, version=None):
        return {"status": estado, "detail": detalle, "version": version}

    if formato == "deb":
        try:
            proc = subprocess.run(
                ["apt-cache", "policy", "aio-debian-gui"],
                capture_output=True, text=True, timeout=12, check=False,
                env={**os.environ, "LC_ALL": "C"},
            )
            if proc.returncode:
                raise RuntimeError((proc.stderr or "No se pudo consultar APT.")[:260])
            match = re.search(r"^\s*Candidate:\s*(\S+)", proc.stdout, re.M)
            if not match or match.group(1) == "(none)":
                return resultado("unknown", "No hay versión candidata en los índices APT.")
            candidata = match.group(1)
            if not version_instalada or not re.search(r"^[0-9]", version_instalada):
                return resultado("unknown", "No se pudo identificar la versión DEB instalada.")
            compara = subprocess.run(
                ["dpkg", "--compare-versions", candidata, "gt", version_instalada],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if compara.returncode not in (0, 1):
                raise RuntimeError("No se pudieron comparar las versiones de Debian.")
            if compara.returncode == 0:
                return resultado("available",
                    f"Instalada: {version_instalada}. Disponible en APT: {candidata}.", candidata)
            return resultado("current",
                f"Instalada: {version_instalada}. Al día según los índices APT locales.", candidata)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            return resultado("unknown", f"No se pudo consultar APT: {exc}")

    if formato == "flatpak":
        try:
            proc = subprocess.run(
                ["flatpak-spawn", "--host", "flatpak", "remote-ls", "--user",
                 "--updates", "--app", "--columns=application"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if proc.returncode:
                raise RuntimeError((proc.stderr or "Consulta Flatpak fallida.")[:260])
            if app_id in proc.stdout.splitlines():
                return resultado("available",
                    f"Hay una actualización de AiO en el repositorio Flatpak configurado (instalada: {version_instalada}).")
            return resultado("current",
                f"Sin actualizaciones según los metadatos Flatpak locales (instalada: {version_instalada}).")
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            return resultado("unknown", f"No se pudo consultar el repositorio Flatpak: {exc}")

    if formato == "appimage":
        try:
            reciente, _nombre, _url, _sha = obtener_release_actualizacion()
            actual = version_numerica(version_instalada)
            if actual is None:
                return resultado("unknown", "No se pudo identificar la versión de la AppImage actual.")
            if version_numerica(reciente) > actual:
                return resultado("available",
                    f"Instalada: {version_instalada}. Última versión publicada: {reciente}.", reciente)
            return resultado("current",
                f"Instalada: {version_instalada}. Última versión publicada: {reciente}.", reciente)
        except Exception as exc:
            return resultado("unknown", f"No se pudo consultar GitHub Releases: {exc}")

    return resultado("unsupported",
        "Esta edición no dispone de actualización automática integrada.")
