#!/bin/bash
# run_privileged() debe reutilizar el lock ya tomado por main()/programador.
set -euo pipefail
cd "$(dirname "$0")/.."

HELPER=package/usr/lib/aio-debian-gui/aio-debian-gui-helper

if ! command -v unshare >/dev/null || ! unshare --user --map-root-user true 2>/dev/null; then
    echo "- namespace de usuario no disponible: se omite la prueba de lock privilegiado"
    exit 0
fi

TEST_DIR=$(mktemp -d)
trap 'rm -rf -- "$TEST_DIR"' EXIT
export TEST_LOCK="$TEST_DIR/maintenance.lock"

# unshare activa la rama de root sin escribir en /run ni modificar el sistema.
unshare --user --map-root-user bash -c '
    source "$1"
    MAINTENANCE_LOCK="$TEST_LOCK"

    # main() ya tiene el lock en el fd 9: no debe interpretarse como ajeno.
    exec 9>"$MAINTENANCE_LOCK"
    flock -n 9
    AIO_PRIV_LOCK_FD=9
    salida=$(run_privileged "dpkg-audit" 0 true 2>&1) || {
        echo "ERROR: se rechazó el propio lock: $salida" >&2
        exit 1
    }
    [[ "$salida" != *"ya hay otra operación"* ]] || {
        echo "ERROR: falso bloqueo con el lock propio: $salida" >&2
        exit 1
    }

    # El descriptor compartido sigue bloqueado después de la operación.
    exec {otro}>"$MAINTENANCE_LOCK"
    if flock -n "$otro"; then
        echo "ERROR: run_privileged liberó el lock compartido" >&2
        exit 1
    fi

    # Sin el descriptor compartido, un lock ajeno sí debe rechazarse.
    AIO_PRIV_LOCK_FD=""
    if salida=$(run_privileged "dpkg-audit" 0 true 2>&1); then
        echo "ERROR: se ignoró un lock ajeno" >&2
        exit 1
    fi
    [[ "$salida" == *"ya hay otra operación"* ]] || {
        echo "ERROR: no se detectó el lock ajeno: $salida" >&2
        exit 1
    }

    # Al cerrar el descriptor de main() el lock queda libre.
    exec 9>&-
    flock -n "$otro" || { echo "ERROR: el lock no se liberó" >&2; exit 1; }
    exec {otro}>&-

    # Un hijo que sobreviva al timeout puede seguir trabajando con el lock.
    marker="${MAINTENANCE_LOCK}.timeout-marker"
    codigo=0
    run_privileged "timeout-test" 1 bash -c "sleep 2 && touch -- \"\$1\" & wait" _ "$marker" || codigo=$?
    [[ "$codigo" = 124 ]] || { echo "ERROR: código inesperado tras el timeout: $codigo" >&2; exit 1; }
    sleep 2
    [[ ! -e "$marker" ]] || { echo "ERROR: el hijo sobrevivió al timeout" >&2; exit 1; }
    exec {otro}>"$MAINTENANCE_LOCK"
    flock -n "$otro" || { echo "ERROR: el timeout dejó el lock ocupado" >&2; exit 1; }
' _ "$HELPER"

echo "✔ lock privilegiado compartido sin falsos bloqueos"

# La cadena normal sigue el orden APT y no repite auditorías ni simulaciones.
unshare --user --map-root-user bash -c '
    set -euo pipefail
    source "$1"
    MAINTENANCE_LOCK="$TEST_LOCK"
    llamadas="$TEST_LOCK.calls"
    distribucion_soportada() { return 0; }
    leer_distribucion() { printf "%s\n" debian; }
    paquete_instalado() { return 1; }
    run_privileged() {
        printf "%s\n" "$1" >> "$llamadas"
        case "$1" in
            dpkg-configure-pending)
                [ "$2" -eq 0 ] && [[ "${*:3}" == "dpkg --force-confdef --force-confold --configure -a" ]] || return 2
                [ "$estado" != reparacion-falla ]
                return $? ;;
            apt-upgrade)
                [[ " $* " == *" DPkg::Lock::Timeout=120 "* ]] || return 2
                case "$estado" in
                    ocupado)
                        echo "E: Could not get lock /var/lib/dpkg/lock-frontend."
                        return 100 ;;
                    interrumpido|reparacion-falla|reintento-falla)
                        if [ "$(grep -Fxc apt-upgrade "$llamadas")" -eq 1 ] || [ "$estado" = reintento-falla ]; then
                            echo "E: dpkg was interrupted, you must manually run dpkg --configure -a to correct the problem."
                            return 100
                        fi ;;
                esac ;;
        esac
        return 0
    }
    for estado in normal ocupado interrumpido reparacion-falla reintento-falla; do
        : > "$llamadas"
        codigo=0
        (exec 9>"$MAINTENANCE_LOCK"; main --lock-fd 9 upgrade autoremove autoclean) || codigo=$?
        case "$estado" in
            normal|interrumpido) [ "$codigo" -eq 0 ] ;;
            *) [ "$codigo" -eq 1 ] ;;
        esac
        case "$estado" in
            normal) esperado=$(printf "%s\n" apt-update apt-upgrade apt-autoremove---no-purge apt-autoclean) ;;
            ocupado) esperado=$(printf "%s\n" apt-update apt-upgrade) ;;
            interrumpido) esperado=$(printf "%s\n" apt-update apt-upgrade dpkg-configure-pending apt-upgrade apt-autoremove---no-purge apt-autoclean) ;;
            reparacion-falla) esperado=$(printf "%s\n" apt-update apt-upgrade dpkg-configure-pending) ;;
            reintento-falla) esperado=$(printf "%s\n" apt-update apt-upgrade dpkg-configure-pending apt-upgrade) ;;
        esac
        [ "$(cat "$llamadas")" = "$esperado" ]
    done
' _ "$HELPER"
echo "✔ cadena APT: espera de bloqueos, recuperación de dpkg y un solo reintento"
