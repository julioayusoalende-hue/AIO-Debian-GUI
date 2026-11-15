#!/bin/bash
# Integración en una VM de CI: DEB o integración portable, solo comprobación de reinicio.
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
FORMAT=${AIO_SCHEDULER_FORMAT:-deb}
case "$FORMAT" in
    deb)
        DEB_FILE=$(find dist -maxdepth 1 -name '*.deb' -print -quit)
        [ -n "$DEB_FILE" ]
        sudo apt-get install -y "./$DEB_FILE"
        ;;
    appimage|flatpak)
        # These tests must start without a DEB, never uninstall a user's package.
        if dpkg-query -W -f='${db:Status-Status}' aio-debian-gui 2>/dev/null | grep -qx installed; then
            echo 'La prueba portable requiere una VM sin el DEB instalado.' >&2
            exit 1
        fi
        STAGE=$(mktemp -d)
        trap 'rm -rf "$STAGE"' EXIT
        if [ "$FORMAT" = appimage ]; then
            APPIMAGE=$(find "$PWD/dist" -maxdepth 1 -name '*.AppImage' -print -quit)
            [ -n "$APPIMAGE" ]
            (cd "$STAGE" && "$APPIMAGE" --appimage-extract >/dev/null)
            SOURCE_HELPER="$STAGE/squashfs-root/usr/lib/aio-debian-gui/aio-debian-gui-helper"
        else
            APP=io.github.julioayusoalende_hue.aio_debian_gui
            mkdir -p "$STAGE/aio_core"
            for component in aio-debian-gui-helper es.aiodebian.gui.policy aio_core/scheduler.py aio-debian-gui-maintenance@.service; do
                flatpak run --user --command=cat "$APP" \
                    "/app/share/aio-debian-gui/host-integration/$component" > "$STAGE/$component"
            done
            SOURCE_HELPER="$STAGE/aio-debian-gui-helper"
        fi
        sudo bash "$SOURCE_HELPER" --install-scheduler
        # Prove the service no longer needs the extracted bundle or image mount.
        rm -rf "$STAGE"
        trap - EXIT
        for component in /usr/lib/aio-debian-gui/aio-debian-gui-helper \
            /usr/lib/aio-debian-gui/aio_core/scheduler.py \
            /usr/lib/systemd/system/aio-debian-gui-maintenance@.service; do
            [ "$(stat -c %u "$component")" = 0 ]
        done
        ;;
    *) echo "Formato de prueba desconocido: $FORMAT" >&2; exit 2;;
esac
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
echo "Formato validado: $FORMAT"
echo 'Systemd real: activar, próxima ejecución, servicio de solo comprobación, resultados, pausa y eliminación OK'
