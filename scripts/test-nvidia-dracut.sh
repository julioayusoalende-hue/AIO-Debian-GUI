#!/bin/bash
# Comprueba que un fallo de dracut no marca NVIDIA como configurado.
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
NVIDIA_MODESET_CONF="$tmp/modeset.conf"
NVIDIA_POWER_CONF="$tmp/power.conf"
NVIDIA_DRACUT_CONF="$tmp/dracut.conf"
NVIDIA_DRACUT_STAMP="$tmp/dracut.state"
DRACUT_STATUS=0

paquete_instalado() { [ "$1" = dracut ]; }
nvidia_hibrida() { return 0; }
nvidia_paquetes_extra() { :; }
dracut() { return "$DRACUT_STATUS"; }

if nvidia_configuracion_ok; then
    echo 'ERROR: NVIDIA se consideró configurado sin regenerar dracut' >&2
    exit 1
fi

DRACUT_STATUS=1
if nvidia_configurar_wiki; then
    echo 'ERROR: se aceptó un fallo de dracut' >&2
    exit 1
fi
[ -f "$NVIDIA_DRACUT_CONF" ]
[ ! -e "$NVIDIA_DRACUT_STAMP" ]
if nvidia_configuracion_ok; then
    echo 'ERROR: el fallo de dracut dejó la tarea como completada' >&2
    exit 1
fi

# Aunque el archivo de configuración ya coincide, debe reintentarse dracut.
DRACUT_STATUS=0
nvidia_configurar_wiki
[ -s "$NVIDIA_DRACUT_STAMP" ]
nvidia_configuracion_ok

# Un estado de otro kernel o configuración debe volver a pendiente.
printf 'otro-kernel:otra-huella\n' > "$NVIDIA_DRACUT_STAMP"
if nvidia_configuracion_ok; then
    echo 'ERROR: se aceptó un estado dracut ajeno' >&2
    exit 1
fi
nvidia_configurar_wiki
nvidia_configuracion_ok

echo '✔ NVIDIA: dracut fallido se reintenta y no marca la tarea como completada'
