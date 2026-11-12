#!/bin/bash
# Añade un .deb al repositorio APT (carpeta que se sirve con GitHub Pages) y lo firma.
# Uso: publish-apt-repo.sh <paquete.deb> <carpeta-del-sitio>
# Variables:
#   GPG_PASSPHRASE   contraseña de la clave privada (opcional)
#   EXPECTED_FPR     huella esperada (por defecto, la de package/usr/share/keyrings/aio-debian-gui.gpg)
#   KEEP_VERSIONS    versiones antiguas a conservar (por defecto 5)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEB=${1:?Uso: $0 <paquete.deb> <carpeta-del-sitio>}
SITE=${2:?Uso: $0 <paquete.deb> <carpeta-del-sitio>}
KEEP=${KEEP_VERSIONS:-5}
KEYRING="$ROOT/package/usr/share/keyrings/aio-debian-gui.gpg"

# --- La clave de firma debe ser la que ya llevan instalada los equipos -------------
if [ -z "${EXPECTED_FPR:-}" ]; then
    EXPECTED_FPR=$(gpg --show-keys --with-colons "$KEYRING" 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}')
fi
FPR=$(gpg --list-secret-keys --with-colons 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}')
[ -n "$FPR" ] || { echo "No hay ninguna clave privada GPG importada." >&2; exit 1; }
if [ "$FPR" != "$EXPECTED_FPR" ]; then
    echo "La clave de firma ($FPR) NO coincide con la del paquete ($EXPECTED_FPR)." >&2
    echo "Los equipos rechazarían el repositorio. Abortando." >&2
    exit 1
fi

GPG_ARGS=(--batch --yes --local-user "$FPR")
if [ -n "${GPG_PASSPHRASE:-}" ]; then
    GPG_ARGS+=(--pinentry-mode loopback --passphrase "$GPG_PASSPHRASE")
fi

# --- Estructura: pool/ + dists/stable/main/binary-all ------------------------------
POOL="$SITE/pool/main/a/aio-debian-gui"
DIST="$SITE/dists/stable"
BIN="$DIST/main/binary-all"
mkdir -p "$POOL" "$BIN"
cp -f "$DEB" "$POOL/"

# Conservar solo las últimas $KEEP versiones
mapfile -t DEBS < <(ls -1 "$POOL"/aio-debian-gui_*_all.deb | sort -V)
if [ "${#DEBS[@]}" -gt "$KEEP" ]; then
    for old in "${DEBS[@]:0:${#DEBS[@]}-KEEP}"; do rm -f "$old"; done
fi

( cd "$SITE" && dpkg-scanpackages --arch all pool/main /dev/null > dists/stable/main/binary-all/Packages 2>/dev/null )
gzip -9nkf "$BIN/Packages"
xz -9ekf "$BIN/Packages"

# --- Release -------------------------------------------------------------------------
hashes() {  # $1 = comando de hash
    ( cd "$DIST" && for f in main/binary-all/Packages main/binary-all/Packages.gz main/binary-all/Packages.xz; do
        printf ' %s %16d %s\n' "$($1 "$f" | cut -d' ' -f1)" "$(stat -c %s "$f")" "$f"
    done )
}
{
    echo "Origin: aio-debian-gui"
    echo "Label: aio-debian-gui"
    echo "Suite: stable"
    echo "Codename: stable"
    echo "Date: $(LC_ALL=C date -Ru | sed 's/+0000/UTC/')"
    echo "Architectures: all"
    echo "Components: main"
    echo "Description: Repositorio APT de aio-debian-gui"
    echo "MD5Sum:";    hashes md5sum
    echo "SHA256:";    hashes sha256sum
} > "$DIST/Release"

rm -f "$DIST/InRelease" "$DIST/Release.gpg"
gpg "${GPG_ARGS[@]}" --clearsign -o "$DIST/InRelease" "$DIST/Release"
gpg "${GPG_ARGS[@]}" --armor --detach-sign -o "$DIST/Release.gpg" "$DIST/Release"

# --- Clave pública y portada -----------------------------------------------------------
cp -f "$KEYRING" "$SITE/aio-debian-gui.gpg"
touch "$SITE/.nojekyll"
cp -f "$ROOT/scripts/site-index.html" "$SITE/index.html"
echo "Repositorio actualizado en $SITE (firmado con $FPR)"
