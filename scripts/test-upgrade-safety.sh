#!/bin/bash
# Todas las operaciones APT están simuladas; nunca se modifica el sistema.
set -euo pipefail
cd "$(dirname "$0")/.."
(
    set -- --review-cleanup
    source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
    [ -n "${_aio_review_fd:-}" ] && [ -e "/proc/self/fd/$_aio_review_fd" ]
)
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
TEST_DIR=$(mktemp -d)
trap 'rm -rf -- "$TEST_DIR"' EXIT
PLAN='Inst nano [7.2] (7.3 Debian:stable)'
UPGRADE_PLAN=$(python3 -c 'import hashlib, sys; print(hashlib.sha256((sys.argv[1]+"\n").encode()).hexdigest())' "$PLAN")
SIMULATION="$PLAN"
SIMULATION_STATUS=0
UPDATE_STATUS=0
INSTALL_STATUS=0
(
    apt-get() { [ "$*" = '--error-on=any update' ]; }
    asegurar_listas
    [ "$LISTAS_ACTUALIZADAS" -eq 1 ]
)
(
    apt-get() { return 100; }
    if asegurar_listas; then echo 'ERROR: se aceptó un fallo parcial de índices'; exit 1; fi
    [ "$LISTAS_ACTUALIZADAS" -eq 0 ]
)
asegurar_listas() { echo update >> "$TEST_DIR/calls"; return "$UPDATE_STATUS"; }
apt-get() {
    printf '%s\n' "$*" >> "$TEST_DIR/calls"
    if [[ " $* " == *" -s "* ]]; then
        printf '%s\n' "$SIMULATION"
        return "$SIMULATION_STATUS"
    fi
    return "$INSTALL_STATUS"
}
reset_calls() { : > "$TEST_DIR/calls"; }
assert_no_install() {
    if grep -qE '^-y .*upgrade --with-new-pkgs --no-remove$' "$TEST_DIR/calls"; then
        echo 'ERROR: se ejecutó APT pese al rechazo del plan'; exit 1
    fi
}

# El diagnóstico solo refresca índices y considera error los fallos parciales.
(
    timeout() {
        [ "$*" = '--kill-after=10s 180s apt-get -o APT::Update::Error-Mode=any update' ]
    }
    output=$(refrescar_indices_diagnostico)
    [[ "$output" == *'##DIAGNOSTIC_APT:updated'* ]]
)
(
    timeout() { return 100; }
    if output=$(refrescar_indices_diagnostico); then echo 'ERROR: índices fallidos aceptados'; exit 1; fi
    [[ "$output" != *'##DIAGNOSTIC_APT:updated'* ]]
)

reset_calls
paso_upgrade
[ "$(head -n 1 "$TEST_DIR/calls")" = update ]
grep -q -- '^-s -o Debug::NoLocking=1 upgrade --with-new-pkgs --no-remove$' "$TEST_DIR/calls"
grep -qE '^-y .*upgrade --with-new-pkgs --no-remove$' "$TEST_DIR/calls"

for SIMULATION in 'Remv old-package [1]' 'Purg old-package [1]' 'Inst nano [7.2] (7.4 Debian:stable)'; do
    reset_calls
    if paso_upgrade; then echo 'ERROR: cambio de plan aceptado'; exit 1; fi
    assert_no_install
done
SIMULATION="$PLAN"
SIMULATION_STATUS=1
reset_calls
if paso_upgrade; then echo 'ERROR: simulación fallida aceptada'; exit 1; fi
assert_no_install
SIMULATION_STATUS=0
UPDATE_STATUS=1
reset_calls
if paso_upgrade; then echo 'ERROR: índices fallidos aceptados'; exit 1; fi
[ "$(wc -l < "$TEST_DIR/calls")" -eq 1 ]
UPDATE_STATUS=0
INSTALL_STATUS=1
if paso_upgrade; then echo 'ERROR: fallo real de APT ignorado'; exit 1; fi

# Una actualización rutinaria nunca autoriza eliminaciones.
UPGRADE_PLAN=''
INSTALL_STATUS=0
SIMULATION='Remv old-package [1]'
reset_calls
if paso_upgrade; then echo 'ERROR: se aceptó una eliminación durante upgrade'; exit 1; fi
assert_no_install

