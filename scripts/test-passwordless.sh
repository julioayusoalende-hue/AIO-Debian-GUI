#!/usr/bin/env bash
# Seguridad: validación estática + reglas Polkit sin cambios en el anfitrión.
set -euo pipefail
cd "$(dirname "$0")/.."
HELPER="$PWD/package/usr/lib/aio-debian-gui/aio-debian-gui-helper"
GUI="$PWD/package/usr/bin/aio-debian-gui"
RULE=$(bash -c 'source "$1"; generar_regla_polkit "test_user"' _ "$HELPER")
grep -Fq 'action.id === "es.aiodebian.gui.mantenimiento"' <<< "$RULE"
grep -Fq 'action.lookup("program") === "/usr/lib/aio-debian-gui/aio-debian-gui-helper"' <<< "$RULE"
grep -Fq 'subject.user === "test_user"' <<< "$RULE"
grep -Fq 'subject.local &&' <<< "$RULE"
grep -Fq 'subject.active)' <<< "$RULE"
grep -Fq 'return polkit.Result.YES;' <<< "$RULE"
# Verificar que el helper no habilita excepciones de forma implícita.
grep -Fq -- '--enable-passwordless)' "$HELPER"
grep -Fq 'habilitar_sin_contrasena' "$HELPER"
grep -Fq -- '--disable-passwordless)' "$HELPER"
grep -Fq 'deshabilitar_sin_contrasena' "$HELPER"
grep -Fq 'PASSWORDLESS_STATE_DIR=/var/lib/aio-debian-gui/passwordless' "$HELPER"
grep -Fq 'guardar_marcador_passwordless' "$HELPER"
grep -Fq -- '--flatpak-user-update' "$HELPER"
grep -Fq 'flatpak --user update -y' "$HELPER"
# No desactivar la política por defecto para todos ni borrar opciones guardadas.
grep -Fq '<allow_active>auth_admin</allow_active>' package/usr/share/polkit-1/actions/es.aiodebian.gui.policy
! grep -Fq '<allow_active>yes</allow_active>' package/usr/share/polkit-1/actions/es.aiodebian.gui.policy
! grep -Eq 'rm -f.*50-aiodebian-gui' package/DEBIAN/postinst
grep -Fq 'rm -f /etc/polkit-1/rules.d/50-aiodebian-gui-*.rules' package/DEBIAN/prerm
grep -Fq 'rm -rf /var/lib/aio-debian-gui/passwordless' package/DEBIAN/prerm
grep -Fq '/var/lib/aio-debian-gui/passwordless' package/DEBIAN/postinst
grep -Fq '50-aiodebian-gui-*.rules' package/DEBIAN/postinst
python3 - "$GUI" <<'PY'
import ast
import sys
from pathlib import Path
source = Path(sys.argv[1]).read_text(encoding="utf-8")
ast.parse(source)
assert 'if pasos == ["flatpak-update"] and not flatpak_sistema:' in source
assert 'self._iniciar_flatpak_usuario(reintento_de)' in source
assert 'comando_host("bash", "-c", script)' in source
assert 'flatpak --user update -y' in source
assert 'flatpak --user uninstall --unused -y' in source
assert 'No solicitar contraseña de administrador en AiO (opcional)' in source
assert 'from aio_core.constants import autorizacion_sin_contrasena_activa' in source
PY
echo "✔ excepción Polkit específica y reversible; tarea Flatpak de usuario sin pkexec"

# Probar creación/eliminación de regla y marcador en un directorio temporal,
# sin privilegios reales ni cambios en el anfitrión.
TMP_POLKIT=$(mktemp -d)
trap 'rm -rf -- "$TMP_POLKIT"' EXIT
bash -c '
    set -e
    source "$1"
    POLKIT_RULES_DIR="$2/rules"
    PASSWORDLESS_STATE_DIR="$2/state"
    pkexec_uid() { echo 1000; }
    pkexec_username() { echo test_user; }
    instalar_componentes_polkit() { :; }
    chown() { :; }
    install() {
        local args=()
        while [ "$#" -gt 0 ]; do
            case "$1" in
                -o|-g) shift 2 ;;
                *) args+=("$1"); shift ;;
            esac
        done
        command install "${args[@]}"
    }
    mkdir -p "$POLKIT_RULES_DIR"
    habilitar_sin_contrasena >/dev/null
    test -s "$POLKIT_RULES_DIR/50-aiodebian-gui-1000.rules"
    test -s "$PASSWORDLESS_STATE_DIR/1000.rules"
    cmp "$POLKIT_RULES_DIR/50-aiodebian-gui-1000.rules" "$PASSWORDLESS_STATE_DIR/1000.rules"
    deshabilitar_sin_contrasena >/dev/null
    test ! -e "$POLKIT_RULES_DIR/50-aiodebian-gui-1000.rules"
    test ! -e "$PASSWORDLESS_STATE_DIR/1000.rules"
' _ "$HELPER" "$TMP_POLKIT"
echo "✔ regla Polkit y marcador persistente se crean y eliminan juntos"

# Simular la migración del postinst sin root ni rutas reales.
TMP_MIGRATE=$(mktemp -d)
trap 'rm -rf -- "$TMP_POLKIT" "$TMP_MIGRATE"' EXIT
mkdir -p "$TMP_MIGRATE/etc/polkit-1/rules.d"
printf '%s\n' 'regla existente' > "$TMP_MIGRATE/etc/polkit-1/rules.d/50-aiodebian-gui-1000.rules"
sed \
    -e "s|/etc/polkit-1/rules.d|$TMP_MIGRATE/etc/polkit-1/rules.d|g" \
    -e "s|/var/lib/aio-debian-gui/passwordless|$TMP_MIGRATE/var/lib/aio-debian-gui/passwordless|g" \
    -e 's/ -o root -g root//g' \
    -e 's/chown root:root/:/g' \
    package/DEBIAN/postinst > "$TMP_MIGRATE/postinst"
sh "$TMP_MIGRATE/postinst" configure
cmp "$TMP_MIGRATE/etc/polkit-1/rules.d/50-aiodebian-gui-1000.rules" \
    "$TMP_MIGRATE/var/lib/aio-debian-gui/passwordless/1000.rules"
echo "✔ postinst migra reglas Polkit existentes al marcador persistente"
