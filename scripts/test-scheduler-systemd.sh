#!/bin/bash
# Integration en VM: configurar y retirar el timer con la cuenta del usuario.
set -euo pipefail
if [ "${AIO_SYSTEMD_INTEGRATION:-}" != 1 ]; then
    echo 'Integración systemd omitida; requiere AIO_SYSTEMD_INTEGRATION=1 en una VM de CI.'
    exit 0
fi
if ! systemctl --user show-environment >/dev/null 2>&1; then
    echo 'No hay un gestor systemd de usuario en esta sesión; integración omitida.'
    exit 0
fi
cd "$(dirname "$0")/.."
SCHEDULE_UID=$(id -u)
CONFIG=$(python3 - <<'PY'
import datetime, json
future = datetime.datetime.now() + datetime.timedelta(hours=2)
print(json.dumps(dict(enabled=True, frequency='daily', weekday=0,
                     hour=future.hour, minute=future.minute, tasks=['rebootcheck'])))
PY
)
run_scheduler() {
    python3 - "$@" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("package/usr/lib/aio-debian-gui").resolve()))
from aio_core.host_integration import run_user_scheduler
action, uid = sys.argv[1:3]
config = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
report = run_user_scheduler("deb", action, uid, config)
if report is not None:
    print(json.dumps(report))
PY
}
cleanup() {
    run_scheduler --remove "$SCHEDULE_UID" >/dev/null 2>&1 || true
}
trap cleanup EXIT
run_scheduler --configure "$SCHEDULE_UID" "$CONFIG" >/dev/null
STATUS=$(run_scheduler --status "$SCHEDULE_UID")
python3 - "$STATUS" <<'PY'
import json, sys
report = json.loads(sys.argv[1])
assert report['available'], report
assert report['config']['enabled'], report
assert report['timer_active'], report
assert report['next_run'], report
PY
PAUSED=$(python3 -c 'import json,sys; c=json.loads(sys.argv[1]); c["enabled"]=False; print(json.dumps(c))' "$CONFIG")
run_scheduler --configure "$SCHEDULE_UID" "$PAUSED" >/dev/null
if systemctl --user is-active --quiet aio-debian-gui-maintenance.timer; then
    echo 'El temporizador no se ha pausado.' >&2
    exit 1
fi
run_scheduler --remove "$SCHEDULE_UID" >/dev/null
trap - EXIT
[ ! -e "$HOME/.config/systemd/user/aio-debian-gui-maintenance.timer" ]
echo 'Systemd --user: activar, consultar próxima ejecución, pausar y eliminar sin privilegios OK'
