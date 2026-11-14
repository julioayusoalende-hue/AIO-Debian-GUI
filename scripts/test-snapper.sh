#!/bin/bash
# Pruebas aisladas: jamás se invoca Snapper real.
set -euo pipefail
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
findmnt() {
    if [[ "$*" == *FSTYPE* ]]; then printf '%s\n' "${FAKE_FS:-btrfs}"
    else printf '%s\n' "${FAKE_TARGET:-/}"; fi
}
snapper() {
    case "${1:-}" in
        -c) [[ "${FAKE_SNAPPER:-ok}" == ok ]] ;;
        *) return 1 ;;
    esac
}
FAKE_FS=ext4
if crear_instantanea_previa; then echo "ERROR: ext4 aceptado"; exit 1; fi
FAKE_FS=btrfs FAKE_TARGET=/otro
if crear_instantanea_previa; then echo "ERROR: montaje ajeno aceptado"; exit 1; fi
FAKE_TARGET=/ FAKE_SNAPPER=fail
if crear_instantanea_previa; then echo "ERROR: Snapper fallido aceptado"; exit 1; fi
FAKE_SNAPPER=ok
crear_instantanea_previa
echo "Snapper: casos positivos y negativos OK"
