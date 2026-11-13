#!/usr/bin/env python3
"""Pruebas aisladas del módulo de actualización y verificación AppImage."""
import hashlib
import io
import json
import os
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.abspath("package/usr/lib/aio-debian-gui"))
from aio_core import updates

assert updates.version_numerica("1.1.0") == (1, 1, 0)
assert updates.version_numerica("v2.10.3") > updates.version_numerica("2.9.99")
assert updates.version_numerica("1x0x17") is None
assert updates.version_numerica("1.0.17-beta") is None

with tempfile.TemporaryDirectory() as tmp:
    payload = b"AppImage test payload"
    expected = hashlib.sha256(payload).hexdigest()
    name = "aio-debian-gui_1.1.0_x86_64.AppImage"
    root = updates.HOMEPAGE + "/releases/download/v1.1.0/"
    release = json.dumps({
        "tag_name": "v1.1.0",
        "assets": [
            {"name": name, "browser_download_url": root + name},
            {"name": "SHA256SUMS", "browser_download_url": root + "SHA256SUMS"},
        ],
    }).encode()
    checksums = (expected + "  " + name + "\n").encode()
    sources = {
        updates.RELEASE_API: release,
        root + name: payload,
        root + "SHA256SUMS": checksums,
    }

    class Response(io.BytesIO):
        status = 200

    original = urllib.request.urlopen

    def fake_urlopen(request, timeout=0):
        url = request.full_url if hasattr(request, "full_url") else request
        return Response(sources[url])

    urllib.request.urlopen = fake_urlopen
    try:
        version, filename, url, checksum_url = updates.obtener_release_actualizacion()
        assert version == "1.1.0" and filename == name
        path = updates.descargar_appimage_verificado(
            version, filename, url, checksum_url, directorio_descargas=tmp,
        )
        assert open(path, "rb").read() == payload
        assert os.stat(path).st_mode & 0o111
        sources[url] = b"tampered"
        try:
            updates.descargar_appimage_verificado(
                version, filename, url, checksum_url, directorio_descargas=tmp,
            )
        except RuntimeError as err:
            assert "SHA-256" in str(err)
        else:
            raise AssertionError("Se aceptó un AppImage con checksum incorrecto")
        assert open(path, "rb").read() == payload
    finally:
        urllib.request.urlopen = original
print("✔ módulo de actualización AppImage: versiones, integridad y rollback seguro")
