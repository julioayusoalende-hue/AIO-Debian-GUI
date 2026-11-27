#!/bin/bash
# Simula la selección y la instalación sin contactar repositorios ni modificar APT.
set -eo pipefail
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
version_instalada_mock=1:1.1.0
publicada=1:1.1.1~testing.32.2
paquete_instalado() { [ "$1" = aio-debian-gui ]; }
dpkg-query() { printf '%s\n' "$version_instalada_mock"; }
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
        printf 'SHA256: %s\n' "$hash_mock"
        return
    fi
    printf 'aio-debian-gui | %s | Testing\n' "$publicada"
}
dpkg-deb() {
    case "$3" in
        Package) echo aio-debian-gui ;;
        Version) echo "$publicada" ;;
        *) return 1 ;;
    esac
}
apt-get() {
    case " $* " in
        *' update '*)
            [[ " $* " == *' APT::Update::Error-Mode=any '* ]]
            ;;
        *' download '*)
            [[ "${*: -1}" == "aio-debian-gui=$publicada" ]] &&
                touch "./aio-debian-gui_all.deb"
            ;;
        *' install '*)
            [[ " $* " == *' --only-upgrade --no-remove install '*/verified/aio-debian-gui_all.deb' '* ]] &&
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
