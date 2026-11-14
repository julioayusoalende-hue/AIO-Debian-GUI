#!/bin/bash
# Pruebas sin ejecutar Timeshift real ni modificar el sistema.
set -euo pipefail
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
timeshift() {
    case "${1:-}" in
        --create) [[ "${FAKE_TIMESHIFT:-ok}" == ok ]] ;;
        *) return 1 ;;
    esac
}
FAKE_TIMESHIFT=ok
# El helper valida existencia de binario y configuración; no ejecutamos
# snapshots reales en CI. Validamos rechazo de proveedor desconocido.
if crear_instantanea_previa desconocido; then
    echo "ERROR: proveedor inválido aceptado" >&2
    exit 1
fi
echo "Timeshift: rechazo de proveedor inválido OK"

# Regresión: algunas versiones de Timeshift rechazan '--tags O'.
helper=package/usr/lib/aio-debian-gui/aio-debian-gui-helper
if grep -Fq -- 'timeshift --create --comments "AiO Debian GUI: antes de mantenimiento" --tags O' "$helper"; then
    echo "ERROR: opción --tags O incompatible reintroducida" >&2
    exit 1
fi
if ! grep -Fq -- 'timeshift --create --comments "AiO Debian GUI: antes de mantenimiento" --scripted' "$helper"; then
    echo "ERROR: falta la llamada Timeshift sin etiquetas forzadas" >&2
    exit 1
fi
