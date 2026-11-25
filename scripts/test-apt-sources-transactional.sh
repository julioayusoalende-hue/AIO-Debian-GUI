#!/bin/bash
# Prueba la actualización transaccional de fuentes APT sin tocar /etc/apt.
set -euo pipefail
cd "$(dirname "$0")/.."
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
list="$tmp/debian.list"
original=$'deb https://deb.debian.org/debian trixie main\n'
printf '%s' "$original" > "$list"

anadir_componentes "$list"
grep -Fxq 'deb https://deb.debian.org/debian trixie main contrib non-free' "$list"
cmp -s "$list.bak" <(printf '%s' "$original")

# Una segunda modificación conserva el respaldo anterior.
sed -i 's/ contrib non-free$//' "$list"
anadir_componentes "$list"
[ -f "$list.bak.previous" ]

# Si falla la sustitución final, el original permanece intacto.
sed -i 's/ contrib non-free$//' "$list"
antes=$(cat "$list")
FAIL_FINAL_MV=1
mv() {
    local destino="${!#}"
    if [ "$FAIL_FINAL_MV" -eq 1 ] && [ "$destino" = "$TEST_TARGET" ]; then
        return 1
    fi
    command mv "$@"
}
TEST_TARGET="$list"
if anadir_componentes "$list"; then
    echo 'ERROR: se aceptó un fallo al sustituir la fuente APT' >&2
    exit 1
else
    [ "$?" -eq 2 ]
fi
[ "$(cat "$list")" = "$antes" ]
[ -f "$list.bak" ]

# Deb822 también se actualiza y deja respaldo.
sources="$tmp/debian.sources"
original_sources=$'Types: deb\nURIs: https://deb.debian.org/debian\nSuites: trixie\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n'
printf '%s' "$original_sources" > "$sources"
anadir_componentes "$sources"
grep -Fxq 'Components: main contrib non-free' "$sources"
cmp -s "$sources.bak" <(printf '%s' "$original_sources")

# Nunca se siguen enlaces simbólicos.
ln -s "$list" "$tmp/enlace.list"
if anadir_componentes "$tmp/enlace.list"; then
    echo 'ERROR: se modificó una fuente APT simbólica' >&2
    exit 1
else
    [ "$?" -eq 2 ]
fi

echo '✔ Fuentes APT: respaldo previo, sustitución atómica y rechazo de symlinks'
