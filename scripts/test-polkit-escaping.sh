#!/bin/bash
set -euo pipefail
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
rule=$(generar_regla_polkit usuario_prueba)
[[ "$rule" == *'subject.user === "usuario_prueba"'* ]]
if generar_regla_polkit 'evil"; return polkit.Result.YES; //' >/dev/null 2>&1; then
    echo "ERROR: inyección de JavaScript aceptada" >&2
    exit 1
fi
echo "Polkit: validación de nombres OK"
