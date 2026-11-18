#!/bin/bash
# Construye el paquete .deb en dist/ (reproducible: permisos y fechas normalizados)
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^Version: //p' package/DEBIAN/control)
[ -n "$VERSION" ] || { echo "No se pudo leer la versión de package/DEBIAN/control" >&2; exit 1; }
EPOCH=""
if [[ "$VERSION" == *:* ]]; then
    EPOCH="${VERSION%%:*}:"
fi
VERSION=${VERSION#*:}
if [ "$#" -ne 0 ]; then
    if [ "$#" -ne 2 ] || [ "$1" != "--testing-version" ] ||
       [[ ! "$2" =~ ^[0-9]+\.[0-9]+\.[0-9]+~testing\.[1-9][0-9]*\.[1-9][0-9]*$ ]]; then
        echo "Uso: $0 [--testing-version X.Y.Z~testing.N.INTENTO]" >&2
        exit 2
    fi
    TESTING_VERSION=$2
else
    TESTING_VERSION=""
fi
PUBLIC_VERSION=${TESTING_VERSION:-$VERSION}
SALIDA="dist/aio-debian-gui_${PUBLIC_VERSION}_all.deb"

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
cp -a package/. "$STAGE/"

if [ -n "$TESTING_VERSION" ]; then
    python3 - "$STAGE" "$EPOCH" "$VERSION" "$TESTING_VERSION" <<'PY'
from pathlib import Path
import sys

stage, epoch, old, new = sys.argv[1:]
files = [
    ("DEBIAN/control", f"Version: {epoch}{old}\n", f"Version: {epoch}{new}\n"),
    ("usr/lib/aio-debian-gui/aio_core/scheduler.py", f"VERSION = '{old}'\n", f"VERSION = '{new}'\n"),
    ("usr/lib/aio-debian-gui/aio-debian-gui-helper", f"HELPER_VERSION={old}\n", f"HELPER_VERSION={new}\n"),
]
for name, original, replacement in files:
    path = Path(stage, name)
    text = path.read_text(encoding="utf-8")
    if text.count(original) != 1:
        raise SystemExit(f"Versión ausente o incompatible en {name}")
    path.write_text(text.replace(original, replacement), encoding="utf-8")
PY
fi

NOTAS="$STAGE/usr/share/aio-debian-gui/release-notes.txt"
awk -v version="${PUBLIC_VERSION}" -v seccion="${PUBLIC_VERSION%%~*}" '
    $0 == "## " seccion { activo = 1; encontrados++; next }
    /^## / { activo = 0 }
    activo && NF {
        if (!contenido++) print version
        sub(/^- /, "• ")
        gsub(/`/, "")
        print
    }
    END { if (encontrados != 1 || !contenido) exit 1 }
' CHANGELOG.md > "$NOTAS" || {
    echo "El CHANGELOG debe contener una única sección con novedades para ${PUBLIC_VERSION%%~*}." >&2
    exit 1
}

# Permisos normalizados (git/zip no los conservan siempre)
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/usr/bin/aio-debian-gui" \
          "$STAGE/usr/lib/aio-debian-gui/aio-debian-gui-helper"

# Fecha fija = fecha del último commit (o la actual si no hay git)
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"
find "$STAGE" -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +

mkdir -p dist
rm -f "$SALIDA"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$SALIDA"
echo "Paquete creado: $SALIDA"
