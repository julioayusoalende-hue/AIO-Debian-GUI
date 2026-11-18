#!/bin/bash
# Integración en una VM de CI: instala el DEB y ejecuta solo la comprobación de reinicio.
# Nunca programa actualizaciones, eliminaciones de paquetes ni reinicios reales.
set -euo pipefail
if [ "${AIO_SYSTEMD_INTEGRATION:-}" != 1 ]; then
    echo 'Integración systemd omitida; requiere AIO_SYSTEMD_INTEGRATION=1 en una VM de CI.'
    exit 0
fi
if [ "$(cat /proc/1/comm)" != systemd ]; then
    echo 'No hay systemd como PID 1; integración no disponible.' >&2
    exit 1
fi
cd "$(dirname "$0")/.."
DEB_FILE=$(find dist -maxdepth 1 -name '*.deb' -print -quit)
[ -n "$DEB_FILE" ]
sudo apt-get install -y "./$DEB_FILE"
SCHEDULE_UID=$(id -u)
HELPER=/usr/lib/aio-debian-gui/aio-debian-gui-helper
TIMER="aio-debian-gui-maintenance-${SCHEDULE_UID}.timer"
SERVICE="aio-debian-gui-maintenance@${SCHEDULE_UID}.service"
cleanup() {
    sudo env PKEXEC_UID="$SCHEDULE_UID" "$HELPER" --schedule-remove || true
}
trap cleanup EXIT
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
assert report['last_result']['status'] == 'success', report
assert report['last_result']['tasks'] == {'rebootcheck': 'success'}, report
assert report['timer_active']
PY
PAUSED=$(python3 -c 'import json,sys; c=json.loads(sys.argv[1]); c["enabled"]=False; print(json.dumps(c))' "$CONFIG")
sudo env PKEXEC_UID="$SCHEDULE_UID" "$HELPER" --schedule-save "$PAUSED"
if systemctl is-active --quiet "$TIMER"; then
    echo 'El temporizador no se ha pausado.' >&2
    exit 1
fi
cleanup
trap - EXIT
[ ! -e "/etc/systemd/system/$TIMER" ]
echo 'Systemd real: activar, próxima ejecución, servicio de solo comprobación, resultados, pausa y eliminación OK'
