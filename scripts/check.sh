#!/bin/bash
# Comprobaciones rápidas antes de publicar (las usa también la integración continua)
set -uo pipefail
cd "$(dirname "$0")/.."
# Evitar bytecode __pycache__ en los paquetes finales durante los tests.
export PYTHONDONTWRITEBYTECODE=1
fallos=0
fallo() { echo "✘ $*" >&2; fallos=1; }
bien()  { echo "✔ $*"; }

GUI=package/usr/bin/aio-debian-gui
HELPER=package/usr/lib/aio-debian-gui/aio-debian-gui-helper

for f in "$HELPER" scripts/*.sh ayusos-control-center/package/usr/lib/aio-debian-gui/extensions/ayusos/helper.sh; do
    bash -n "$f" && bien "sintaxis bash: $f" || fallo "sintaxis bash: $f"
done

python3 - "$GUI" <<'PY' && bien "sintaxis python: $GUI" || fallo "sintaxis python: $GUI"
import ast, sys
ast.parse(open(sys.argv[1], encoding="utf-8").read())
PY

python3 -c 'import ast, pathlib; [ast.parse(p.read_text(encoding="utf-8"), filename=str(p)) for p in pathlib.Path("package/usr/lib/aio-debian-gui/aio_core").glob("*.py")]' &&
    bien "módulos core Python válidos" || fallo "sintaxis módulos core"
python3 -c 'import ast, pathlib; [ast.parse(p.read_text(encoding="utf-8"), filename=str(p)) for p in pathlib.Path("ayusos-control-center/package/usr/lib/aio-debian-gui/extensions/ayusos").rglob("*.py")]' &&
    bien "extensión AyusOS Python válida" || fallo "sintaxis extensión AyusOS"
python3 -m unittest discover -s ayusos-control-center/tests -q &&
    bien "pruebas de extensión y onboarding" || fallo "pruebas de extensión y onboarding"
python3 scripts/test-core-preferences.py && bien "preferencias modulares" || fallo "pruebas de preferencias core"
bash scripts/test-update-testing.sh && bien "actualizador Testing" || fallo "actualizador Testing"
bash scripts/test-self-update.sh && bien "autoactualización estable segura" || fallo "autoactualización estable segura"
python3 scripts/test-gtk-versions.py && bien "compatibilidad GTK/GDK 3" || fallo "compatibilidad GTK/GDK 3"
python3 scripts/test-appearance.py && bien "tema automático y preferencia manual" || fallo "pruebas de apariencia"
bash scripts/test-polkit-escaping.sh && bien "validación de usuario Polkit" || fallo "validación de usuario Polkit"
bash scripts/test-passwordless.sh && bien "reglas Polkit de AiO y Flatpak de usuario" || fallo "pruebas de autorización"
bash scripts/test-distro.sh && bien "detección Debian/Ubuntu LTS y HWE" || fallo "pruebas de distribución"
python3 scripts/test-updater.py && bien "actualizador AppImage: versiones y SHA-256" || fallo "pruebas de actualizador"
python3 scripts/test-testing-release.py && bien "versionado y paquete de testing" || fallo "pruebas de testing"
python3 scripts/test-release-notes.py && bien "notas de release agregadas" || fallo "pruebas de notas de release"
python3 scripts/test-history.py && bien "historial de mantenimiento y persistencia" || fallo "pruebas del historial"
python3 scripts/test-scheduler.py && bien "programación automática de mantenimiento" || fallo "pruebas de programación"
python3 scripts/test-preflight.py && bien "modo de mantenimiento seguro" || fallo "pruebas de mantenimiento seguro"
python3 scripts/test-grub-settings.py && bien "ajustes de arranque de GRUB y restauración" || fallo "pruebas de GRUB"
bash scripts/test-upgrade-safety.sh && bien "actualización APT protegida" || fallo "pruebas de actualización APT segura"
bash scripts/test-apt-sources-transactional.sh && bien "fuentes APT transaccionales" || fallo "pruebas de fuentes APT transaccionales"
python3 scripts/test-diagnostics.py && bien "diagnóstico preventivo de solo lectura" || fallo "pruebas del diagnóstico"
(umask 022 && python3 scripts/test-host-integration.py) && bien "guía de integración del anfitrión" || fallo "pruebas de integración del anfitrión"
python3 scripts/test-host-updater.py && bien "actualizador del anfitrión" || fallo "pruebas del actualizador del anfitrión"
python3 scripts/test-interface-translations.py && bien "traducciones de interfaz y diagnóstico" || fallo "traducciones incompletas"
python3 scripts/test-app-update-diagnostic.py && bien "versiones y actualización desde diagnóstico" || fallo "pruebas de actualización desde diagnóstico"
python3 scripts/test-install-format.py && bien "detección de formato DEB/AppImage/Flatpak" || fallo "detección de formato"
python3 scripts/test-local-files.py && bien "instalación de .flatpakref y arrastrar archivos" || fallo "pruebas de archivos locales"
python3 scripts/test-software-queue.py && bien "cola del gestor de software y lotes APT/Flatpak" || fallo "pruebas de la cola del gestor de software"
python3 scripts/test-system-logo.py && bien "logotipos dinámicos Debian/Ubuntu" || fallo "pruebas de logotipos"
bash scripts/test-nvidia.sh && bien "detección NVIDIA e híbrida" || fallo "pruebas NVIDIA"
bash scripts/test-nvidia-dracut.sh && bien "reintento NVIDIA tras fallo de dracut" || fallo "reintento NVIDIA tras fallo de dracut"
bash scripts/test-backports-rollback.sh && bien "reversión Backports segura" || fallo "pruebas de reversión Backports"
bash scripts/test-backup-apps.sh && bien "instalación segura de aplicaciones de backup" || fallo "pruebas de aplicaciones de backup"
python3 scripts/test-apt-sources-backup.py && bien "copia y restauración de repositorios APT" || fallo "pruebas de copias APT"
python3 scripts/test-desktop-backup.py && bien "copia y restauración de ajustes del escritorio" || fallo "pruebas de copias del escritorio"
bash scripts/test-recommended-apps.sh && bien "instalación segura de apps recomendadas" || fallo "pruebas de apps recomendadas"
bash scripts/test-gnome-extensions.sh && bien "extensiones GNOME seguras" || fallo "extensiones GNOME"

if python3 -c 'import gi; gi.require_version("Gtk", "3.0")' >/dev/null 2>&1; then
    # Las pruebas GTK simulan el paquete DEB: sin estas variables, lanzar
    # check.sh desde un AppImage, Flatpak o Snap de AiO cambia las páginas y
    # el menú que construye la ventana y las pruebas fallan sin motivo.
    unset APPIMAGE FLATPAK_ID SNAP
    python3 scripts/test-gtk-appearance.py &&
        bien "seguimiento GTK del tema del sistema" ||
        fallo "seguimiento GTK del tema del sistema"
    python3 scripts/test-preferences.py "$GUI" &&
        bien "preferencias, traducciones, Acerca de y modo simple" ||
        fallo "pruebas de preferencias"
    python3 scripts/test-ui-flow.py && bien "flujos de interfaz y adaptación" || fallo "pruebas de interfaz"
    python3 scripts/test-software-queue-ui.py &&
        bien "selección múltiple y cola de instalación" ||
        fallo "pruebas GTK de la cola del gestor de software"
    python3 scripts/test-scheduler-ui.py && bien "interfaz de programación" || fallo "pruebas GTK de programación"
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
   grep -Fq 'subject.active)' "$HELPER" &&
   grep -Fq 'subject.local &&' "$HELPER"; then
    bien "Polkit exige autorización por defecto; excepción opcional limitada a sesión local activa"
else
    fallo "revisión de seguridad de la política Polkit"
fi
sh -n package/DEBIAN/prerm && bien "sintaxis prerm" || fallo "sintaxis prerm"
sh -n package/DEBIAN/postinst && bien "sintaxis postinst" || fallo "sintaxis postinst"

# La versión del control debe tener una entrada única en el CHANGELOG.
V=$(sed -n 's/^Version: //p' package/DEBIAN/control)
V=${V#*:}
SCHEDULER_VERSION=$(python3 -c 'import sys; sys.path.insert(0,"package/usr/lib/aio-debian-gui"); from aio_core.scheduler import VERSION; print(VERSION)')
[ "$SCHEDULER_VERSION" = "$V" ] && bien "versión del programador coincide con el paquete" || fallo "versión del programador incompatible"
[ -f package/usr/lib/systemd/system/aio-debian-gui-maintenance@.service ] && bien "servicio de mantenimiento incluido" || fallo "falta servicio systemd"
[ "$(bash "$HELPER" --version)" = "$V" ] &&
    bien "versión del asistente coincide con el paquete" ||
    fallo "versión del asistente incompatible con el paquete"
grep -Fq -- '--check-update-self)' "$HELPER" &&
    bien "actualizador APT con comprobación previa" ||
    fallo "falta comprobación previa APT"
[ "$(grep -Fxc "## ${V%%[~-]*}" CHANGELOG.md)" -eq 1 ] &&
    bien "entrada única de $V en CHANGELOG.md" ||
    fallo "se requiere una única sección '## ${V%%[~-]*}' en CHANGELOG.md"

if grep -Fq '("backports-kernel-mesa",' "$GUI" &&
   grep -Fq 'helper_admite_tarea(helper, "backports-kernel-mesa")' "$GUI" &&
   grep -Fq 'paso_backports_kernel_mesa()' "$HELPER" &&
   grep -Fq '[backports-kernel-mesa]=' "$HELPER" &&
   grep -Fq 'paso_revertir_backports()' "$HELPER" &&
   grep -Fq '("revertir-backports",' "$GUI"; then
    bien "tarea de kernel y Mesa Backports conectada entre GUI y asistente"
else
    fallo "la tarea de kernel y Mesa Backports no está conectada"
fi

# Ejecutar pruebas existentes de Debian incluso sobre los runners Ubuntu.
TMP_DISTRIBUTION_DIR=$(mktemp -d)
printf 'ID=debian\nVERSION_ID="13"\n' > "$TMP_DISTRIBUTION_DIR/debian-os-release"
export AIO_TEST_OS_RELEASE="$TMP_DISTRIBUTION_DIR/debian-os-release"
trap 'rm -rf -- "$TMP_DISTRIBUTION_DIR"' EXIT
ESTADOS=$(bash "$HELPER" --status) || {
    fallo "consulta de estado de tareas"
    ESTADOS=""
}
for tarea in repos tools backports-kernel-mesa ubuntu-hwe gnome-plugin ext-manager; do
    printf '%s\n' "$ESTADOS" | grep -Eq "^##STATUS:${tarea}:[01]$" ||
        fallo "falta un estado válido para la tarea $tarea"
done

TMP_TEST=$(mktemp -d)
trap 'rm -rf -- "$TMP_TEST" "$TMP_DISTRIBUTION_DIR"' EXIT
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

if grep -Eq '^Depends: .*[, ]needrestart([ ,]|$)' package/DEBIAN/control; then
    bien "needrestart es una dependencia obligatoria"
else
    fallo "needrestart debe estar en Depends"
fi

if bash -c '
    source "$1"
    paquete_instalado() {
        case "$1" in
            libnotify-bin|fastfetch|libfuse2t64) return 0 ;;
            *) return 1 ;;
        esac
    }
    estado_tools || exit 1
    asegurar_listas() { return 0; }
    instalar_paquete_si_falta() { echo "$1"; }
    ok() { :; }
    [ "$(paso_tools)" = "$(printf "libnotify-bin\nfastfetch")" ] || exit 1
    paquete_instalado() {
        case "$1" in
            fastfetch) return 1 ;;
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

python3 scripts/test-existing-scheduler.py && bien "reutilización del programador existente" || fallo "programador existente"

bash scripts/test-snap-maintenance.sh && bien "mantenimiento Snap" || fallo "mantenimiento Snap"

python3 scripts/test-snap-maintenance.py && bien "detección y programación Snap" || fallo "detección Snap"

bash scripts/test-cleanup.sh && bien "limpieza segura del sistema" || fallo "limpieza segura del sistema"

exit $fallos
