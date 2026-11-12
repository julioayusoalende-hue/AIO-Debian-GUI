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
sh -n scripts/appimage/AppRun && bien "sintaxis AppRun" || fallo "sintaxis AppRun"

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

REGLA=$(bash -c 'source "$1"; generar_regla_polkit "test-user"' _ "$HELPER") || {
    fallo "generación de regla polkit"
    REGLA=""
}
if printf '%s\n' "$REGLA" | grep -Fq 'action.id === "es.aiodebian.gui.mantenimiento"' &&
   printf '%s\n' "$REGLA" | grep -Fq 'action.lookup("program") === "/usr/lib/aio-debian-gui/aio-debian-gui-helper"' &&
   printf '%s\n' "$REGLA" | grep -Fq 'subject.user === "test-user"' &&
   printf '%s\n' "$REGLA" | grep -Fq "subject.local" &&
   printf '%s\n' "$REGLA" | grep -Fq "subject.active"; then
    bien "regla polkit limitada al usuario y al asistente de AiO"
else
    fallo "la regla polkit no limita correctamente la autorización"
fi

# La versión del control debe tener su entrada de novedades en la GUI y en el CHANGELOG
V=$(sed -n 's/^Version: //p' package/DEBIAN/control)
grep -q "\"$V\":" "$GUI"   && bien "novedad $V en la GUI"      || fallo "falta la novedad $V en $GUI (NOVEDADES)"
grep -q "^## $V" CHANGELOG.md && bien "entrada $V en CHANGELOG.md" || fallo "falta '## $V' en CHANGELOG.md"

exit $fallos
