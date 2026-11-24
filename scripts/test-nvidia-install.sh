#!/usr/bin/env bash
# Pruebas sin privilegios y sin cambios en APT: los comandos están simulados.
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
# Verificación real de la función de estado con comandos simulados.
(
    paquete_instalado() { return 0; }
    dpkg-query() { printf '%s' '1:550.163.01-2'; }
    uname() { echo 6.12.1-amd64; }
    modinfo() { echo 550.163.01; }
    dkms() { echo 'nvidia-current/550.163.01, 6.12.1-amd64, x86_64: installed'; }
    nvidia_modulo_listo
    dkms() { echo 'nvidia-current/550.163.01, 6.12.1-amd64, x86_64: installed (original_module exists)'; }
    nvidia_modulo_listo || { echo 'ERROR: installed con nota rechazado'; exit 1; }
    dkms() { echo 'nvidia-current/550.163.01, 6.12.1-amd64, x86_64: installed-weak'; }
    if nvidia_modulo_listo; then echo 'ERROR: estado desconocido aceptado'; exit 1; fi
    dkms() { echo 'nvidia-current/550.163.01, 6.12.1-amd64, x86_64: added'; }
    if nvidia_modulo_listo; then echo 'ERROR: DKMS no compilado aceptado'; exit 1; fi
    dkms() { echo 'nvidia-current/550.163.01, 6.11.0-amd64, x86_64: installed'; }
    if nvidia_modulo_listo; then echo 'ERROR: kernel ajeno aceptado'; exit 1; fi
    modinfo() { [ "${!#}" = nvidia-current ] && echo 550.163.01 || return 1; }
    dkms() { echo 'nvidia-current/550.163.01, 6.12.1-amd64, x86_64: installed'; }
    nvidia_modulo_listo || { echo 'ERROR: módulo nvidia-current de Debian rechazado'; exit 1; }
    modinfo() { return 1; }
    if nvidia_modulo_listo; then echo 'ERROR: módulo inexistente aceptado'; exit 1; fi
    modinfo() { echo 535.1; }
    if nvidia_modulo_listo; then echo 'ERROR: módulo de otra versión aceptado'; exit 1; fi
)

# Flujo administrativo enteramente simulado: ninguna llamada real a APT/DKMS.
leer_distribucion() { echo debian; }
nvidia_presente() { return 0; }
nvidia_hibrida() { return 1; }
READY=1
nvidia_modulo_listo() { [ "$READY" = 1 ]; }
SECURE=desactivado
nvidia_secure_boot() { echo "$SECURE"; }
paquete_instalado() { return 1; }
asegurar_listas() { return 0; }
SELECT_OK=1
nvidia_elegir_modulo() { [ "$SELECT_OK" = 1 ] || return 1; echo nvidia-kernel-dkms; }
uname() { echo 6.12.1-amd64; }
apt-cache() {
    case "$1" in
        policy) echo 'Candidate: 550.163.01-2' ;;
        show) echo ' Building the kernel module has been tested up to Linux 6.12.' ;;
        *) return 1 ;;
    esac
}
: > "$tmp/calls"
SIMULATION='Inst nvidia-driver (550.163.01-2 Debian:stable)'
SIM_STATUS=0
INSTALL_STATUS=0
apt-get() {
    echo "$*" >> "$tmp/calls"
    [[ " $* " == *' --no-remove '* ]] || return 99
    if [[ " $* " == *' -s '* ]]; then
        echo "$SIMULATION"; return "$SIM_STATUS"
    fi
    READY=1
    return "$INSTALL_STATUS"
}
NVIDIA_MODESET_CONF="$tmp/nvidia-modeset.conf"
update-initramfs() { echo "initramfs $*" >> "$tmp/initramfs"; }
# Paquete sano sin modesetting: solo escribe la opción y regenera el initramfs.
paso_nvidia_driver > "$tmp/out"
[ ! -s "$tmp/calls" ]
grep -qx 'options nvidia-drm modeset=1' "$NVIDIA_MODESET_CONF"
grep -qx 'initramfs -u -k 6.12.1-amd64' "$tmp/initramfs"
grep -q '##REBOOT:1' "$tmp/out"
# Segunda ejecución: ya configurado, no toca nada ni pide reiniciar.
: > "$tmp/initramfs"
paso_nvidia_driver > "$tmp/out"
[ ! -s "$tmp/initramfs" ]
if grep -q '##REBOOT' "$tmp/out"; then echo 'ERROR: reinicio innecesario'; exit 1; fi
# Fallo del initramfs: la tarea falla.
rm -f "$NVIDIA_MODESET_CONF"
update-initramfs() { return 1; }
if paso_nvidia_driver >/dev/null 2>&1; then echo 'ERROR: fallo de initramfs ignorado'; exit 1; fi
update-initramfs() { echo "initramfs $*" >> "$tmp/initramfs"; }
rm -f "$NVIDIA_MODESET_CONF"
# Paquete ausente o incompleto: selección, simulación e instalación protegida.
READY=0
paso_nvidia_driver
[ "$(wc -l < "$tmp/calls")" -eq 2 ]
grep -q -- 'nvidia-driver=550.163.01-2 nvidia-kernel-dkms=550.163.01-2' "$tmp/calls"
for SIMULATION in 'Remv desktop [1]' 'Purg desktop [1]'; do
    READY=0; : > "$tmp/calls"
    if paso_nvidia_driver; then echo 'ERROR: permite eliminaciones'; exit 1; fi
    [ "$(wc -l < "$tmp/calls")" -eq 1 ]
