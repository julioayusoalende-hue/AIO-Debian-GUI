#!/bin/bash
# Construye ayusos-control-center como paquete .deb independiente.
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(sed -n 's/^Version: //p' package/DEBIAN/control)
[ -n "$VERSION" ] || { echo 'No se pudo leer la versión' >&2; exit 1; }
AIO_VERSION=""
case "$#" in
    0) ;;
    2)
        if [[ "$1" != --aio-release-version || ! "$2" =~ ^([0-9]+:)?[0-9]+\.[0-9]+\.[0-9]+(~testing\.[1-9][0-9]*\.[1-9][0-9]*)?$ ]]; then
            echo "Versión de AiO para publicación no válida." >&2
            exit 2
        fi
        AIO_VERSION=$2
        VERSION=${AIO_VERSION#*:}
        ;;
    *)
        echo "Uso: $0 [--aio-release-version VERSIÓN_DEBIAN]" >&2
        exit 2
        ;;
esac
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
cp -a package/. "$STAGE/"
if [[ -n "$AIO_VERSION" ]]; then
    sed -i -e "s/^Version: .*/Version: $VERSION/" \
        -e "s/^Depends: aio-debian-gui,/Depends: aio-debian-gui (>= $AIO_VERSION),/" \
        "$STAGE/DEBIAN/control"
fi
find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf -- {} +
find "$STAGE" -name '*.py[co]' -type f -delete
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"
find "$STAGE" -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" \
    "$STAGE/usr/bin/ayusos-onboarding-graphical" \
    "$STAGE/usr/local/libexec/ayusos-aio-inicial" \
    "$STAGE/usr/local/libexec/ayusos-aio-autorizar" \
    "$STAGE/usr/local/libexec/ayusos-aio-limpiar-usuario" \
    "$STAGE/usr/local/libexec/ayusos-aplicar-onboarding" \
    "$STAGE/usr/local/libexec/ayusos-timeshift" \
    "$STAGE/usr/local/libexec/ayusos-recovery-session" \
    "$STAGE/usr/lib/aio-debian-gui/extensions/ayusos/aio-run" \
    "$STAGE/usr/lib/aio-debian-gui/extensions/ayusos/ayusos-recovery"
mkdir -p dist
rm -f "dist/ayusos-control-center_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "dist/ayusos-control-center_${VERSION}_all.deb"
echo "Paquete creado: dist/ayusos-control-center_${VERSION}_all.deb"
