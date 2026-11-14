#!/usr/bin/env bash
# Prueba no privilegiada: PCI NVIDIA y detección de equipo híbrido.
set -euo pipefail
cd "$(dirname "$0")/.."
HELPER=package/usr/lib/aio-debian-gui/aio-debian-gui-helper
if [ "$EUID" -eq 0 ]; then
    echo "Omitido: la simulación PCI no se permite con root."
    exit 0
fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
source "$HELPER"
export AIO_TEST_PCI_ROOT="$tmp"
mkdir -p "$tmp/0000:01:00.0" "$tmp/0000:00:02.0"
printf '%s\n' 0x10de > "$tmp/0000:01:00.0/vendor"
printf '%s\n' 0x030200 > "$tmp/0000:01:00.0/class"
printf '%s\n' 0x8086 > "$tmp/0000:00:02.0/vendor"
printf '%s\n' 0x030000 > "$tmp/0000:00:02.0/class"
nvidia_presente
nvidia_hibrida
result=$(nvidia_report)
grep -Fqx '##NVIDIA:present:1' <<< "$result"
grep -Fqx '##NVIDIA:hybrid:1' <<< "$result"
rm -rf "$tmp/0000:00:02.0"
nvidia_presente
if nvidia_hibrida; then
    echo 'ERROR: una sola NVIDIA no es híbrida' >&2; exit 1
fi
rm -rf "$tmp/0000:01:00.0"
if nvidia_presente; then
    echo 'ERROR: GPU NVIDIA ausente' >&2; exit 1
fi
leer_distribucion() { echo debian; }
if paso_nvidia_driver; then
    echo 'ERROR: permite instalar sin GPU NVIDIA' >&2; exit 1
fi
echo '✔ NVIDIA: PCI, híbrida y bloqueo sin GPU'
