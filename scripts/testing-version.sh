#!/bin/bash
set -euo pipefail

if [ "$#" -ne 4 ] || [[ ! "$1" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "Uso: $0 vX.Y.Z VERSION_ESTABLE NUMERO_EJECUCION INTENTO" >&2
    exit 2
fi
major=${BASH_REMATCH[1]} minor=${BASH_REMATCH[2]} patch=${BASH_REMATCH[3]}
stable_version=$2
epoch=${stable_version%:*}
testing_version=$(sed -n 's/^Version: //p' package/DEBIAN/control)
if [[ ! "$epoch" =~ ^[0-9]+$ || "$stable_version" != "$epoch:${1#v}" ||
      "$testing_version" != "$epoch:"* ||
      ! "$3" =~ ^[1-9][0-9]*$ || ! "$4" =~ ^[1-9][0-9]*$ ]]; then
    echo "Versión estable, época Debian o número de ejecución no válidos." >&2
    exit 2
fi
printf '%s.%s.%s~testing.%s.%s\n' "$major" "$minor" "$((10#$patch + 1))" "$3" "$4"
