"""Comandos para guiar la integración manual en el anfitrión."""
import os
import shlex

APP_ID = "io.github.julioayusoalende_hue.aio_debian_gui"


def commands(formato, appimage=None):
    """Devuelve comandos separados para extracción e instalación, sin ejecutarlos."""
    if formato == "flatpak":
        extract = f"""APP={APP_ID}
for f in aio-debian-gui-helper es.aiodebian.gui.policy aio-debian-gui-maintenance@.service; do
  flatpak run --command=cat "$APP" "/app/share/aio-debian-gui/host-integration/$f" > "$f"
done
for f in __init__.py scheduler.py preflight.py; do
  flatpak run --command=cat "$APP" "/app/lib/aio-debian-gui/aio_core/$f" > "$f"
done"""
    elif formato == "appimage":
        if not appimage or not os.path.isabs(appimage) or "\n" in appimage or "\r" in appimage:
            raise ValueError("No se pudo determinar la ruta absoluta del AppImage.")
        extract = f"""APPIMAGE={shlex.quote(appimage)}
"$APPIMAGE" --appimage-extract >/dev/null
cp squashfs-root/usr/lib/aio-debian-gui/aio-debian-gui-helper .
cp squashfs-root/usr/lib/aio-debian-gui/aio_core/{{__init__,scheduler,preflight}}.py .
cp squashfs-root/usr/lib/systemd/system/aio-debian-gui-maintenance@.service .
cp squashfs-root/usr/share/polkit-1/actions/es.aiodebian.gui.policy ."""
    else:
        raise ValueError("Formato de integración no compatible.")

    extract = f"""(
set -e
INTEGRACION=$(mktemp -d "$HOME/aio-debian-gui-integracion.XXXXXXXX")
cd "$INTEGRACION"
echo "Directorio: $INTEGRACION"
{extract}
echo "Revisa los archivos en $INTEGRACION antes de instalar."
)"""

    install = """(
set -e
for f in aio-debian-gui-helper es.aiodebian.gui.policy aio-debian-gui-maintenance@.service __init__.py scheduler.py preflight.py; do
  test -s "$f" || { echo "Falta $f. Ejecuta este bloque desde el directorio de extracción." >&2; exit 1; }
done
if dpkg-query -W -f='${db:Status-Status}' aio-debian-gui 2>/dev/null | grep -qx installed; then
  echo "El DEB está instalado. Actualízalo con APT; no sobrescribas sus archivos." >&2
  exit 1
fi
for f in /usr/lib/aio-debian-gui/aio-debian-gui-helper /usr/lib/aio-debian-gui/aio_core/__init__.py /usr/lib/aio-debian-gui/aio_core/scheduler.py /usr/lib/aio-debian-gui/aio_core/preflight.py /usr/share/polkit-1/actions/es.aiodebian.gui.policy /usr/lib/systemd/system/aio-debian-gui-maintenance@.service; do
  if resultado=$(LC_ALL=C dpkg-query -S "$f" 2>&1); then
    echo "Archivo gestionado por un paquete: $f. No se instalará la integración." >&2
    exit 1
  elif [ "$resultado" != "dpkg-query: no path found matching pattern $f" ]; then
    echo "No se pudo verificar el propietario de $f: $resultado" >&2
    exit 1
  fi
done
sudo install -D -o root -g root -m 0755 aio-debian-gui-helper /usr/lib/aio-debian-gui/aio-debian-gui-helper
for f in __init__.py scheduler.py preflight.py; do
  sudo install -D -o root -g root -m 0644 "$f" "/usr/lib/aio-debian-gui/aio_core/$f"
done
sudo install -D -o root -g root -m 0644 es.aiodebian.gui.policy /usr/share/polkit-1/actions/es.aiodebian.gui.policy
sudo install -D -o root -g root -m 0644 aio-debian-gui-maintenance@.service /usr/lib/systemd/system/aio-debian-gui-maintenance@.service
sudo systemctl daemon-reload
)"""
    return extract, install
