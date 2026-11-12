#!/bin/bash
# Comprobaciones rápidas antes de publicar (las usa también la integración continua)
set -uo pipefail
cd "$(dirname "$0")/.."
fallos=0
fallo() { echo "✘ $*" >&2; fallos=1; }
bien()  { echo "✔ $*"; }

GUI=package/usr/bin/aio-debian-gui
HELPER=package/usr/lib/aio-debian-gui/aio-debian-gui-helper

for f in "$HELPER" scripts/*.sh; do
    bash -n "$f" && bien "sintaxis bash: $f" || fallo "sintaxis bash: $f"
done

python3 - "$GUI" <<'PY' && bien "sintaxis python: $GUI" || fallo "sintaxis python: $GUI"
import ast, sys
ast.parse(open(sys.argv[1], encoding="utf-8").read())
PY

if command -v shellcheck >/dev/null; then
    shellcheck -S error "$HELPER" scripts/*.sh && bien "shellcheck" || fallo "shellcheck"
else
    echo "- shellcheck no instalado: se omite"
fi
if command -v xmllint >/dev/null; then
    xmllint --noout package/usr/share/polkit-1/actions/*.policy && bien "XML polkit" || fallo "XML polkit"
fi
if command -v desktop-file-validate >/dev/null; then
    desktop-file-validate package/usr/share/applications/*.desktop && bien "archivo .desktop" || fallo "archivo .desktop"
fi

# La versión del control debe tener su entrada de novedades en la GUI y en el CHANGELOG
V=$(sed -n 's/^Version: //p' package/DEBIAN/control)
grep -q "\"$V\":" "$GUI"   && bien "novedad $V en la GUI"      || fallo "falta la novedad $V en $GUI (NOVEDADES)"
grep -q "^## $V" CHANGELOG.md && bien "entrada $V en CHANGELOG.md" || fallo "falta '## $V' en CHANGELOG.md"

exit $fallos
