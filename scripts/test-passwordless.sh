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
grep -Fq -- '--flatpak-user-update' "$HELPER"
grep -Fq 'flatpak --user update -y' "$HELPER"
# No desactivar la política por defecto para todos ni borrar opciones guardadas.
grep -Fq '<allow_active>auth_admin</allow_active>' package/usr/share/polkit-1/actions/es.aiodebian.gui.policy
! grep -Fq '<allow_active>yes</allow_active>' package/usr/share/polkit-1/actions/es.aiodebian.gui.policy
! grep -Eq 'rm -f.*50-aiodebian-gui' package/DEBIAN/postinst
python3 - "$GUI" <<'PY'
import ast
import sys
from pathlib import Path
source = Path(sys.argv[1]).read_text(encoding="utf-8")
ast.parse(source)
assert 'if pasos == ["flatpak-update"]:' in source
assert 'self._iniciar_flatpak_usuario()' in source
assert 'comando_host("bash", "-c", script)' in source
assert 'flatpak --user update -y' in source
assert 'flatpak --user uninstall --unused -y' in source
assert 'No solicitar contraseña de administrador en AiO (opcional)' in source
PY
echo "✔ excepción Polkit específica y reversible; tarea Flatpak de usuario sin pkexec"
