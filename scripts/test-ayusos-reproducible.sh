#!/bin/bash
# El DEB de AyusOS debe ser reproducible con el mismo SOURCE_DATE_EPOCH.
set -euo pipefail
cd "$(dirname "$0")/.."

TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
export SOURCE_DATE_EPOCH=1700000000

bash ayusos-control-center/build-deb.sh >/dev/null
VERSION=$(sed -n 's/^Version: //p' ayusos-control-center/package/DEBIAN/control)
DEB="ayusos-control-center/dist/ayusos-control-center_${VERSION}_all.deb"
cp "$DEB" "$TMP/first.deb"

bash ayusos-control-center/build-deb.sh >/dev/null
cmp "$TMP/first.deb" "$DEB"
sha256sum "$DEB"
echo "✔ ayusos-control-center reproducible con el mismo SOURCE_DATE_EPOCH"
