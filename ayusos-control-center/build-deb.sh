#!/bin/bash
# Construye ayusos-control-center como paquete .deb independiente.
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(sed -n 's/^Version: //p' package/DEBIAN/control)
[ -n "$VERSION" ] || { echo 'No se pudo leer la versión' >&2; exit 1; }
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
cp -a package/. "$STAGE/"
find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf -- {} +
find "$STAGE" -name '*.py[co]' -type f -delete
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" \
    "$STAGE/usr/bin/ayusos-onboarding-graphical" \
    "$STAGE/usr/local/libexec/ayusos-aio-inicial" \
    "$STAGE/usr/local/libexec/ayusos-aio-autorizar" \
    "$STAGE/usr/local/libexec/ayusos-aplicar-onboarding" \
    "$STAGE/usr/local/libexec/ayusos-timeshift" \
    "$STAGE/usr/lib/aio-debian-gui/extensions/ayusos/software_manager/admin.py" \
    "$STAGE/usr/lib/aio-debian-gui/extensions/ayusos/aio-run"
mkdir -p dist
rm -f "dist/ayusos-control-center_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "dist/ayusos-control-center_${VERSION}_all.deb"
echo "Paquete creado: dist/ayusos-control-center_${VERSION}_all.deb"
