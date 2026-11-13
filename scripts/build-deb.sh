#!/bin/bash
# Construye el paquete .deb en dist/ (reproducible: permisos y fechas normalizados)
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^Version: //p' package/DEBIAN/control)
[ -n "$VERSION" ] || { echo "No se pudo leer la versión de package/DEBIAN/control" >&2; exit 1; }
SALIDA="dist/aio-debian-gui_${VERSION}_all.deb"

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
cp -a package/. "$STAGE/"

# Permisos normalizados (git/zip no los conservan siempre)
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/usr/bin/aio-debian-gui" \
          "$STAGE/usr/lib/aio-debian-gui/aio-debian-gui-helper"

# Fecha fija = fecha del último commit (o la actual si no hay git)
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"
find "$STAGE" -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +

mkdir -p dist
rm -f "$SALIDA"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$SALIDA"
echo "Paquete creado: $SALIDA"
