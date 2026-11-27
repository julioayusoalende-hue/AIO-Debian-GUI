#!/bin/bash
# Actualización estable de AiO: simulación, versión aprobada y sin eliminaciones.
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
CALLS="$tmp/calls"
INSTALLED='1:1.4.4'
CANDIDATE='1:1.4.5'
MADISON=$'1:1.4.5\n1:1.4.6'
AUDIT=''
SIMULATION='Inst aio-debian-gui [1.4.4] (1.4.5 Debian:stable)'
APT_STATUS=0

reset() {
    : > "$CALLS"
    AUDIT=''
    SIMULATION='Inst aio-debian-gui [1.4.4] (1.4.5 Debian:stable)'
    APT_STATUS=0
}
paquete_instalado() { [ "$1" = aio-debian-gui ] || [ -n "${CENTRO:-}" ]; }
asegurar_listas() { echo update >> "$CALLS"; return 0; }
dpkg-query() {
    if [ "${*: -1}" = ayusos-control-center ]; then
        printf '%s' "$CENTRO"
    else
        printf '%s' "$INSTALLED"
    fi
}
timeout() { shift 2; "$@"; }
dpkg() {
    case "$1" in
        --audit) [ -z "$AUDIT" ] || printf '%s\n' "$AUDIT"; return 0 ;;
        --compare-versions) command dpkg "$@" ;;
        *) return 99 ;;
    esac
}
apt-cache() {
    case "$1" in
        policy) printf '  Candidate: %s\n' "$CANDIDATE" ;;
        madison)
            while IFS= read -r version; do
                printf ' aio-debian-gui | %s | https://example.invalid stable/main amd64 Packages\n' "$version"
            done <<< "$MADISON"
            ;;
        *) return 99 ;;
    esac
}
apt-get() {
    printf '%s\n' "$*" >> "$CALLS"
    if [[ " $* " == *' -s '* ]]; then
        printf '%s\n' "$SIMULATION"
        return 0
    fi
    return "$APT_STATUS"
}

reset
output=$(actualizar_aiodebian_estable comprobar)
[ "$output" = '##UPDATE:1.4.4:1.4.5' ]
grep -Fxq -- '-s --only-upgrade --no-remove install aio-debian-gui=1:1.4.5' "$CALLS"

CANDIDATE='1:1.4.4'
reset
output=$(actualizar_aiodebian_estable comprobar)
[ "$output" = '##NOUPDATE:1.4.4:1.4.4' ]
! grep -q -- ' -s ' "$CALLS"

CANDIDATE='1:1.4.5'
AUDIT='paquete roto'
reset
AUDIT='paquete roto'
if actualizar_aiodebian_estable comprobar >/dev/null 2>&1; then
    echo 'ERROR: se consultó actualización con dpkg pendiente' >&2
    exit 1
fi
[ ! -s "$CALLS" ]

reset
actualizar_aiodebian_estable instalar 1.4.5 >/dev/null
grep -Fq -- '--only-upgrade --no-remove install aio-debian-gui=1:1.4.5' "$CALLS"

# Aunque aparezca una versión nueva, se instala exactamente la aprobada.
CANDIDATE='1:1.4.6'
reset
actualizar_aiodebian_estable instalar 1.4.5 >/dev/null
grep -Fq -- '--only-upgrade --no-remove install aio-debian-gui=1:1.4.5' "$CALLS"
! grep -Fq 'aio-debian-gui=1:1.4.6' "$CALLS"

# Una versión retirada o ambigua no se instala.
MADISON='1:1.4.6'
reset
if actualizar_aiodebian_estable instalar 1.4.5 >/dev/null 2>&1; then
    echo 'ERROR: se instaló una versión aprobada ya retirada' >&2
    exit 1
fi
! grep -Fq -- '--only-upgrade --no-remove install' "$CALLS"

MADISON=$'1:1.4.5\n2:1.4.5'
reset
if actualizar_aiodebian_estable instalar 1.4.5 >/dev/null 2>&1; then
    echo 'ERROR: se aceptó una versión ambigua' >&2
    exit 1
fi

# APT nunca puede eliminar paquetes en una autoactualización.
MADISON='1:1.4.5'
SIMULATION='Remv other-package [1]'
reset
SIMULATION='Remv other-package [1]'
if actualizar_aiodebian_estable instalar 1.4.5 >/dev/null 2>&1; then
    echo 'ERROR: se aceptó una actualización con eliminaciones' >&2
    exit 1
fi
! grep -Fq -- '--only-upgrade --no-remove install' "$CALLS"

# Tampoco se permite rebajar de versión.
INSTALLED='1:1.4.5'
reset
if actualizar_aiodebian_estable instalar 1.4.4 >/dev/null 2>&1; then
    echo 'ERROR: se permitió una rebajada de AiO' >&2
    exit 1
fi

echo '✔ Autoactualización estable: dpkg, simulación, versión aprobada y sin eliminaciones'


CENTRO=1.4.4
INSTALLED=1:1.4.5
CANDIDATE=$INSTALLED
reset
output=$(actualizar_aiodebian_estable comprobar)
[[ "$output" == *"##AYUSOS-UPDATE:1.4.4:1.4.5"* ]]
actualizar_aiodebian_estable instalar 1.4.5 >/dev/null
grep -Fxq -- '-s --only-upgrade --no-remove install aio-debian-gui=1:1.4.5 ayusos-control-center=1.4.5' "$CALLS"
grep -Fq -- '--only-upgrade --no-remove install aio-debian-gui=1:1.4.5 ayusos-control-center=1.4.5' "$CALLS"

CENTRO=1.4.6
reset
[[ "$(actualizar_aiodebian_estable comprobar)" == '##NOUPDATE:1.4.5:1.4.5' ]]
! grep -Fq 'ayusos-control-center=' "$CALLS"
echo '✔ Estable: el Centro de Control se actualiza en la misma transacción y no se rebaja'
