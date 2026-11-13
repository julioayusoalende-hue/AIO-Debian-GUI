#!/usr/bin/env python3
"""Pruebas offline del actualizador AppImage: versiones, checksum y fallo seguro."""
import ast
import hashlib
import io
import json
import os
import re
import tempfile
import types
import urllib.error
import urllib.request

SOURCE = "package/usr/bin/aio-debian-gui"
with open(SOURCE, encoding="utf-8") as source:
    tree = ast.parse(source.read(), filename=SOURCE)
names = {"version_numerica", "obtener_release_actualizacion", "descargar_appimage_verificado"}
selected = [node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names]
assert {x.name for x in selected} == names
ns = {
    "hashlib": hashlib, "io": io, "json": json, "os": os, "re": re,
    "tempfile": tempfile, "urllib": urllib, "RuntimeError": RuntimeError,
    "MAX_APPIMAGE_SIZE": 256 * 1024 * 1024,
    "HOMEPAGE": "https://github.com/julioayusoalende-hue/AIO-Debian-GUI",
    "RELEASE_API": "https://api.github.com/repos/julioayusoalende-hue/AIO-Debian-GUI/releases/latest",
}
with tempfile.TemporaryDirectory() as tmp:
    ns["GLib"] = types.SimpleNamespace(
        UserDirectory=types.SimpleNamespace(DIRECTORY_DOWNLOAD=0),
        get_user_special_dir=lambda _: tmp,
    )
    exec(compile(ast.Module(body=selected, type_ignores=[]), SOURCE, "exec"), ns)
    version = ns["version_numerica"]
    assert version("1.0.17") == (1, 0, 17)
    assert version("v2.10.3") > version("2.9.99")
    assert version("1x0x17") is None
    assert version("1.0.17-beta") is None

    payload = b"AppImage test payload"
    expected = hashlib.sha256(payload).hexdigest()
    name = "aio-debian-gui_1.0.17_x86_64.AppImage"
    root = ns["HOMEPAGE"] + "/releases/download/v1.0.17/"
    release = json.dumps({
        "tag_name": "v1.0.17",
        "assets": [
            {"name": name, "browser_download_url": root + name},
            {"name": "SHA256SUMS", "browser_download_url": root + "SHA256SUMS"},
        ],
    }).encode()
    checksums = (expected + "  " + name + "\n").encode()
    sources = {
        ns["RELEASE_API"]: release,
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
        value, filename, url, checksum_url = ns["obtener_release_actualizacion"]()
        assert value == "1.0.17" and filename == name
        path = ns["descargar_appimage_verificado"](value, filename, url, checksum_url)
        assert open(path, "rb").read() == payload
        assert os.stat(path).st_mode & 0o111

        # Si los bytes cambian, el instalador existente NO se modifica.
        sources[url] = b"tampered"
        try:
            ns["descargar_appimage_verificado"](value, filename, url, checksum_url)
        except RuntimeError as err:
            assert "SHA-256" in str(err)
        else:
            raise AssertionError("Se aceptó un AppImage con checksum incorrecto")
        assert open(path, "rb").read() == payload
    finally:
        urllib.request.urlopen = original
print("✔ actualizador AppImage: versiones, descarga verificada y fallo seguro")
