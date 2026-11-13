#!/bin/bash
# Construye un AppImage Debian-targeted en dist/ (requiere appimagetool).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

VERSION=$(sed -n 's/^Version: //p' package/DEBIAN/control)
[ -n "$VERSION" ] || { echo "No se pudo leer la versión de package/DEBIAN/control" >&2; exit 1; }
[ "$(uname -m)" = x86_64 ] || { echo "Este script solo crea AppImages x86_64." >&2; exit 1; }

APPIMAGETOOL=${APPIMAGETOOL:-appimagetool}
command -v "$APPIMAGETOOL" >/dev/null 2>&1 || {
    echo "No se encontró appimagetool. Instálalo o define APPIMAGETOOL con su ruta." >&2
    exit 1
}
APPIMAGETOOL=$(command -v "$APPIMAGETOOL")

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
RUNTIME_FILE=${APPIMAGE_RUNTIME_FILE:-"$STAGE/runtime-x86_64"}
if [ -z "${APPIMAGE_RUNTIME_FILE:-}" ]; then
    python3 - "$RUNTIME_FILE" <<'PY'
import sys
import urllib.request

url = "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64"
with urllib.request.urlopen(url, timeout=60) as response:
    data = response.read()
with open(sys.argv[1], "wb") as runtime:
    runtime.write(data)
PY
fi
RUNTIME_SHA256=2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d
ACTUAL_SHA256=$(sha256sum "$RUNTIME_FILE" | awk '{print $1}')
[ "$ACTUAL_SHA256" = "$RUNTIME_SHA256" ] || {
    echo "La suma SHA256 del runtime AppImage no coincide." >&2
    exit 1
}

APPDIR="$STAGE/AppDir"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib/aio-debian-gui" \
         "$APPDIR/usr/share/applications" "$APPDIR/usr/share/aio-debian-gui" \
         "$APPDIR/usr/share/doc/aio-debian-gui" "$APPDIR/usr/share/polkit-1/actions"

install -m 755 package/usr/bin/aio-debian-gui "$APPDIR/usr/bin/aio-debian-gui"
cp -a package/usr/lib/aio-debian-gui/aio_core "$APPDIR/usr/lib/aio-debian-gui/aio_core"
install -m 755 package/usr/lib/aio-debian-gui/aio-debian-gui-helper \
    "$APPDIR/usr/lib/aio-debian-gui/aio-debian-gui-helper"
install -m 644 package/usr/share/aio-debian-gui/debian-openlogo.png \
    "$APPDIR/usr/share/aio-debian-gui/debian-openlogo.png"
install -m 644 package/usr/share/aio-debian-gui/ubuntu-logo.svg \
    "$APPDIR/usr/share/aio-debian-gui/ubuntu-logo.svg"
install -m 644 package/usr/share/aio-debian-gui/adri-y-lu.jpg \
    "$APPDIR/usr/share/aio-debian-gui/adri-y-lu.jpg"
install -m 644 package/usr/share/doc/aio-debian-gui/copyright \
    "$APPDIR/usr/share/doc/aio-debian-gui/copyright"
install -m 644 package/usr/share/polkit-1/actions/es.aiodebian.gui.policy \
    "$APPDIR/usr/share/polkit-1/actions/es.aiodebian.gui.policy"
cp -a package/usr/share/icons/hicolor "$APPDIR/usr/share/icons"
install -m 644 package/usr/share/icons/hicolor/512x512/apps/aio-debian-gui.png \
    "$APPDIR/aio-debian-gui.png"
sed 's/^Exec=aio-debian-gui$/Exec=AppRun/' \
    package/usr/share/applications/aio-debian-gui.desktop \
    > "$APPDIR/usr/share/applications/aio-debian-gui.desktop"
cp "$APPDIR/usr/share/applications/aio-debian-gui.desktop" "$APPDIR/aio-debian-gui.desktop"
sed "s/@VERSION@/$VERSION/" scripts/appimage/AppRun > "$APPDIR/AppRun"
chmod 755 "$APPDIR/AppRun"
ln -s usr/share/icons/hicolor/512x512/apps/aio-debian-gui.png "$APPDIR/.DirIcon"

mkdir -p dist
OUTPUT="dist/aio-debian-gui_${VERSION}_x86_64.AppImage"
rm -f "$OUTPUT"
ARCH=x86_64 "$APPIMAGETOOL" --runtime-file "$RUNTIME_FILE" "$APPDIR" "$OUTPUT"
chmod 755 "$OUTPUT"
echo "AppImage creado: $OUTPUT"
