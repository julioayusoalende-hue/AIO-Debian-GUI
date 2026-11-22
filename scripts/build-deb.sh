#!/bin/bash
# Construye el paquete .deb en dist/ (reproducible: permisos y fechas normalizados)
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^Version: //p' package/DEBIAN/control)
[ -n "$VERSION" ] || { echo "No se pudo leer la versión de package/DEBIAN/control" >&2; exit 1; }
EPOCH=""
if [[ "$VERSION" == *:* ]]; then
    EPOCH="${VERSION%%:*}:"
fi
VERSION=${VERSION#*:}
if [ "$#" -ne 0 ]; then
    if [ "$#" -ne 2 ] || [ "$1" != "--testing-version" ] ||
       [[ ! "$2" =~ ^[0-9]+\.[0-9]+\.[0-9]+~testing\.[1-9][0-9]*\.[1-9][0-9]*$ ]]; then
        echo "Uso: $0 [--testing-version X.Y.Z~testing.N.INTENTO]" >&2
        exit 2
    fi
    TESTING_VERSION=$2
else
    TESTING_VERSION=""
fi
PUBLIC_VERSION=${TESTING_VERSION:-$VERSION}
SALIDA="dist/aio-debian-gui_${PUBLIC_VERSION}_all.deb"

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
cp -a package/. "$STAGE/"

if [ -n "$TESTING_VERSION" ]; then
    python3 - "$STAGE" "$EPOCH" "$VERSION" "$TESTING_VERSION" "assets/testing-icons" <<'PY'
from pathlib import Path
import shutil
import sys

stage, epoch, old, new, testing_icons = sys.argv[1:]
stable_icon, testing_icon = "aio-debian-gui", "aio-debian-gui-testing"
files = [
    ("DEBIAN/control", f"Version: {epoch}{old}\n", f"Version: {epoch}{new}\n"),
    ("usr/lib/aio-debian-gui/aio_core/scheduler.py", f"VERSION = '{old}'\n", f"VERSION = '{new}'\n"),
    ("usr/lib/aio-debian-gui/aio-debian-gui-helper", f"HELPER_VERSION={old}\n", f"HELPER_VERSION={new}\n"),
    ("usr/bin/aio-debian-gui", f'APP_ICON_NAME = "{stable_icon}"\n', f'APP_ICON_NAME = "{testing_icon}"\n'),
    ("usr/share/applications/aio-debian-gui.desktop", f"Icon={stable_icon}\n", f"Icon={testing_icon}\n"),
    ("usr/share/polkit-1/actions/es.aiodebian.gui.policy",
     f"<icon_name>{stable_icon}</icon_name>", f"<icon_name>{testing_icon}</icon_name>"),
]
for name, original, replacement in files:
    path = Path(stage, name)
    text = path.read_text(encoding="utf-8")
    if text.count(original) != 1:
        raise SystemExit(f"No se pudo preparar el archivo de Testing: {name}")
    path.write_text(text.replace(original, replacement), encoding="utf-8")
icon_root = Path(stage, "usr/share/icons/hicolor")
for icon in sorted(icon_root.glob(f"*/apps/{stable_icon}.png")):
    relative = icon.with_name(f"{testing_icon}.png").relative_to(icon_root)
    shutil.copyfile(Path(testing_icons, relative), icon_root / relative)
    icon.unlink()
PY
fi

NOTAS="$STAGE/usr/share/aio-debian-gui/release-notes.txt"
SECCION=${PUBLIC_VERSION%%[~-]*}
awk -v version="${PUBLIC_VERSION}" -v seccion="$SECCION" '
    $0 == "## " seccion { activo = 1; encontrados++; next }
    /^## / { activo = 0 }
    activo && NF {
        if (!contenido++) print version
        sub(/^- /, "• ")
        gsub(/`/, "")
        print
    }
    END { if (encontrados != 1 || !contenido) exit 1 }
' CHANGELOG.md > "$NOTAS" || {
    echo "El CHANGELOG debe contener una única sección con novedades para ${SECCION}." >&2
    exit 1
}

# La misma versión y las mismas notas alimentan AiO y los centros de software.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"
python3 - "$STAGE" "$PUBLIC_VERSION" <<'PYMETA'
from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import sys
import xml.etree.ElementTree as ET

stage, version = Path(sys.argv[1]), sys.argv[2]
component = stage / "usr/share/metainfo/io.github.julioayusoalende_hue.aio_debian_gui.metainfo.xml"
tree = ET.parse(component)
releases = ET.SubElement(tree.getroot(), "releases")
date = datetime.fromtimestamp(int(os.environ["SOURCE_DATE_EPOCH"]), timezone.utc).date()
release = ET.SubElement(releases, "release", version=version, date=date.isoformat(),
                        type="development" if "~" in version or "+preview" in version else "stable")
description = ET.SubElement(release, "description")
points = ET.SubElement(description, "ul")
notes = stage / "usr/share/aio-debian-gui/release-notes.txt"
for line in notes.read_text(encoding="utf-8").splitlines()[1:]:
    if line.strip():
        ET.SubElement(points, "li").text = line.removeprefix("• ").strip()
ET.indent(tree, space="  ")
tree.write(component, encoding="utf-8", xml_declaration=True)

size = 0
seen = set()
for top in stage.iterdir():
    if top.name == "DEBIAN":
        continue
    for path in (top, *top.rglob("*")):
        info = path.lstat()
        if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            inode = (info.st_dev, info.st_ino)
            if inode in seen:
                continue
            seen.add(inode)
            size += (info.st_size + 1023) // 1024
        else:
            size += 1
control = stage / "DEBIAN/control"
fields = control.read_text(encoding="utf-8").splitlines()
fields = [field for field in fields if not field.startswith("Installed-Size:")]
description_index = next(i for i, field in enumerate(fields) if field.startswith("Description:"))
fields.insert(description_index, f"Installed-Size: {size}")
control.write_text("\n".join(fields) + "\n", encoding="utf-8")
PYMETA

# Permisos normalizados (git/zip no los conservan siempre)
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/usr/bin/aio-debian-gui" \
          "$STAGE/usr/lib/aio-debian-gui/"{aio-debian-gui-helper,aio-apt-sources-backup,aio-grub-settings,aio-clock-enable}

chmod 755 "$STAGE/usr/lib/aio-debian-gui/software_manager/admin.py"

# Fecha fija = fecha del último commit (o la actual si no hay git)
find "$STAGE" -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +

mkdir -p dist
rm -f "$SALIDA"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$SALIDA"
echo "Paquete creado: $SALIDA"
