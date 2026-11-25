#!/bin/bash
# Exercise the task with mock commands; never modify the real snapd installation.
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT
paquete_instalado() { [ "${TEST_MODE:-ok}" != absent ]; }
snap() {
    printf '%s\n' "$*" >> "$TEST_DIR/calls"
    case "$1" in
        refresh) [ "${TEST_MODE:-ok}" != refresh-error ] ;;
        list)
            [ "${TEST_MODE:-ok}" != list-error ] || return 1
            cat <<'SNAPS'
Name Version Rev Tracking Publisher Notes
app 1.0 10 latest/stable example disabled
app 2.0 20 latest/stable example disabled,classic
app 3.0 30 latest/stable example classic
other 1.0 5 latest/stable example disabled
other 2.0 7 latest/stable example -
malicious 1.0 --purge latest/stable example disabled
local 1.0 x1 latest/stable example disabled
new 1.0 100 latest/stable example -
SNAPS
            ;;
        remove) [ "${TEST_MODE:-ok}" != remove-error ] ;;
        *) return 2 ;;
    esac
}
export LC_ALL=C
TEST_MODE=absent
paso_snap_update
[ ! -e "$TEST_DIR/calls" ]
TEST_MODE=ok
paso_snap_update
diff -u <(printf '%s\n' 'refresh') "$TEST_DIR/calls"
TEST_MODE=refresh-error
: > "$TEST_DIR/calls"
if paso_snap_update; then echo "Failure swallowed: refresh-error" >&2; exit 1; fi

TEST_MODE=ok
: > "$TEST_DIR/calls"
paso_clean_snap
diff -u <(printf '%s\n' 'list --all' 'remove app --revision=10') "$TEST_DIR/calls"
for TEST_MODE in list-error remove-error; do
    : > "$TEST_DIR/calls"
    if paso_clean_snap; then echo "Failure swallowed: $TEST_MODE" >&2; exit 1; fi
    if [ "$TEST_MODE" != remove-error ]; then
        ! grep -q '^remove ' "$TEST_DIR/calls"
    fi
done
printf '✔ Snap: actualización y limpieza independientes, rollback acotado y errores\n'
