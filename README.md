# AiO Debian GUI

**Mantenimiento, diagnóstico y configuración de Debian desde una interfaz gráfica.**

[![Última versión](https://img.shields.io/github/v/release/julioayusoalende-hue/AIO-Debian-GUI?label=versi%C3%B3n)](../../releases/latest)
[![Licencia GPL-3.0](https://img.shields.io/badge/licencia-GPL--3.0-blue)](LICENSE)
[![Descargas](https://img.shields.io/badge/descargas-Releases-red)](../../releases/latest)

AiO Debian GUI reúne tareas habituales de administración en una aplicación GTK. Antes de las operaciones delicadas presenta comprobaciones y pide confirmación. Es un proyecto independiente del script de consola [aio-debian](https://github.com/julioayusoalende-hue/aio-debian).

**Descarga la última versión estable desde [Releases](../../releases/latest).** Allí encontrarás los paquetes disponibles y el archivo `SHA256SUMS`. Las versiones anteriores se conservan en el [historial de releases](../../releases).

## Funciones

- **Mantenimiento APT:** actualizar índices y paquetes, limpiar caché y retirar dependencias innecesarias, con comprobaciones preventivas y confirmación.
- **Programación:** mantenimiento diario, semanal o mensual; consulta de próximas ejecuciones y resultados. No se programan eliminaciones ni cambios de kernel, controladores o repositorios.
- **Diagnóstico:** actualiza los índices APT con autorización de administrador y después informa sobre espacio, APT/dpkg, actualizaciones, DKMS, reinicios y servicios. No instala ni elimina paquetes.
- **Sistema y hardware:** gestión de repositorios, kernel y Mesa de Backports; detección NVIDIA con instalación conservadora en Debian. Algunas operaciones tienen requisitos y bloqueos adicionales.
- **Copias de seguridad:** acceso a Timeshift y Respaldos (Déjà Dup); si no están instalados, AiO ofrece instalarlos con confirmación y autorización de administrador.
- **Apps recomendadas:** catálogo en dos columnas con GIMP, VLC, Celluloid, Plex, Switcheroo, Video Downloader, HandBrake, Spotify, Feishin y Google Chrome. Distingue DEB y Flatpak, indica qué formato está instalado y no abre las aplicaciones tras instalarlas. Las instalaciones requieren confirmación; los DEB externos se descargan e instalan manualmente.
- **Terminal:** pestaña interactiva con Bash que muestra Fastfetch al iniciar si está instalado. En Flatpak ejecuta los comandos en el anfitrión; se aplican los permisos habituales del usuario.
- **Escritorio:** integración con Flatpak, AppImage y complementos de GNOME; interfaz en español, inglés, francés y chino, con temas claro y oscuro.

La aplicación es compatible con Debian 12 o superior y Ubuntu 24.04/26.04 LTS. Algunas tareas dependen de la distribución y se bloquean cuando no son compatibles.

El diagnóstico solicita autorización para renovar los índices APT antes de comprobar las actualizaciones del sistema y de AiO. Si se rechaza la autorización o falla la actualización, informa del error y no presenta las lecturas APT como actualizadas. Flatpak necesita el asistente de la misma versión instalado en el anfitrión para renovar los índices.

## Novedades recientes

- **2.9.0:** terminal interactiva con Fastfetch al iniciar cuando está instalado.
- **2.8.3:** incorpora iconos para Celluloid, GIMP, Spotify y VLC en «Apps recomendadas».
- **2.8.2:** corrige la instalación de Video Downloader y muestra los formatos instalados sin abrir las aplicaciones automáticamente.
- **2.8.1:** mejora los iconos de aplicaciones recomendadas cuando sus logos no están disponibles en el sistema.
- **2.8.0:** catálogo alfabético de diez apps recomendadas, con canales DEB y Flatpak disponibles y selección explícita del formato.
- **2.7.10:** corrige la inicialización de la pestaña Backup y conserva la consola y los controles habituales.
- **2.7.9:** pestaña Backup con Timeshift y Respaldos (Déjà Dup), e instalación opcional autorizada.
- **2.7.8:** guía integrada para instalar o actualizar el asistente del anfitrión en Flatpak y AppImage, con revisión de archivos y autorización explícita.
- **2.7.7:** actualización autorizada de los índices APT antes del diagnóstico, con aviso si falla.
- **2.7.6:** diagnóstico más completo de paquetes actualizables y aviso sobre los índices APT locales que pueden ocultar actualizaciones.
- **2.7.5:** el paquete DEB instala `needrestart`; si la comprobación de reinicio no está disponible o falla, AiO informa del error en lugar de indicar que no hace falta reiniciar. Para AppImage y Flatpak, instala `needrestart` en el anfitrión si quieres usar esa comprobación.
- **2.7.4:** correcciones para las notificaciones de escritorio y el aviso de reinicio del mantenimiento programado.
- **2.7.3:** si el mantenimiento recomienda reiniciar, AiO abre el aviso en la sesión gráfica; nunca reinicia el equipo automáticamente.
- **2.7.1–2.7.0:** programación de tareas con temporizadores de systemd, recuperación de ejecuciones pendientes al encender el equipo y resultados visibles aunque AiO esté cerrado. En AppImage y Flatpak se requiere instalar una integración administrativa en el anfitrión.

Consulta las notas completas en [Releases](../../releases).

## Instalación

En cada release, descarga el archivo correspondiente y sustituye `X.Y.Z` por su versión.

### DEB (recomendado)

Descarga `aio-debian-gui_X.Y.Z_all.deb` e instálalo:

```bash
sudo apt install ./aio-debian-gui_X.Y.Z_all.deb
```

El paquete configura el repositorio APT del proyecto para recibir futuras actualizaciones con APT.

### AppImage

Descarga `aio-debian-gui_X.Y.Z_x86_64.AppImage` y ejecútalo:

```bash
chmod +x aio-debian-gui_X.Y.Z_x86_64.AppImage
./aio-debian-gui_X.Y.Z_x86_64.AppImage
```

Requiere arquitectura `x86_64`, Python 3, GTK 3, `gir1.2-vte-2.91`, Polkit y FUSE 2 (`libfuse2` en Debian 12 o `libfuse2t64` en Debian 13). Instala `fastfetch` para mostrar el resumen al abrir la terminal. La aplicación no necesita que instales el paquete DEB.

### Flatpak

Para las actualizaciones desde el repositorio firmado del proyecto, instala Flatpak y la referencia oficial:

```bash
sudo apt install flatpak
flatpak install --user https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakref
```

La release estable vigente también incluye `aio-debian-gui_X.Y.Z_x86_64.flatpak`, que se puede instalar con `flatpak install --user ./aio-debian-gui_X.Y.Z_x86_64.flatpak`. Este bundle por sí solo no configura el repositorio de actualizaciones; para recibirlas, usa el `.flatpakref`. Consulta la [guía de actualizaciones Flatpak](docs/flatpak-actualizaciones.md).

### Verificar las descargas

Descarga `SHA256SUMS` junto con los paquetes que quieras comprobar y ejecuta:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

## Programación y permisos

En la instalación DEB, la integración del programador se instala automáticamente. AppImage y Flatpak necesitan una integración persistente en el sistema anfitrión para programar tareas con AiO cerrado; sigue los pasos de la sección [Integración del programador](#integración-del-programador-para-appimage-y-flatpak).

Programar, pausar o eliminar un horario requiere autorización de administrador. Instalar o actualizar AiO no activa horarios por sí solo. Los temporizadores usan systemd y no encienden un equipo apagado. Para AppImage y Flatpak también se necesita `libnotify-bin` en el anfitrión para las notificaciones y `needrestart` para comprobar si hace falta reiniciar.

Antes de cambiar kernel, Mesa, repositorios o controladores, haz una copia de seguridad y revisa las advertencias de la tarea. La vuelta de kernel y Mesa desde Backports no cambia por sí sola el kernel de arranque; NVIDIA puede quedar bloqueado cuando la compatibilidad no se pueda verificar. La opción de Polkit sin contraseña es opcional, está desactivada inicialmente y reduce la protección de la cuenta.

### Integración del programador para AppImage y Flatpak

En AppImage o Flatpak, abre **Menú → Guía de integración del anfitrión**. La guía muestra dos bloques que puedes copiar a una terminal del anfitrión: uno extrae los archivos y otro los instala tras tu revisión y autorización. La aplicación no ejecuta los comandos automáticamente. La guía también está disponible desde la ventana de programación cuando la integración no está lista y desde el diagnóstico si falla la actualización APT.

Estos pasos instalan en el anfitrión el asistente, los módulos de programación, la política Polkit y el servicio systemd incluidos en la misma versión de AiO. No los ejecutes si el paquete DEB ya gestiona esos archivos. Requiere autorización de administrador.

Prepara un directorio temporal privado y extrae los archivos desde el formato que utilizas.

Para **Flatpak**:

```bash
set -e
INTEGRACION=$(mktemp -d "$HOME/aio-debian-gui-integracion.XXXXXXXX")
cd "$INTEGRACION"
APP=io.github.julioayusoalende_hue.aio_debian_gui
for f in aio-debian-gui-helper es.aiodebian.gui.policy aio-debian-gui-maintenance@.service; do
  flatpak run --command=cat "$APP" "/app/share/aio-debian-gui/host-integration/$f" > "$f"
done
for f in __init__.py scheduler.py preflight.py; do
  flatpak run --command=cat "$APP" "/app/lib/aio-debian-gui/aio_core/$f" > "$f"
done
```

Para **AppImage**, define `APPIMAGE` con la ruta del archivo descargado:

```bash
set -e
INTEGRACION=$(mktemp -d "$HOME/aio-debian-gui-integracion.XXXXXXXX")
cd "$INTEGRACION"
APPIMAGE="$HOME/Descargas/aio-debian-gui_X.Y.Z_x86_64.AppImage"
"$APPIMAGE" --appimage-extract
cp squashfs-root/usr/lib/aio-debian-gui/aio-debian-gui-helper .
cp squashfs-root/usr/lib/aio-debian-gui/aio_core/{__init__,scheduler,preflight}.py .
cp squashfs-root/usr/lib/systemd/system/aio-debian-gui-maintenance@.service .
cp squashfs-root/usr/share/polkit-1/actions/es.aiodebian.gui.policy .
```

Comprueba que se extrajeron los seis archivos antes de instalarlos como administrador:

```bash
set -e
for f in aio-debian-gui-helper es.aiodebian.gui.policy aio-debian-gui-maintenance@.service __init__.py scheduler.py preflight.py; do
  test -s "$f" || { echo "Falta $f; no se instalará la integración." >&2; exit 1; }
done
sudo install -D -o root -g root -m 0755 aio-debian-gui-helper /usr/lib/aio-debian-gui/aio-debian-gui-helper
for f in __init__.py scheduler.py preflight.py; do
  sudo install -D -o root -g root -m 0644 "$f" "/usr/lib/aio-debian-gui/aio_core/$f"
done
sudo install -D -o root -g root -m 0644 es.aiodebian.gui.policy /usr/share/polkit-1/actions/es.aiodebian.gui.policy
sudo install -D -o root -g root -m 0644 aio-debian-gui-maintenance@.service /usr/lib/systemd/system/aio-debian-gui-maintenance@.service
sudo systemctl daemon-reload
```

## Desarrollo

Para clonar el proyecto, ejecutar las comprobaciones y consultar la estructura de paquetes:

```bash
git clone https://github.com/julioayusoalende-hue/AIO-Debian-GUI.git
cd AIO-Debian-GUI
./scripts/check.sh
```

## Licencia

GNU GPL v3 o posterior. Consulta [LICENSE](LICENSE). Sin ninguna garantía.
