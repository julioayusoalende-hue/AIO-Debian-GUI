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

for app in btop celluloid deluge gimp handbrake htop kitty qbittorrent vlc; do
    EXPECTED_PACKAGE="$app"
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

echo "✔ Instalación APT recomendada limitada a los paquetes autorizados"

ubuntu_compatible_con_ghostty() { return 1; }
if instalar_aplicacion_recomendada ghostty >/dev/null 2>&1; then
    echo "ERROR: Ghostty via APT was accepted on an unsupported distribution" >&2
    exit 1
fi

ubuntu_compatible_con_ghostty() { return 0; }
EXPECTED_PACKAGE=ghostty
INSTALLED=0
apt-get() {
    [[ " $* " == *" --no-remove install ghostty "* ]]
    local opcion
    for opcion in "$@"; do
        if [[ "$opcion" == Dir::Etc::Preferences=* ]]; then
            grep -Fxq 'Pin: release o=Ubuntu' "${opcion#*=}"
            grep -Fxq 'Pin-Priority: -1' "${opcion#*=}"
            touch "$TEST_DIR/installed"
            return 0
        fi
    done
    return 1
}
output=$(instalar_aplicacion_recomendada ghostty)
[[ "$output" == *"##RECOMMENDED:installed:ghostty" ]]
echo "✔ Ghostty se limita al origen de Ubuntu en APT"
