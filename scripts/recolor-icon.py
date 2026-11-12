#!/usr/bin/env python3
"""Regenera los iconos de package/usr/share/icons cambiando el color de fondo.

Parte de assets/icon-original-512.png (fondo azul) y gira el tono de los píxeles azules
saturados (fondo y mango del destornillador); el remolino blanco y las herramientas
plateadas no cambian. Requiere: python3-pil y python3-numpy.

Uso: scripts/recolor-icon.py [TONO]
  TONO en grados (0-360). Por defecto 145 (verde).
  Ejemplos: 145 verde · 28 naranja · 275 violeta · 350 rojo · 205 = azul original
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "assets" / "icon-original-512.png"
DESTINO = RAIZ / "package" / "usr/share/icons/hicolor"
TAMANOS = (48, 64, 128, 256, 512)
NOMBRE = "aio-debian-gui.png"


def recolorear(img, tono):
    a = np.asarray(img.convert("RGBA")).astype(np.float32) / 255.0
    rgb, alfa = a[..., :3], a[..., 3]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    seguro = np.maximum(d, 1e-6)
    h = np.where(
        r == mx, (mx - b) / seguro - (mx - g) / seguro,
        np.where(g == mx, 2.0 + (mx - r) / seguro - (mx - b) / seguro,
                 4.0 + (mx - g) / seguro - (mx - r) / seguro),
    )
    h = np.where(d > 1e-6, (h / 6.0) % 1.0, 0)

    azul = (h > 0.50) & (h < 0.72)
    peso = np.clip((s - 0.25) / 0.25, 0, 1) * azul     # blancos y grises: peso 0

    nh = np.where(peso > 0, tono / 360.0, h)
    i = np.floor(nh * 6).astype(int) % 6
    f = nh * 6 - np.floor(nh * 6)
    p, q, t = mx * (1 - s), mx * (1 - f * s), mx * (1 - (1 - f) * s)
    c = [i == k for k in range(6)]
    nuevo = np.stack([
        np.select(c, [mx, q, p, p, t, mx]),
        np.select(c, [t, mx, mx, q, p, p]),
        np.select(c, [p, p, t, mx, mx, q]),
    ], -1)
    salida = rgb * (1 - peso[..., None]) + nuevo * peso[..., None]
    res = np.dstack([salida, alfa])
    return Image.fromarray((res * 255 + 0.5).astype(np.uint8), "RGBA")


def main():
    tono = float(sys.argv[1]) if len(sys.argv) > 1 else 145.0
    base = recolorear(Image.open(ORIGEN), tono)
    for t in TAMANOS:
        ruta = DESTINO / f"{t}x{t}" / "apps" / NOMBRE
        ruta.parent.mkdir(parents=True, exist_ok=True)
        img = base if t == 512 else base.resize((t, t), Image.LANCZOS)
        img.save(ruta, optimize=True)
        print("escrito", ruta.relative_to(RAIZ))


if __name__ == "__main__":
    main()
