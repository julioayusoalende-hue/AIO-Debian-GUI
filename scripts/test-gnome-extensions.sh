#!/usr/bin/env bash
# Pruebas de la lista blanca y el flujo de instalación sin descargar nada.
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper

[ "${EXTENSIONES_GNOME[gnome-ext-appindicator]}" = "appindicatorsupport@rgcjonas.gmail.com" ]
[ "${EXTENSIONES_GNOME[gnome-ext-tiling-shell]}" = "tilingshell@ferrarodomenico.com" ]

TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
CALLS="$TMP/calls"
: > "$CALLS"

paquete_instalado() { [ "${1:-}" = gnome-shell ] && [ "${TEST_GNOME:-yes}" = yes ]; }
ejecutar_como_usuario_solicitante() {
    printf '%s\n' "$*" >> "$CALLS"
    case "$1 $2 $3" in
        'python3 -I '*) ;;
    esac
    if [ "$1" = python3 ] && [ "$3" = list ]; then
        [ "${TEST_INSTALLED:-no}" != yes ] || echo "${EXTENSIONES_GNOME[gnome-ext-appindicator]}"
    elif [ "$1" = mktemp ]; then
        command mktemp -d /tmp/aio-gnome-extension-test.XXXXXXXX
    elif [ "$1" = python3 ] && [ "$3" = download ]; then
        : > "$5"
    fi
}

TEST_GNOME=no
instalar_extension_gnome gnome-ext-appindicator >/dev/null
[ ! -s "$CALLS" ]

TEST_GNOME=yes TEST_INSTALLED=yes
instalar_extension_gnome gnome-ext-appindicator >/dev/null
! grep -q ' download ' "$CALLS"
! grep -q ' install ' "$CALLS"

: > "$CALLS"
TEST_INSTALLED=no
instalar_extension_gnome gnome-ext-appindicator >/dev/null
grep -q ' download gnome-ext-appindicator ' "$CALLS"
grep -q ' install gnome-ext-appindicator ' "$CALLS"

if instalar_extension_gnome gnome-ext-arbitrary >/dev/null 2>&1; then
    echo 'Se aceptó una extensión fuera de la lista blanca' >&2
    exit 1
fi

ESTADOS=$(mostrar_estados)
for tarea in gnome-ext-appindicator gnome-ext-blur-shell gnome-ext-caffeine \
             gnome-ext-clipboard-indicator gnome-ext-dash-to-dock \
             gnome-ext-places-status gnome-ext-tiling-shell; do
    grep -Eq "^##STATUS:${tarea}:[01]$" <<< "$ESTADOS"
done

echo "✔ Extensiones GNOME: lista blanca, instalación como usuario y estados"
