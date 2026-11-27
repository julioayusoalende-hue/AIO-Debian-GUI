#!/bin/bash
# Simula la selección y la instalación sin contactar repositorios ni modificar APT.
set -eo pipefail
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
version_instalada_mock=1:1.1.0
publicada=1:1.1.1~testing.32.2
paquete_instalado() { [ "$1" = aio-debian-gui ] || [ -n "${centro_mock:-}" ]; }
dpkg-query() {
    if [ "${*: -1}" = ayusos-control-center ]; then
        printf '%s\n' "$centro_mock"
    else
        printf '%s\n' "$version_instalada_mock"
    fi
}
auditoria_mock=
timeout() { printf '%s' "$auditoria_mock"; }
dpkg() {
    case "$1" in
        --audit) [ -z "$auditoria_mock" ] || printf '%s\n' "$auditoria_mock"; return 0 ;;
        *) command dpkg "$@" ;;
    esac
}
hash_mock=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
apt-cache() {
    if [[ " $* " == *' show '* ]]; then
        if [[ "${*: -1}" == ayusos-control-center=* ]]; then
            [ -z "${falta_centro:-}" ] || return 0
            printf 'SHA256: %s\n' "$hash_centro_mock"
        else
            printf 'SHA256: %s\n' "$hash_mock"
        fi
        return
    fi
    printf 'aio-debian-gui | %s | Testing\n' "$publicada"
}
dpkg-deb() {
    local paquete
    paquete=$(basename "$2" _all.deb)
    case "$3" in
        Package) echo "$paquete" ;;
        Version) if [ "$paquete" = ayusos-control-center ]; then echo "${publicada#*:}"; else echo "$publicada"; fi ;;
        *) return 1 ;;
    esac
}
apt-get() {
    case " $* " in
        *' update '*)
            [[ " $* " == *' APT::Update::Error-Mode=any '* ]]
            ;;
        *' download '*)
            [[ " $* " == *" aio-debian-gui=$publicada "* ]] || return 1
            touch "./aio-debian-gui_all.deb"
            if [[ " $* " == *" ayusos-control-center=${publicada#*:} "* ]]; then
                touch "./ayusos-control-center_all.deb"
            fi
            ;;
        *' install '*)
            [[ " $* " == *' --only-upgrade --no-remove install '*/verified/aio-debian-gui_all.deb' '* ]] || return 1
            if [ -n "${centro_mock:-}" ]; then
                [[ "${*: -1}" == */verified/ayusos-control-center_all.deb ]] || return 1
            fi
            echo INSTALADA
            ;;
        *) return 1 ;;
    esac
}
[[ "$(actualizar_aiodebian_testing comprobar)" == "##UPDATE:1.1.0:1.1.1~testing.32.2" ]]
[[ "$(actualizar_aiodebian_testing instalar 1.1.1~testing.32.2)" == INSTALADA ]]
auditoria_mock="grub-pc requiere configuración"
if actualizar_aiodebian_testing instalar 1.1.1~testing.32.2; then exit 1; fi
auditoria_mock=
hash_valido=$hash_mock
hash_mock=${hash_mock//e/a}
if actualizar_aiodebian_testing instalar 1.1.1~testing.32.2; then exit 1; fi
hash_mock=$hash_valido
if actualizar_aiodebian_testing instalar 1.1.1~testing.32.1; then exit 1; fi
version_instalada_mock=1:1.1.1
[[ "$(actualizar_aiodebian_testing comprobar)" == "##NOUPDATE:1.1.1:1.1.1~testing.32.2" ]]
if actualizar_aiodebian_testing instalar 1.1.1~testing.32.2; then exit 1; fi
publicada=1:1.1.2
if actualizar_aiodebian_testing comprobar; then exit 1; fi
echo "✔ Canal Testing: selección firmada, versión confirmada y sin bajadas"


publicada=1:1.1.1~testing.32.2
version_instalada_mock=$publicada
centro_mock=1.1.0
hash_centro_mock=$hash_mock
output=$(actualizar_aiodebian_testing comprobar)
[[ "$output" == *'##AYUSOS-UPDATE:1.1.0:1.1.1~testing.32.2'* ]]
output=$(actualizar_aiodebian_testing instalar 1.1.1~testing.32.2)
[[ "$output" == $'INSTALADA\n##AYUSOS-UPDATED' ]]
hash_centro_mock=${hash_mock//e/a}
if actualizar_aiodebian_testing instalar 1.1.1~testing.32.2; then exit 1; fi
falta_centro=1
if actualizar_aiodebian_testing comprobar; then exit 1; fi
echo '✔ Testing: ambos paquetes verificados e instalados juntos'
