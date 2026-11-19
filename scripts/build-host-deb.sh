#!/bin/bash
# Construye solo el backend del anfitrión con la versión de la GUI.
set -euo pipefail
cd "$(dirname "$0")/.."

[ "$#" -le 1 ] || { echo "Uso: $0 [directorio-de-salida]" >&2; exit 1; }
OUTPUT_DIR=${1:-dist}
VERSION=$(sed -n 's/^Version: //p' package/DEBIAN/control)
VERSION=${VERSION#*:}
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "Versión del paquete principal no válida." >&2; exit 1;
}
python3 - "$VERSION" <<'PY'
import ast
from pathlib import Path
import re
import sys

version = sys.argv[1]
tree = ast.parse(Path("package/usr/lib/aio-debian-gui/aio_core/scheduler.py").read_text())
values = [node.value.value for node in tree.body
          if isinstance(node, ast.Assign)
          and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
          and isinstance(node.value, ast.Constant)]
helper = Path("package/usr/lib/aio-debian-gui/aio-debian-gui-helper").read_text()
if values != [version] or re.findall(r"^HELPER_VERSION=(.*)$", helper, re.M) != [version]:
    raise SystemExit("Las versiones del helper, programador y paquete principal no coinciden.")
PY

mkdir -p "$OUTPUT_DIR"
BUILD_DIR="$OUTPUT_DIR/host-package-build-$$"
mkdir -m 700 "$BUILD_DIR"
trap 'rm -rf -- "$BUILD_DIR"' EXIT
STAGE="$BUILD_DIR/package"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/lib/aio-debian-gui/aio_core" \
    "$STAGE/usr/lib/systemd/system" "$STAGE/usr/share/polkit-1/actions" \
    "$STAGE/usr/share/keyrings" \
    "$STAGE/usr/share/doc/aio-debian-gui-host"
cat host-package/DEBIAN/control > "$STAGE/DEBIAN/control"
printf 'Version: %s\n' "$VERSION" >> "$STAGE/DEBIAN/control"
install -m 755 host-package/DEBIAN/postinst host-package/DEBIAN/postrm "$STAGE/DEBIAN/"
install -m 755 package/usr/lib/aio-debian-gui/{aio-debian-gui-helper,aio-apt-sources-backup,aio-grub-settings} "$STAGE/usr/lib/aio-debian-gui/"
install -m 755 host-package/usr/lib/aio-debian-gui/aio-host-scheduler "$STAGE/usr/lib/aio-debian-gui/"
install -m 644 package/usr/lib/aio-debian-gui/aio_core/{__init__,scheduler,preflight}.py \
    "$STAGE/usr/lib/aio-debian-gui/aio_core/"
install -m 644 package/usr/lib/aio-debian-gui/aio_core/host_repository.py \
    host-package/usr/lib/aio-debian-gui/aio_core/{host_requests,host_updater}.py \
    "$STAGE/usr/lib/aio-debian-gui/aio_core/"
install -m 755 host-package/usr/lib/aio-debian-gui/aio-host-update "$STAGE/usr/lib/aio-debian-gui/"
install -m 644 host-package/usr/lib/systemd/system/aio-debian-gui-host-update.{service,timer} \
    "$STAGE/usr/lib/systemd/system/"
mkdir -p "$STAGE/usr/lib/systemd/system/timers.target.wants"
ln -s ../aio-debian-gui-host-update.timer \
    "$STAGE/usr/lib/systemd/system/timers.target.wants/aio-debian-gui-host-update.timer"
install -m 644 host-package/usr/lib/systemd/system/aio-debian-gui-maintenance@.service \
    "$STAGE/usr/lib/systemd/system/"
install -m 644 package/usr/share/polkit-1/actions/es.aiodebian.gui.policy \
    "$STAGE/usr/share/polkit-1/actions/"
install -m 644 package/usr/share/keyrings/aio-debian-gui.gpg \
    "$STAGE/usr/share/keyrings/aio-debian-gui-host.gpg"
install -m 644 package/usr/share/doc/aio-debian-gui/copyright \
    "$STAGE/usr/share/doc/aio-debian-gui-host/"

find "$STAGE" -type d -exec chmod 755 {} +
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"
find "$STAGE" -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +
SALIDA="$OUTPUT_DIR/aio-debian-gui-host_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$BUILD_DIR/output.deb"
mv -f -- "$BUILD_DIR/output.deb" "$SALIDA"
echo "Paquete creado: $SALIDA"
