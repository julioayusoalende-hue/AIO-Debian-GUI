#!/bin/bash
# Instalar copias persistentes sin tocar el anfitrión.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
TEMP=$(mktemp -d)
trap 'rm -rf "$TEMP"' EXIT
mkdir -p "$TEMP/bundle/aio_core" "$TEMP/host"
cp package/usr/lib/aio-debian-gui/aio-debian-gui-helper "$TEMP/bundle/"
cp package/usr/lib/aio-debian-gui/aio_core/scheduler.py "$TEMP/bundle/aio_core/"
cp package/usr/lib/systemd/system/*.service "$TEMP/bundle/"
cp package/usr/share/polkit-1/actions/es.aiodebian.gui.policy "$TEMP/bundle/"
source "$TEMP/bundle/aio-debian-gui-helper"
SYSTEM_HELPER="$TEMP/host/helper"
SYSTEM_POLICY="$TEMP/host/policy"
SCHEDULER_MODULE="$TEMP/host/aio_core/scheduler.py"
SCHEDULER_SERVICE="$TEMP/host/service"
paquete_instalado() { return 1; }
# Exercise real install, replacing only root ownership for unprivileged CI.
install() {
    local args=()
    while [ "$#" -gt 0 ]; do
        case "$1" in -o|-g) shift 2;; *) args+=("$1"); shift;; esac
    done
    command install "${args[@]}"
}
systemctl() { [ "$*" = daemon-reload ]; }
instalar_programador
instalar_programador # Idempotente.
cmp "$SYSTEM_HELPER" "$TEMP/bundle/aio-debian-gui-helper"
cmp "$SCHEDULER_MODULE" "$TEMP/bundle/aio_core/scheduler.py"
cmp "$SCHEDULER_SERVICE" "$TEMP/bundle/aio-debian-gui-maintenance@.service"
paquete_instalado() { return 0; }
printf '\n# Different DEB\n' >> "$SCHEDULER_MODULE"
if instalar_programador; then exit 1; fi
rm "$TEMP/bundle/aio_core/scheduler.py"
if instalar_programador; then exit 1; fi
echo 'Integración sin DEB: instalación, repetición, conflicto y componentes ausentes OK'
