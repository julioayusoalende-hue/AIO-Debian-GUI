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
gnome-extensions() { :; }
ejecutar_como_usuario_solicitante() {
    printf '%s\n' "$*" >> "$CALLS"
    if [ "$1" = python3 ] && [ "${4:-}" = list ]; then
        [ "${TEST_INSTALLED:-no}" != yes ] || echo "${EXTENSIONES_GNOME[gnome-ext-appindicator]}"
    fi
}

TEST_GNOME=no
instalar_extension_gnome gnome-ext-appindicator >/dev/null
[ ! -s "$CALLS" ]

TEST_GNOME=yes TEST_INSTALLED=yes
instalar_extension_gnome gnome-ext-appindicator >/dev/null
! grep -q ' download ' "$CALLS"

: > "$CALLS"
TEST_INSTALLED=no
instalar_extension_gnome gnome-ext-appindicator >/dev/null
grep -q ' install-remote gnome-ext-appindicator$' "$CALLS"
! grep -q ' download ' "$CALLS"

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
