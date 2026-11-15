#!/bin/bash
# Todas las operaciones APT están simuladas; nunca se modifica el sistema.
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
TEST_DIR=$(mktemp -d)
trap 'rm -rf -- "$TEST_DIR"' EXIT
PLAN='Inst nano [7.2] (7.3 Debian:stable)'
UPGRADE_PLAN=$(python3 -c 'import hashlib, sys; print(hashlib.sha256((sys.argv[1]+"\n").encode()).hexdigest())' "$PLAN")
SIMULATION="$PLAN"
SIMULATION_STATUS=0
UPDATE_STATUS=0
INSTALL_STATUS=0
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
    if grep -q -- '--no-remove' "$TEST_DIR/calls"; then
        echo 'ERROR: se ejecutó APT pese al bloqueo'; exit 1
    fi
}

reset_calls
paso_upgrade
[ "$(head -n 1 "$TEST_DIR/calls")" = update ]
grep -q -- '^-s -o Debug::NoLocking=1 dist-upgrade$' "$TEST_DIR/calls"
grep -q -- '--no-remove dist-upgrade$' "$TEST_DIR/calls"

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

# Invocaciones sin GUI también simulan y bloquean las eliminaciones.
UPGRADE_PLAN=''
INSTALL_STATUS=0
SIMULATION='Remv old-package [1]'
reset_calls
if paso_upgrade; then echo 'ERROR: eliminación sin GUI aceptada'; exit 1; fi
assert_no_install
echo 'Actualización segura: índices, simulación, plan aprobado y --no-remove OK'