# La limpieza requiere el mismo plan que aprobó el usuario.
paquete_instalado() { return 1; }
AUTOREMOVE_PLAN=$(huella_plan_apt <<< "$SIMULATION")
reset_calls
paso_autoremove
grep -Fxq -- '-s -o Debug::NoLocking=1 autoremove --no-purge' "$TEST_DIR/calls"
grep -qE '^-y .*autoremove --no-purge$' "$TEST_DIR/calls"
for SIMULATION in 'Remv other-package [1]' 'Remv old-package [2]' ''; do
    reset_calls
    if paso_autoremove; then echo 'ERROR: se aceptó una limpieza distinta'; exit 1; fi
    if grep -qE '^-y .*autoremove --no-purge$' "$TEST_DIR/calls"; then
        echo 'ERROR: se ejecutó la limpieza pese al rechazo del plan'; exit 1
    fi
done
AUTOREMOVE_PLAN=''
reset_calls
if paso_autoremove; then echo 'ERROR: se limpió sin plan aprobado'; exit 1; fi

SIMULATION='Purg old-package [1]'
AUTOREMOVE_PLAN=$(huella_plan_apt <<< "$SIMULATION")
reset_calls
paso_autopurge
grep -Fxq -- '-s -o Debug::NoLocking=1 autoremove --purge' "$TEST_DIR/calls"
grep -qE '^-y .*autoremove --purge$' "$TEST_DIR/calls"
SIMULATION='Purg other-package [1]'
reset_calls
if paso_autopurge; then echo 'ERROR: se aceptó una purga distinta'; exit 1; fi
if grep -qE '^-y .*autoremove --purge$' "$TEST_DIR/calls"; then
    echo 'ERROR: se ejecutó una purga sin aprobar'; exit 1
fi

# La GUI puede aprobar una nueva lista sin reiniciar el mantenimiento.
REVISAR_LIMPIEZA=1
AUTOREMOVE_PLAN=$(huella_plan_apt <<< 'Purg old-package [1]')
SIMULATION='Purg another-package [1]'
UPDATED_PLAN=$(huella_plan_apt <<< "$SIMULATION")
reset_calls
output=$(paso_autopurge 8<<< "$UPDATED_PLAN")
[[ "$output" == *"##CLEANUP-REVIEW:--purge:$UPDATED_PLAN:"* ]]
grep -qE '^-y .*autoremove --purge$' "$TEST_DIR/calls"
reset_calls
result=0
output=$(paso_autopurge 8<<< omitir) || result=$?
[ "$result" -eq 3 ]
if grep -qE '^-y .*autoremove --purge$' "$TEST_DIR/calls"; then
    echo 'ERROR: se aplicó la purga omitida'; exit 1
fi
SIMULATION=''
reset_calls
output=$(paso_autopurge </dev/null)
[[ "$output" == *'No quedan dependencias huérfanas'* ]]
if grep -qE '^-y .*autoremove --purge$' "$TEST_DIR/calls"; then
    echo 'ERROR: se ejecutó una purga vacía'; exit 1
fi

# La comprobación no debe anunciar éxito cuando falta o falla needrestart.
(
    command() {
        if [ "$1" = -v ] && [ "$2" = needrestart ]; then return 1; fi
        builtin command "$@"
    }
    if output=$(paso_rebootcheck); then echo 'ERROR: needrestart ausente aceptado'; exit 1; fi
    [[ "$output" == *'instala needrestart'* && "$output" != *'##REBOOT:0'* ]]
)
(
    needrestart() { :; }
    timeout() { return 1; }
    if output=$(paso_rebootcheck); then echo 'ERROR: fallo de needrestart ignorado'; exit 1; fi
    [[ "$output" == *'No se pudo completar'* && "$output" != *'##REBOOT:0'* ]]
    REINICIO_REQUERIDO=1
    if output=$(paso_rebootcheck); then exit 1; fi
    [[ "$output" == *'##REBOOT:1'* ]]
)
(
    needrestart() { :; }
    timeout() { echo 'NEEDRESTART-KSTA: 3'; }
    output=$(paso_rebootcheck)
    [[ "$output" == *'##REBOOT:1'* ]]
)
echo 'Actualización segura: índices, simulación, planes aprobados y limpieza opcional OK'
