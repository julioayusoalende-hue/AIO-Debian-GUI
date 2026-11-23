#!/bin/bash
set -euo pipefail

if [ "$#" -ne 4 ] || [[ ! "$1" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "Uso: $0 vX.Y.Z VERSION_ESTABLE NUMERO_EJECUCION INTENTO" >&2
    exit 2
fi
stable_version=$2
epoch=${stable_version%:*}
testing_version=$(sed -n 's/^Version: //p' package/DEBIAN/control)
if [[ ! "$epoch" =~ ^[0-9]+$ || "$stable_version" != "$epoch:${1#v}" ||
      ! "$3" =~ ^[1-9][0-9]*$ || ! "$4" =~ ^[1-9][0-9]*$ ]]; then
    echo "Versión estable o número de ejecución no válidos." >&2
    exit 2
fi
IFS=. read -r stable_major stable_minor stable_patch <<< "${1#v}"
if [[ "$testing_version" != "$epoch:"* ]]; then
    echo "Época Debian incompatible." >&2
    exit 2
fi
if [[ "$testing_version" =~ ^([0-9]+):([0-9]+)\.([0-9]+)\.([0-9]+)~testing\.[1-9][0-9]*(\.[1-9][0-9]*)?$ ]]; then
    base_major=${BASH_REMATCH[2]} base_minor=${BASH_REMATCH[3]} base_patch=${BASH_REMATCH[4]}
    if [ "$base_major" = "$stable_major" ] && [ "$base_minor" = "$stable_minor" ] && [ "$base_patch" -gt "$stable_patch" ]; then
        printf '%s.%s.%s~testing.%s.%s\n' "$base_major" "$base_minor" "$base_patch" "$3" "$4"
    else
        printf '%s.%s.%s~testing.%s.%s\n' "$stable_major" "$stable_minor" "$((10#$stable_patch + 1))" "$3" "$4"
    fi
elif [[ "$testing_version" =~ ^[0-9]+:[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf '%s.%s.%s~testing.%s.%s\n' "$stable_major" "$stable_minor" "$((10#$stable_patch + 1))" "$3" "$4"
else
    echo "Versión testing no válida." >&2
    exit 2
fi
