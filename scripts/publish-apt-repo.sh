#!/bin/bash
# Añade los paquetes al repositorio APT (GitHub Pages) y firma sus metadatos.
# Uso: publish-apt-repo.sh <paquete-principal.deb> <carpeta-del-sitio> [paquete-host.deb] [ayusos-control-center.deb]
# Variables:
#   GPG_PASSPHRASE   contraseña de la clave privada (opcional)
#   EXPECTED_FPR     si se indica, debe coincidir con la clave del proyecto
#   APT_CHANNEL      stable (por defecto) o testing
#   KEEP_VERSIONS    versiones a conservar de cada paquete (por defecto 5)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEB=${1:?Uso: $0 <paquete-principal.deb> <carpeta-del-sitio> [paquete-host.deb] [ayusos-control-center.deb]}
SITE=${2:?Uso: $0 <paquete-principal.deb> <carpeta-del-sitio> [paquete-host.deb] [ayusos-control-center.deb]}
HOST_DEB=${3:-}
AYUSOS_DEB=${4:-}
[ "$#" -le 4 ] || { echo "Demasiados argumentos." >&2; exit 1; }
KEEP=${KEEP_VERSIONS:-5}
CHANNEL=${APT_CHANNEL:-stable}
VERSION_PATTERN='^([0-9]+:)?[0-9]+\.[0-9]+\.[0-9]+(-[1-9][0-9]*)?$'
case "$CHANNEL" in
    stable) ;;
    testing)
        [ -z "$HOST_DEB" ] || exit 1
        SITE="$SITE/apt-testing"
        VERSION_PATTERN='^[0-9]+:[0-9]+\.[0-9]+\.[0-9]+~testing\.[1-9][0-9]*\.[1-9][0-9]*$'
        ;;
    *) echo "APT_CHANNEL no válido." >&2; exit 1 ;;
