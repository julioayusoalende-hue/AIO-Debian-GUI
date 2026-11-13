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

python3 scripts/test-updater.py && bien "actualizador AppImage: versiones y SHA-256" || fallo "pruebas de actualizador"
python3 scripts/test-history.py && bien "historial de mantenimiento y persistencia" || fallo "pruebas del historial"
python3 scripts/test-install-format.py && bien "detección de formato DEB/AppImage/Flatpak" || fallo "detección de formato"

if python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
    python3 scripts/test-preferences.py "$GUI" &&
        bien "preferencias, traducciones, Acerca de y modo simple" ||
        fallo "pruebas de preferencias"
else
    echo "- PyGObject no instalado: se omiten las pruebas de preferencias"
fi

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

# La política no debe autorizar sesiones inactivas ni retener privilegios.
if grep -Fq '<allow_any>no</allow_any>' package/usr/share/polkit-1/actions/es.aiodebian.gui.policy &&
   grep -Fq '<allow_inactive>no</allow_inactive>' package/usr/share/polkit-1/actions/es.aiodebian.gui.policy &&
   grep -Fq '<allow_active>auth_admin</allow_active>' package/usr/share/polkit-1/actions/es.aiodebian.gui.policy &&
   grep -Fq 'La autorización permanente sin contraseña se ha retirado' "$HELPER"; then
    bien "Polkit requiere autorización activa y no permite nuevas reglas sin contraseña"
else
    fallo "revisión de seguridad de la política Polkit"
fi
sh -n package/DEBIAN/postinst && bien "sintaxis postinst" || fallo "sintaxis postinst"

# La versión del control debe tener su entrada de novedades en la GUI y en el CHANGELOG
V=$(sed -n 's/^Version: //p' package/DEBIAN/control)
[ "$(bash "$HELPER" --version)" = "$V" ] &&
    bien "versión del asistente coincide con el paquete" ||
    fallo "versión del asistente incompatible con el paquete"
grep -Fq -- '--check-update-self)' "$HELPER" &&
    bien "actualizador APT con comprobación previa" ||
    fallo "falta comprobación previa APT"
grep -q "\"$V\":" "$GUI"   && bien "novedad $V en la GUI"      || fallo "falta la novedad $V en $GUI (NOVEDADES)"
grep -q "^## $V" CHANGELOG.md && bien "entrada $V en CHANGELOG.md" || fallo "falta '## $V' en CHANGELOG.md"

if grep -Fq '("backports-kernel-mesa",' "$GUI" &&
   grep -Fq 'helper_admite_tarea(helper, "backports-kernel-mesa")' "$GUI" &&
   grep -Fq 'paso_backports_kernel_mesa()' "$HELPER" &&
   grep -Fq '[backports-kernel-mesa]=' "$HELPER"; then
    bien "tarea de kernel y Mesa Backports conectada entre GUI y asistente"
else
    fallo "la tarea de kernel y Mesa Backports no está conectada"
fi

ESTADOS=$(bash "$HELPER" --status) || {
    fallo "consulta de estado de tareas"
    ESTADOS=""
}
for tarea in repos tools backports-kernel-mesa gnome-plugin ext-manager; do
    printf '%s\n' "$ESTADOS" | grep -Eq "^##STATUS:${tarea}:[01]$" ||
        fallo "falta un estado válido para la tarea $tarea"
done

TMP_TEST=$(mktemp -d)
trap 'rm -rf -- "$TMP_TEST"' EXIT
mkdir -p "$TMP_TEST/apt/sources.list.d"
printf '%s\n' "Types: deb" "URIs: http://deb.debian.org/debian" \
    "Suites: trixie" "Components: main" > "$TMP_TEST/apt/sources.list.d/test.sources"
if bash -c '
    source "$1"
    estado_repos "$2" && exit 1
    printf "%s\n" "Types: deb" "URIs: http://deb.debian.org/debian" \
        "Suites: trixie" "Components: main contrib non-free" \
        > "$2/sources.list.d/test.sources"
    estado_repos "$2"
' _ "$HELPER" "$TMP_TEST/apt"; then
    bien "estado de repositorios distingue configuración incompleta y completa"
else
    fallo "estado de repositorios incorrecto"
fi

if bash -c '
    source "$1"
    paquete_instalado() {
        case "$1" in
            needrestart|fastfetch|kitty|synaptic|libfuse2t64) return 0 ;;
            *) return 1 ;;
        esac
    }
    estado_tools || exit 1
    paquete_instalado() {
        case "$1" in
            synaptic) return 1 ;;
            *) return 0 ;;
        esac
    }
    if estado_tools; then exit 1; fi
' _ "$HELPER"; then
    bien "estado de herramientas requiere todos los paquetes y FUSE"
else
    fallo "estado de herramientas incorrecto"
fi

if bash -c '
    source "$1"
    debian_backports_codename() { printf "%s\n" trixie; }
    kernel_backports_package() { printf "%s\n" linux-image-amd64; }
    paquete_disponible_en_suite() { return 0; }
    paquete_instalado_en_suite() { return 0; }
    estado_backports || exit 1
    paquete_instalado_en_suite() {
        [ "$1" != libgl1-mesa-dri ]
    }
    if estado_backports; then exit 1; fi
' _ "$HELPER"; then
    bien "estado de Backports requiere kernel y Mesa instalados desde la suite"
else
    fallo "estado de Backports incorrecto"
fi

if bash -c '
    source "$1"
    paquete_instalado() { [ "$1" = gnome-software-plugin-flatpak ]; }
    estado_gnome_plugin || exit 1
    paquete_instalado() { [ "$1" = gnome-shell-extension-manager ]; }
    estado_ext_manager
' _ "$HELPER"; then
    bien "estado GNOME comprueba plugin y Extension Manager instalados"
else
    fallo "estado de las opciones GNOME incorrecto"
fi

exit $fallos
