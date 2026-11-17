#!/bin/bash
# Añade los paquetes al repositorio APT (GitHub Pages) y firma sus metadatos.
# Uso: publish-apt-repo.sh <paquete-principal.deb> <carpeta-del-sitio> [paquete-host.deb]
# Variables:
#   GPG_PASSPHRASE   contraseña de la clave privada (opcional)
#   EXPECTED_FPR     si se indica, debe coincidir con la clave del proyecto
#   KEEP_VERSIONS    versiones a conservar de cada paquete (por defecto 5)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEB=${1:?Uso: $0 <paquete-principal.deb> <carpeta-del-sitio> [paquete-host.deb]}
SITE=${2:?Uso: $0 <paquete-principal.deb> <carpeta-del-sitio> [paquete-host.deb]}
HOST_DEB=${3:-}
[ "$#" -le 3 ] || { echo "Demasiados argumentos." >&2; exit 1; }
KEEP=${KEEP_VERSIONS:-5}
KEYRING="$ROOT/package/usr/share/keyrings/aio-debian-gui.gpg"
[[ "$KEEP" =~ ^[1-9][0-9]{0,2}$ ]] || { echo "KEEP_VERSIONS no válido." >&2; exit 1; }

# La clave de firma debe ser la incluida en el proyecto, también si se pasa EXPECTED_FPR.
FPR=$(gpg --show-keys --with-colons "$KEYRING" 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}')
[ -n "$FPR" ] || { echo "No se pudo leer la clave pública del proyecto." >&2; exit 1; }
[ -z "${EXPECTED_FPR:-}" ] || [ "$FPR" = "$EXPECTED_FPR" ] || {
    echo "EXPECTED_FPR no coincide con la clave del proyecto." >&2; exit 1;
}
gpg --batch --list-secret-keys "$FPR" >/dev/null 2>&1 || {
    echo "Falta la clave privada correspondiente a $FPR." >&2; exit 1;
}

[ "$(dpkg-deb -f "$DEB" Package)" = "aio-debian-gui" ] &&
    [ "$(dpkg-deb -f "$DEB" Architecture)" = "all" ] || {
    echo "El paquete principal no es válido." >&2; exit 1;
}
VERSION=$(dpkg-deb -f "$DEB" Version)
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] &&
    [ "$(basename "$DEB")" = "aio-debian-gui_${VERSION}_all.deb" ] || {
    echo "Nombre o versión del paquete principal no válidos." >&2; exit 1;
}
if [ -n "$HOST_DEB" ]; then
    [ "$(dpkg-deb -f "$HOST_DEB" Package)" = "aio-debian-gui-host" ] &&
        [ "$(dpkg-deb -f "$HOST_DEB" Architecture)" = "all" ] &&
        [ "$(dpkg-deb -f "$HOST_DEB" Version)" = "$VERSION" ] &&
        [ "$(dpkg-deb -f "$HOST_DEB" Conflicts)" = "aio-debian-gui" ] &&
        [ -z "$(dpkg-deb -f "$HOST_DEB" Replaces)" ] &&
        [ "$(basename "$HOST_DEB")" = "aio-debian-gui-host_${VERSION}_all.deb" ] || {
        echo "El paquete host no coincide con el paquete principal." >&2; exit 1;
    }
fi

GPG_ARGS=(--batch --yes --local-user "$FPR")
if [ -n "${GPG_PASSPHRASE:-}" ]; then
    GPG_ARGS+=(--pinentry-mode loopback --passphrase "$GPG_PASSPHRASE")
fi

# No publicar el host en el índice APT global, ni siquiera si ya hay
# artefactos antiguos en el pool. Requiere intervención explícita.
if [ -d "$SITE/pool/main" ]; then
    EXISTING_PACKAGES=$(cd "$SITE" && dpkg-scanpackages --multiversion --arch all pool/main /dev/null)
    if grep -qx 'Package: aio-debian-gui-host' <<< "$EXISTING_PACKAGES"; then
        echo "El repositorio global contiene un paquete host; no se publicará." >&2
        exit 1
    fi
fi

publish_repo() {
    local site=$1 deb=$2 package=$3 label=$4
    local pool="$site/pool/main/a/aio-debian-gui"
    local dist="$site/dists/stable"
    local bin="$dist/main/binary-all"
    local files=() debs=() old
    mkdir -p "$pool" "$bin"
    cp -f "$deb" "$pool/"
    shopt -s nullglob
    files=("$pool/${package}_"*_all.deb)
    if [ "${#files[@]}" -gt "$KEEP" ]; then
        mapfile -t debs < <(printf '%s\n' "${files[@]}" | sort -V)
        for old in "${debs[@]:0:${#debs[@]}-KEEP}"; do rm -f -- "$old"; done
    fi
    shopt -u nullglob
    ( cd "$site" && dpkg-scanpackages --arch all pool/main /dev/null > dists/stable/main/binary-all/Packages 2>/dev/null )
    gzip -9nkf "$bin/Packages"
    xz -9ekf "$bin/Packages"
    hashes() {
        ( cd "$dist" && for f in main/binary-all/Packages main/binary-all/Packages.gz main/binary-all/Packages.xz; do
            printf ' %s %16d %s\n' "$($1 "$f" | cut -d' ' -f1)" "$(stat -c %s "$f")" "$f"
        done )
    }
    {
        echo "Origin: $label"
        echo "Label: $label"
        echo "Suite: stable"
        echo "Codename: stable"
        echo "Date: $(LC_ALL=C date -Ru | sed 's/+0000/UTC/')"
        echo "Architectures: all"
        echo "Components: main"
        echo "Description: Repositorio APT de $label"
        echo "MD5Sum:"; hashes md5sum
        echo "SHA256:"; hashes sha256sum
    } > "$dist/Release"
    rm -f "$dist/InRelease" "$dist/Release.gpg"
    gpg "${GPG_ARGS[@]}" --clearsign -o "$dist/InRelease" "$dist/Release"
    gpg "${GPG_ARGS[@]}" --armor --detach-sign -o "$dist/Release.gpg" "$dist/Release"
}

publish_repo "$SITE" "$DEB" aio-debian-gui aio-debian-gui
if [ -n "$HOST_DEB" ]; then
    publish_repo "$SITE/host-repo" "$HOST_DEB" aio-debian-gui-host aio-debian-gui-host
fi

# --- Clave pública y portada -----------------------------------------------------------
cp -f "$KEYRING" "$SITE/aio-debian-gui.gpg"
touch "$SITE/.nojekyll"
cp -f "$ROOT/scripts/site-index.html" "$SITE/index.html"
echo "Repositorio actualizado en $SITE (firmado con $FPR)"