done
SIMULATION='Inst nvidia-driver (550.163.01-2 Debian:stable)'
READY=0; INSTALL_STATUS=100
if paso_nvidia_driver; then echo 'ERROR: ignora fallo de instalación'; exit 1; fi
READY=0; SELECT_OK=0; : > "$tmp/calls"
if paso_nvidia_driver; then echo 'ERROR: instala sin soporte PCI'; exit 1; fi
[ ! -s "$tmp/calls" ]
SELECT_OK=1; SECURE=desconocido
if paso_nvidia_driver; then echo 'ERROR: permite Secure Boot desconocido'; exit 1; fi
[ ! -s "$tmp/calls" ]
# mokutil: en EFI se instala si falta; sin EFI o ya presente, no se toca nada.
SECURE=desactivado; READY=0; INSTALL_STATUS=0
mkdir "$tmp/efi"
HAY_MOKUTIL=0
command() { if [ "$1" = -v ] && [ "$2" = mokutil ]; then [ "$HAY_MOKUTIL" = 1 ]; else builtin command "$@"; fi; }
apt-get() {
    echo "$*" >> "$tmp/calls"
    [[ " $* " == *' --no-remove '* ]] || return 99
    [[ " $* " == *' install mokutil'* ]] && { HAY_MOKUTIL=1; return "$INSTALL_STATUS"; }
    if [[ " $* " == *' -s '* ]]; then echo "$SIMULATION"; return "$SIM_STATUS"; fi
    READY=1; return "$INSTALL_STATUS"
}
EFI_DIR="$tmp/efi"; : > "$tmp/calls"
paso_nvidia_driver
grep -q -- 'install mokutil' "$tmp/calls"
HAY_MOKUTIL=0; READY=0; INSTALL_STATUS=100; : > "$tmp/calls"
if paso_nvidia_driver; then echo 'ERROR: sigue sin mokutil'; exit 1; fi
[ "$(wc -l < "$tmp/calls")" -eq 1 ]
INSTALL_STATUS=0; HAY_MOKUTIL=1; READY=0; : > "$tmp/calls"
paso_nvidia_driver
! grep -q -- 'install mokutil' "$tmp/calls"
HAY_MOKUTIL=0; READY=0; EFI_DIR="$tmp/sin-efi"; : > "$tmp/calls"
paso_nvidia_driver
! grep -q -- 'install mokutil' "$tmp/calls"
unset EFI_DIR
echo '✔ NVIDIA: selección, módulo, simulación y APT sin eliminaciones'
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-nvidia-selection.py
