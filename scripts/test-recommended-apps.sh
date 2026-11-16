#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
TEST_DIR=$(mktemp -d)
trap 'rm -rf -- "$TEST_DIR"' EXIT

EXPECTED_PACKAGE=
INSTALLED=0
paquete_instalado() {
    [ "$1" = "$EXPECTED_PACKAGE" ] &&
        { [ "$INSTALLED" -eq 1 ] || [ -f "$TEST_DIR/installed" ]; }
}
asegurar_listas() {
    printf '%s\n' update >> "$TEST_DIR/calls"
}

for app in celluloid gimp handbrake vlc; do
    case "$app" in
        celluloid) EXPECTED_PACKAGE=celluloid ;;
        gimp) EXPECTED_PACKAGE=gimp ;;
        handbrake) EXPECTED_PACKAGE=handbrake ;;
        vlc) EXPECTED_PACKAGE=vlc ;;
    esac
    : > "$TEST_DIR/calls"
    INSTALLED=1
    output=$(instalar_aplicacion_recomendada "$app")
    [[ "$output" == "##RECOMMENDED:installed:$app" ]]
    [ ! -s "$TEST_DIR/calls" ]

    : > "$TEST_DIR/calls"
    INSTALLED=0
    apt-get() {
        printf '%s\n' "$*" >> "$TEST_DIR/calls"
        [[ " $* " == *" --no-remove install $EXPECTED_PACKAGE "* ]]
        touch "$TEST_DIR/installed"
    }
    output=$(instalar_aplicacion_recomendada "$app")
    [[ "$output" == *"##RECOMMENDED:installed:$app" ]]
    grep -Fxq update "$TEST_DIR/calls"
    grep -Fq -- "--no-remove install $EXPECTED_PACKAGE" "$TEST_DIR/calls"
    rm -f -- "$TEST_DIR/installed"
done

if instalar_aplicacion_recomendada arbitrary >/dev/null 2>&1; then
    echo "ERROR: se aceptó una aplicación fuera de la lista permitida" >&2
    exit 1
fi

echo "✔ Instalación APT recomendada limitada a Celluloid, GIMP, HandBrake y VLC"
