#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
TEST_DIR=$(mktemp -d)
trap 'rm -rf -- "$TEST_DIR"' EXIT

INSTALLED=0
UPDATE_STATUS=0
INSTALL_STATUS=0
paquete_instalado() {
    [ "$INSTALLED" -eq 1 ] && [ "$1" = "$EXPECTED_PACKAGE" ]
}
asegurar_listas() {
    echo update >> "$TEST_DIR/calls"
    return "$UPDATE_STATUS"
}
apt-get() {
    printf '%s\n' "$*" >> "$TEST_DIR/calls"
    return "$INSTALL_STATUS"
}

for app in timeshift deja-dup; do
    case "$app" in
        timeshift) EXPECTED_PACKAGE=timeshift ;;
        deja-dup) EXPECTED_PACKAGE=deja-dup ;;
    esac
    : > "$TEST_DIR/calls"
    INSTALLED=1
    output=$(instalar_aplicacion_backup "$app")
    [[ "$output" == "##BACKUP:installed:$app" ]]
    [ ! -s "$TEST_DIR/calls" ]

    : > "$TEST_DIR/calls"
    INSTALLED=0
    UPDATE_STATUS=0
    INSTALL_STATUS=0
    apt-get() {
        printf '%s\n' "$*" >> "$TEST_DIR/calls"
        [[ " $* " == *" --no-remove install $EXPECTED_PACKAGE "* ]]
        INSTALLED=1
        return "$INSTALL_STATUS"
    }
    output=$(instalar_aplicacion_backup "$app")
    [[ "$output" == *"##BACKUP:installed:$app" ]]
    grep -Fxq 'update' "$TEST_DIR/calls"
    grep -Fq -- "--no-remove install $EXPECTED_PACKAGE" "$TEST_DIR/calls"
done

if output=$(instalar_aplicacion_backup arbitrary 2>&1); then
    echo "ERROR: se aceptó una aplicación fuera de la lista permitida" >&2
    exit 1
fi

INSTALLED=0
paquete_instalado() { return 1; }
asegurar_listas() { return 1; }
if instalar_aplicacion_backup timeshift >/dev/null 2>&1; then
    echo "ERROR: se aceptó un fallo al actualizar índices" >&2
    exit 1
fi

echo "✔ Instalación autorizada y limitada a Timeshift y Déjà Dup"
