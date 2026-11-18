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

# Verificación real de la función de estado con comandos simulados.
(
    paquete_instalado() { return 0; }
    dpkg-query() { printf '%s' '1:550.163.01-2'; }
    uname() { echo 6.12.1-amd64; }
    modinfo() { echo 550.163.01; }
    dkms() { echo 'nvidia-current/550.163.01, 6.12.1-amd64, x86_64: installed'; }
    nvidia_modulo_listo
    dkms() { echo 'nvidia-current/550.163.01, 6.12.1-amd64, x86_64: added'; }
    if nvidia_modulo_listo; then echo 'ERROR: DKMS no compilado aceptado'; exit 1; fi
    dkms() { echo 'nvidia-current/550.163.01, 6.11.0-amd64, x86_64: installed'; }
    if nvidia_modulo_listo; then echo 'ERROR: kernel ajeno aceptado'; exit 1; fi
    modinfo() { echo 535.1; }
    if nvidia_modulo_listo; then echo 'ERROR: módulo de otra versión aceptado'; exit 1; fi
)

# Flujo administrativo enteramente simulado: ninguna llamada real a APT/DKMS.
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
# Paquete sano: no modifica el sistema.
paso_nvidia_driver
[ ! -s "$tmp/calls" ]
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
echo '✔ NVIDIA: selección, módulo, simulación y APT sin eliminaciones'
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-nvidia-selection.py
