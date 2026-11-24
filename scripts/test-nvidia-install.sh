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
NVIDIA_POWER_CONF="$tmp/nvidia-aio-power.conf"
NVIDIA_DRACUT_CONF="$tmp/dracut/10-nvidia.conf"
EXTRA=""
nvidia_paquetes_extra() { [ -z "$EXTRA" ] || printf '%s\n' $EXTRA; }
# Driver ya instalado, equipo con una sola GPU: configura modeset y suspensión.
paso_nvidia_driver > "$tmp/out"
[ ! -s "$tmp/calls" ]
grep -qx 'options nvidia-drm modeset=1' "$NVIDIA_MODESET_CONF"
grep -qx 'options nvidia-drm fbdev=1' "$NVIDIA_MODESET_CONF"
grep -qx 'options nvidia-current NVreg_PreserveVideoMemoryAllocations=1' "$NVIDIA_POWER_CONF"
grep -qx 'options nvidia-current NVreg_TemporaryFilePath=/var/tmp' "$NVIDIA_POWER_CONF"
[ ! -e "$NVIDIA_DRACUT_CONF" ]
grep -q '##REBOOT:1' "$tmp/out"
nvidia_configuracion_ok
# Segunda ejecución: nada que hacer, sin reinicio.
paso_nvidia_driver > "$tmp/out"
if grep -q '##REBOOT' "$tmp/out"; then echo 'ERROR: reinicio innecesario'; exit 1; fi
# Híbrido (Optimus): sin PreserveVideoMemoryAllocations, como indica la wiki.
rm -f "$NVIDIA_MODESET_CONF" "$NVIDIA_POWER_CONF"
nvidia_hibrida() { return 0; }
paso_nvidia_driver > "$tmp/out"
[ -f "$NVIDIA_MODESET_CONF" ] && [ ! -e "$NVIDIA_POWER_CONF" ]
nvidia_configuracion_ok
# Falta X11 (caso AyusOS): se instala sin eliminaciones y la tarea vuelve a aparecer hasta entonces.
EXTRA="xserver-xorg"
if nvidia_configuracion_ok; then echo 'ERROR: falta xserver-xorg y se da por configurado'; exit 1; fi
: > "$tmp/calls"
paso_nvidia_driver > "$tmp/out"
grep -q -- '-s --no-remove install xserver-xorg' "$tmp/calls"
grep -q -- '--no-remove install xserver-xorg' "$tmp/calls"
grep -q '##REBOOT:1' "$tmp/out"
EXTRA=""
# dracut: incluye los ficheros de modprobe y regenera el initramfs.
dracut() { echo "dracut $*" >> "$tmp/dracut.log"; }
paquete_instalado() { [ "$1" = dracut ]; }
paso_nvidia_driver > "$tmp/out"
grep -qx 'install_items+=" /etc/modprobe.d/nvidia\* "' "$NVIDIA_DRACUT_CONF"
grep -qx 'dracut --force --kver 6.12.1-amd64' "$tmp/dracut.log"
paquete_instalado() { return 1; }
nvidia_hibrida() { return 1; }
rm -rf "$NVIDIA_MODESET_CONF" "$NVIDIA_POWER_CONF" "$tmp/dracut"
: > "$tmp/calls"
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
