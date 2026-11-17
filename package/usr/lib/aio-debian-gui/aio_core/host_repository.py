"""Verificación de metadatos y paquetes del repositorio aislado del anfitrión."""
import hashlib
import re
import subprocess
import urllib.error
import urllib.request
from email import policy
from email.parser import BytesParser

MAX_RELEASE = 1024 * 1024
MAX_INDEX = 4 * 1024 * 1024
MAX_PACKAGE = 32 * 1024 * 1024
PACKAGE = "aio-debian-gui-host"
INDEX = "main/binary-all/Packages"
BASE_URL = "https://julioayusoalende-hue.github.io/AIO-Debian-GUI/host-repo/"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise urllib.error.HTTPError(request.full_url, code, "Redirección no permitida", headers, fp)


def _download(opener, path, limit):
    request = urllib.request.Request(BASE_URL + path, headers={"Accept-Encoding": "identity"})
    with opener.open(request, timeout=30) as response:
        data = response.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError("Respuesta del repositorio host vacía o demasiado grande.")
    return data


def _fields(data):
    if b"\0" in data:
        raise ValueError("Metadatos APT no válidos.")
    message = BytesParser(policy=policy.compat32).parsebytes(data)
    if message.defects:
        raise ValueError("Metadatos APT malformados.")
    result = {}
    for name, value in message.items():
        name = name.lower()
        if name in result:
            raise ValueError("Campo APT duplicado: " + name)
        result[name] = str(value).strip()
    return result


def _size(value, maximum):
    if not re.fullmatch(r"[0-9]{1,10}", value):
        raise ValueError("Tamaño APT no válido.")
    size = int(value)
    if not 0 < size <= maximum:
        raise ValueError("Tamaño APT fuera de límites.")
    return size


def _digest(value):
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Huella APT no válida.")
    return value


def verify_release(inrelease, keyring):
    """Autentica InRelease con una clave elegida por el administrador."""
    if not 0 < len(inrelease) <= MAX_RELEASE:
        raise ValueError("InRelease vacío o demasiado grande.")
    result = subprocess.run(
        ["/usr/bin/gpgv", "--keyring", str(keyring), "--output", "-", "-"],
        input=inrelease, capture_output=True, timeout=30, check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    if result.returncode:
        raise ValueError("La firma del repositorio host no es válida.")
    fields = _fields(result.stdout)
    if (fields.get("origin") != PACKAGE or fields.get("suite") != "stable"
            or fields.get("codename") != "stable"
            or fields.get("architectures") != "all"
            or fields.get("components") != "main"):
        raise ValueError("El repositorio host no corresponde al esperado.")
    matches = []
    for line in fields.get("sha256", "").splitlines():
        parts = line.split()
        if len(parts) != 3:
            raise ValueError("Índice de huellas APT no válido.")
        if parts[2] == INDEX:
            matches.append((_digest(parts[0]), _size(parts[1], MAX_INDEX)))
    if len(matches) != 1:
        raise ValueError("El índice del repositorio host no es único.")
    return matches[0]


def verify_index(data, expected):
    """Comprueba el índice firmado y devuelve la identidad exacta del paquete."""
    digest, size = expected
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("El índice del repositorio host no coincide con su firma.")
    blocks = [block for block in re.split(rb"\n[ \t]*\n", data) if block.strip()]
    if len(blocks) != 1:
        raise ValueError("El repositorio host debe contener un único paquete.")
    fields = _fields(blocks[0])
    version = fields.get("version", "")
    if (fields.get("package") != PACKAGE or fields.get("architecture") != "all"
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
            or len(version) > 40):
        raise ValueError("Identidad del paquete host no válida.")
    filename = "pool/main/a/aio-debian-gui/" + PACKAGE + "_" + version + "_all.deb"
    if fields.get("filename") != filename:
        raise ValueError("Ruta del paquete host no válida.")
    return {
        "version": version,
        "filename": filename,
        "size": _size(fields.get("size", ""), MAX_PACKAGE),
        "sha256": _digest(fields.get("sha256", "")),
    }


def verify_package(data, metadata):
    if (len(data) != metadata["size"]
            or hashlib.sha256(data).hexdigest() != metadata["sha256"]):
        raise ValueError("El paquete host no coincide con los metadatos firmados.")


def download_package(keyring):
    """Descarga únicamente el paquete autenticado por el repositorio fijo."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    release = _download(opener, "dists/stable/InRelease", MAX_RELEASE)
    expected_index = verify_release(release, keyring)
    index = _download(opener, "dists/stable/" + INDEX, MAX_INDEX)
    metadata = verify_index(index, expected_index)
    data = _download(opener, metadata["filename"], metadata["size"])
    verify_package(data, metadata)
    return metadata, data