esac
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
PUBLIC_VERSION=${VERSION#*:}
[[ "$VERSION" =~ $VERSION_PATTERN ]] &&
    [ "$(basename "$DEB")" = "aio-debian-gui_${PUBLIC_VERSION}_all.deb" ] || {
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

if [ -n "$AYUSOS_DEB" ]; then
    AYUSOS_VERSION=$(dpkg-deb -f "$AYUSOS_DEB" Version)
    AYUSOS_PUBLIC_VERSION=${AYUSOS_VERSION#*:}
    [ "$AYUSOS_VERSION" = "$PUBLIC_VERSION" ] &&
        [[ "$(dpkg-deb -f "$AYUSOS_DEB" Depends)" == "aio-debian-gui (>= $VERSION),"* ]] &&
        [ "$(dpkg-deb -f "$AYUSOS_DEB" Package)" = "ayusos-control-center" ] &&
        [ "$(dpkg-deb -f "$AYUSOS_DEB" Architecture)" = "all" ] &&
        [ "$(basename "$AYUSOS_DEB")" = "ayusos-control-center_${AYUSOS_PUBLIC_VERSION}_all.deb" ] || {
        echo "El paquete ayusos-control-center no coincide con la versión de AiO." >&2; exit 1;
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

publish_appstream() (
    local deb=$1 dist=$2 origin=$3
    local stage
    stage=$(mktemp -d)
    trap 'rm -rf -- "$stage"' EXIT
    dpkg-deb -x "$deb" "$stage"
    local metainfo="$stage/usr/share/metainfo/io.github.julioayusoalende_hue.aio_debian_gui.metainfo.xml"
    [ -f "$metainfo" ] || return 0

    # DEP-11 ofrece la ficha a GNOME Software incluso antes de instalar.
    python3 - "$metainfo" "$origin" "$stage/catalog.xml" <<'PYMETA'
import sys
import xml.etree.ElementTree as ET

metainfo, origin, destination = sys.argv[1:]
component = ET.parse(metainfo).getroot()
ET.SubElement(component, "pkgname").text = "aio-debian-gui"
ET.SubElement(component, "icon", type="remote", width="128", height="128").text = (
    "https://raw.githubusercontent.com/julioayusoalende-hue/AIO-Debian-GUI/main/"
    "package/usr/share/icons/hicolor/128x128/apps/aio-debian-gui.png"
)
categories = ET.SubElement(component, "categories")
ET.SubElement(categories, "category").text = "System"
ET.SubElement(categories, "category").text = "PackageManager"
catalog = ET.Element("components", version="1.0", origin=origin)
catalog.append(component)
ET.ElementTree(catalog).write(destination, encoding="utf-8", xml_declaration=True)
PYMETA
    mkdir -p "$dist/main/dep11"
    appstreamcli convert --format=yaml "$stage/catalog.xml" "$stage/Components-all.yml"
    install -m 0644 "$stage/Components-all.yml" "$dist/main/dep11/Components-all.yml"
    gzip -9nkf "$dist/main/dep11/Components-all.yml"
)

publish_repo() {
    local site=$1 deb=$2 package=$3 label=$4
    local pool_group=${5:-$package}
    local pool="$site/pool/main/${pool_group:0:1}/$pool_group"
    local dist="$site/dists/$CHANNEL"
    local bin="$dist/main/binary-all"
    local files=() debs=() old
    mkdir -p "$pool" "$bin"
    if [[ "$(dpkg-deb -f "$deb" Version)" == 1:* ]]; then
        for old in "$pool/${package}_"*_all.deb; do
            [ -f "$old" ] || continue
            if [[ "$(dpkg-deb -f "$old" Version)" != 1:* ]]; then
                rm -f -- "$old"
            fi
        done
    fi
    cp -f "$deb" "$pool/"
    shopt -s nullglob
    files=("$pool/${package}_"*_all.deb)
    if [ "${#files[@]}" -gt "$KEEP" ]; then
        mapfile -t debs < <(printf '%s\n' "${files[@]}" | sort -V)
        for old in "${debs[@]:0:${#debs[@]}-KEEP}"; do rm -f -- "$old"; done
    fi
    shopt -u nullglob
    ( cd "$site" && dpkg-scanpackages --arch all pool/main /dev/null > "dists/$CHANNEL/main/binary-all/Packages" 2>/dev/null )
    gzip -9nkf "$bin/Packages"
    xz -9ekf "$bin/Packages"
    local indices=(main/binary-all/Packages main/binary-all/Packages.gz main/binary-all/Packages.xz)
    if [ "$CHANNEL" = stable ]; then
        if [ "$package" = aio-debian-gui ]; then
            publish_appstream "$deb" "$dist" "$label"
        fi
        if [ -f "$dist/main/dep11/Components-all.yml.gz" ]; then
            indices+=(main/dep11/Components-all.yml main/dep11/Components-all.yml.gz)
        fi
    fi
    hashes() {
        ( cd "$dist" && for f in "${indices[@]}"; do
            printf ' %s %16d %s\n' "$($1 "$f" | cut -d' ' -f1)" "$(stat -c %s "$f")" "$f"
        done )
    }
    {
        echo "Origin: $label"
        echo "Label: $label"
        echo "Suite: $CHANNEL"
        echo "Codename: $CHANNEL"
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
if [ -n "$AYUSOS_DEB" ]; then
    publish_repo "$SITE" "$AYUSOS_DEB" ayusos-control-center aio-debian-gui
fi
if [ -n "$HOST_DEB" ]; then
    publish_repo "$SITE/host-repo" "$HOST_DEB" aio-debian-gui-host aio-debian-gui-host aio-debian-gui
fi

# --- Clave pública y portada -----------------------------------------------------------
if [ "$CHANNEL" = stable ]; then
    cp -f "$KEYRING" "$SITE/aio-debian-gui.gpg"
    touch "$SITE/.nojekyll"
    cp -f "$ROOT/scripts/site-index.html" "$SITE/index.html"
fi
echo "Repositorio actualizado en $SITE (firmado con $FPR)"
