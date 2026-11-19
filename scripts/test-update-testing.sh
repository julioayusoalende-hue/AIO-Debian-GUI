#!/bin/bash
# Simula la selección y la instalación sin contactar repositorios ni modificar APT.
set -eo pipefail
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
version_instalada_mock=1:1.1.0
publicada=1:1.1.1~testing.32.2
paquete_instalado() { [ "$1" = aio-debian-gui ]; }
dpkg-query() { printf '%s\n' "$version_instalada_mock"; }
apt-cache() { printf 'aio-debian-gui | %s | Testing\n' "$publicada"; }
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
            [[ " $* " == *' --only-upgrade --no-remove install ./aio-debian-gui_all.deb '* ]] &&
                echo INSTALADA
            ;;
        *) return 1 ;;
    esac
}
[[ "$(actualizar_aiodebian_testing comprobar)" == "##UPDATE:1.1.0:1.1.1~testing.32.2" ]]
[[ "$(actualizar_aiodebian_testing instalar 1.1.1~testing.32.2)" == INSTALADA ]]
if actualizar_aiodebian_testing instalar 1.1.1~testing.32.1; then exit 1; fi
version_instalada_mock=1:1.1.1
[[ "$(actualizar_aiodebian_testing comprobar)" == "##NOUPDATE:1.1.1:1.1.1~testing.32.2" ]]
if actualizar_aiodebian_testing instalar 1.1.1~testing.32.2; then exit 1; fi
publicada=1:1.1.2
if actualizar_aiodebian_testing comprobar; then exit 1; fi
echo "✔ Canal Testing: selección firmada, versión confirmada y sin bajadas"
