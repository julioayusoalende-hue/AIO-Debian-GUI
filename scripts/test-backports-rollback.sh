#!/bin/bash
# Pruebas simuladas: no modifican APT, paquetes ni GRUB.
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
debian_backports_codename() { printf 'trixie\n'; }
kernel_backports_package() { printf 'linux-image-amd64\n'; }
paquete_instalado() {
    case "$1" in
        libgl1-mesa-dri|mesa-vulkan-drivers) return 0 ;;
        nvidia-driver|nvidia-kernel-dkms|nvidia-open-kernel-dkms)
            [ "${SIMULATE_NVIDIA:-0}" = 1 ] ;;
        *) return 1 ;;
    esac
}
apt-cache() {
    [ "$1" = madison ] || return 1
    case "$2" in
        linux-image-amd64|linux-headers-amd64|libgl1-mesa-dri|mesa-vulkan-drivers)
            printf '%s | 99.0~bpo13+1 | http://deb.debian.org/debian trixie-backports/main amd64 Packages\n' "$2"
            printf '%s | 6.0-1 | http://deb.debian.org/debian trixie/main amd64 Packages\n' "$2"
            printf '%s | 6.0-2 | http://security.debian.org/debian-security trixie-security/main amd64 Packages\n' "$2"
            ;;
        *) return 1 ;;
    esac
}
dpkg-query() { printf '99.0~bpo13+1'; }
apt-get() {
    if [ "${SIMULATE_REMOVAL:-0}" = 1 ]; then
        printf 'Remv essential-package [1]\n'
    else
        printf 'Inst linux-image-amd64 [99] (6.0-2 Debian:13/stable)\n'
    fi
}
dkms() { :; }

[ "$(version_stable_paquete linux-image-amd64 trixie)" = 6.0-2 ]
output=$(plan_revertir_backports)
grep -q '##STABLE:linux-image-amd64=6.0-2' <<< "$output"
grep -q '##STABLE:linux-headers-amd64=6.0-2' <<< "$output"
grep -q '##STABLE:libgl1-mesa-dri=6.0-2' <<< "$output"
if grep -q '##STABLE:.*99.0' <<< "$output"; then
    echo "✘ Selección errónea de Backports"; exit 1
fi
SIMULATE_REMOVAL=1
if plan_revertir_backports >/dev/null; then
    echo "✘ No bloqueó eliminaciones"; exit 1
fi
SIMULATE_REMOVAL=0
SIMULATE_NVIDIA=1
if plan_revertir_backports >/dev/null; then
    echo "✘ No bloqueó NVIDIA"; exit 1
fi
echo "✔ Reversión Stable: versiones, simulación, eliminación y NVIDIA"
