#!/bin/bash
# Integración en una VM de CI: instala el runtime autónomo sin instalar el DEB.
# El único mantenimiento ejecutado es comprobar el reinicio; no modifica paquetes.
set -euo pipefail
if [ "${AIO_SYSTEMD_INTEGRATION:-}" != 1 ]; then
    echo 'Integración autónoma omitida; requiere AIO_SYSTEMD_INTEGRATION=1 en una VM de CI.'
    exit 0
fi
if [ "$(cat /proc/1/comm)" != systemd ]; then
    echo 'No hay systemd como PID 1; integración autónoma no disponible.' >&2
    exit 1
fi
cd "$(dirname "$0")/.."
SCHEDULE_UID=$(id -u)
[ "$SCHEDULE_UID" -ne 0 ] || { echo 'Ejecuta esta prueba como usuario de CI con sudo.' >&2; exit 1; }
HELPER=/usr/lib/aio-debian-gui/aio-debian-gui-helper
TIMER="aio-debian-gui-maintenance-${SCHEDULE_UID}.timer"
SERVICE="aio-debian-gui-maintenance@${SCHEDULE_UID}.service"
MANAGED_FILES=(
    "$HELPER"
    /usr/lib/aio-debian-gui/aio_core/__init__.py
    /usr/lib/aio-debian-gui/aio_core/scheduler.py
    /usr/lib/aio-debian-gui/aio_core/preflight.py
    /usr/share/polkit-1/actions/es.aiodebian.gui.policy
    /usr/lib/systemd/system/aio-debian-gui-maintenance@.service
)
assert_no_deb() {
    if dpkg-query -W -f='${db:Status-Status}' aio-debian-gui 2>/dev/null | grep -qx installed; then
        echo 'La prueba autónoma exige que aio-debian-gui no esté instalado como DEB.' >&2
        exit 1
    fi
}
assert_no_deb
for path in "${MANAGED_FILES[@]}" /var/lib/aio-debian-gui/host-integration.json; do
    [ ! -e "$path" ] && [ ! -L "$path" ] || {
        echo "Ya existe una integración del anfitrión: $path" >&2
        exit 1
    }
done
WORK_DIR=$(mktemp -d)
INSTALL_ATTEMPTED=0
cleanup() {
    if [ "$INSTALL_ATTEMPTED" -eq 1 ]; then
        if [ -x "$HELPER" ]; then
            sudo env PKEXEC_UID="$SCHEDULE_UID" "$HELPER" --schedule-remove || true
        fi
        if [ -f "$WORK_DIR/removal/host_integration.py" ]; then
            sudo env PKEXEC_UID="$SCHEDULE_UID" /usr/bin/python3 -I \
                "$WORK_DIR/removal/host_integration.py" --uninstall || true
        fi
    fi
    rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT
python3 scripts/build-host-integration.py "$WORK_DIR/install"
# Una copia recién preparada permite retirar la integración sin conservar el origen instalado.
python3 scripts/build-host-integration.py "$WORK_DIR/removal"
INSTALL_ATTEMPTED=1
sudo env PKEXEC_UID="$SCHEDULE_UID" /usr/bin/python3 -I \
    "$WORK_DIR/install/host_integration.py" --install "$WORK_DIR/install/payload.json"
assert_no_deb
for path in "${MANAGED_FILES[@]}"; do
    [ -f "$path" ] && [ ! -L "$path" ]
    [ "$(stat -c %u "$path")" -eq 0 ]
    [ "$(stat -c %a "$path")" = 644 ] || [ "$(stat -c %a "$path")" = 755 ]
done
[ -f /var/lib/aio-debian-gui/host-integration.json ]
# El servicio debe seguir funcionando después de desaparecer el staging original.
rm -rf -- "$WORK_DIR/install"
[ ! -e "$WORK_DIR/install" ]
if grep -Fq "$WORK_DIR" /usr/lib/systemd/system/aio-debian-gui-maintenance@.service; then
    echo 'El servicio depende del directorio temporal de instalación.' >&2
    exit 1
fi
CONFIG=$(python3 - <<'PY'
import datetime, json
future = datetime.datetime.now() + datetime.timedelta(hours=2)
print(json.dumps(dict(enabled=True, frequency='daily', weekday=0,
                     hour=future.hour, minute=future.minute, tasks=['rebootcheck'])))
PY
)
sudo env PKEXEC_UID="$SCHEDULE_UID" "$HELPER" --schedule-save "$CONFIG"
systemctl is-active --quiet "$TIMER"
[ -n "$(systemctl show "$TIMER" --property=NextElapseUSecRealtime --value)" ]
for attempt in 1 2 3; do
    if ! sudo systemctl start "$SERVICE"; then
        sudo journalctl -u "$SERVICE" --no-pager -n 100 >&2
        exit 1
    fi
    STATUS=$("$HELPER" --schedule-status)
    OUTCOME=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["last_result"]["status"])' "$STATUS")
    [ "$OUTCOME" = success ] && break
    [ "$OUTCOME" = skipped ] || { echo "$STATUS" >&2; exit 1; }
    sleep 5
done
python3 - "$STATUS" <<'PY'
import json, sys
report = json.loads(sys.argv[1])
assert report['available'], report
assert report['last_result']['status'] == 'success', report
assert report['last_result']['tasks'] == {'rebootcheck': 'success'}, report
assert report['timer_active'], report
PY
assert_no_deb
PAUSED=$(python3 -c 'import json,sys; c=json.loads(sys.argv[1]); c["enabled"]=False; print(json.dumps(c))' "$CONFIG")
sudo env PKEXEC_UID="$SCHEDULE_UID" "$HELPER" --schedule-save "$PAUSED"
if systemctl is-active --quiet "$TIMER"; then
    echo 'El temporizador autónomo no se ha pausado.' >&2
    exit 1
fi
sudo env PKEXEC_UID="$SCHEDULE_UID" "$HELPER" --schedule-remove
[ ! -e "/etc/systemd/system/$TIMER" ]
sudo env PKEXEC_UID="$SCHEDULE_UID" /usr/bin/python3 -I \
    "$WORK_DIR/removal/host_integration.py" --uninstall
INSTALL_ATTEMPTED=0
for path in "${MANAGED_FILES[@]}" /var/lib/aio-debian-gui/host-integration.json; do
    [ ! -e "$path" ] && [ ! -L "$path" ] || {
        echo "La integración autónoma no se ha retirado: $path" >&2
        exit 1
    }
done
assert_no_deb
echo 'Systemd autónomo sin DEB: instalar, retirar staging, ejecutar, resultados, pausar, eliminar y desinstalar OK'
