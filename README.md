# AiO Debian GUI

**Mantenimiento, diagnóstico y configuración de Debian y Ubuntu LTS desde una interfaz gráfica GTK.**

[![Última versión](https://img.shields.io/github/v/release/julioayusoalende-hue/AIO-Debian-GUI?label=versi%C3%B3n)](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest)
[![Licencia GPL-3.0](https://img.shields.io/badge/licencia-GPL--3.0-blue)](LICENSE)
[![Descargas](https://img.shields.io/badge/descargas-Releases-red)](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest)

AiO Debian GUI reúne tareas habituales de administración en una aplicación GTK. Antes de las operaciones delicadas presenta comprobaciones y pide confirmación. Es un proyecto independiente del script de consola [aio-debian](https://github.com/julioayusoalende-hue/aio-debian).

**Descarga la última versión estable desde [Releases](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest).** Allí encontrarás los paquetes disponibles y el archivo `SHA256SUMS`. Las versiones anteriores se conservan en el [historial de releases](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases).

## Funciones

- **Mantenimiento APT:** actualizar índices y paquetes, limpiar caché y retirar dependencias innecesarias, con comprobaciones preventivas y confirmación.
- **Programación:** mantenimiento diario, semanal o mensual; consulta de próximas ejecuciones y resultados. No se programan eliminaciones ni cambios de kernel, controladores o repositorios.
- **Diagnóstico:** actualiza los índices APT con autorización de administrador y después informa sobre espacio, APT/dpkg, actualizaciones, DKMS, reinicios y servicios. No instala ni elimina paquetes.
- **Sistema y hardware:** gestión de repositorios, kernel y Mesa de Backports; detección NVIDIA con instalación conservadora en Debian. Algunas operaciones tienen requisitos y bloqueos adicionales.
- **Copias de seguridad:** acceso a Timeshift y Respaldos (Déjà Dup); si no están instalados, AiO ofrece instalarlos con confirmación y autorización de administrador.
- **Apps recomendadas:** catálogo en dos columnas con GIMP, VLC, Celluloid, Plex, Switcheroo, Video Downloader, HandBrake, Spotify, Feishin, Google Chrome, Brave y Gear Lever. Distingue DEB y Flatpak, indica qué formato está instalado y no abre las aplicaciones tras instalarlas. Las instalaciones requieren confirmación; los DEB externos se descargan e instalan manualmente.
- **Terminal:** pestaña interactiva con Bash que recibe en directo la salida de mantenimiento. El botón «Ver en Terminal» de la consola integrada abre esta pestaña. Incluye accesos para limpiar la pantalla, ejecutar Fastfetch y abrir Nautilus en `admin:/` (puede solicitar autorización). Los accesos ejecutan procesos independientes, sin enviar texto a la sesión interactiva. En Flatpak se ejecutan en el anfitrión; se aplican los permisos habituales del usuario.
- **Escritorio:** integración con Flatpak, AppImage y complementos de GNOME; interfaz en español, inglés, francés y chino, con temas claro y oscuro.

La aplicación es compatible con Debian 12 o superior y Ubuntu 24.04/26.04 LTS. Algunas tareas dependen de la distribución y se bloquean cuando no son compatibles.

El diagnóstico solicita autorización para renovar los índices APT antes de comprobar las actualizaciones del sistema y de AiO. Si se rechaza la autorización o falla la actualización, informa del error y no presenta las lecturas APT como actualizadas. Flatpak necesita un asistente compatible instalado en el anfitrión para renovar los índices.

## Releases disponibles

Para instalar o actualizar AiO, usa la [última release estable](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest). Las versiones anteriores siguen disponibles en [GitHub Releases](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases). Cada una incluye DEB, AppImage, Flatpak y `SHA256SUMS`.

| Versión | Estado |
|---|---|
| [v2.11.3](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.11.3) | Última estable |
| [v2.10.12](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.10.12) | Histórica |
| [v2.10.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.10.0) | Histórica |
| [v2.8.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.8.0) | Histórica |
| [v2.7.5](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.7.5) | Histórica |
| [v2.7.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.7.0) | Histórica |
| [v2.6.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.6.0) | Histórica |
| [v2.4.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.4.0) | Histórica |
| [v2.3.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.3.0) | Histórica |
| [v2.2.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.2.0) | Histórica |
| [v2.1.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.1.0) | Histórica |
| [v2.0.0](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v2.0.0) | Histórica |
| [v1.2.4](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/tag/v1.2.4) | Histórica |

Consulta las notas de cada versión en su página de GitHub.

## Instalación

Descarga el archivo de la release que quieras instalar. En los ejemplos, sustituye `VERSION` por el número del archivo descargado.

### DEB (recomendado)

Descarga `aio-debian-gui_VERSION_all.deb` e instálalo:

```bash
sudo apt install ./aio-debian-gui_VERSION_all.deb
```

El paquete instala las dependencias y configura el repositorio APT firmado del proyecto. Abre AiO desde el menú de aplicaciones o ejecuta `aio-debian-gui` sin sudo.

Para actualizar únicamente AiO:

```bash
sudo apt update
sudo apt install --only-upgrade aio-debian-gui
```

También puedes usar **Menú → Buscar actualizaciones**. Cierra y vuelve a abrir la aplicación después de actualizarla; si se ofrece reiniciar AiO, puedes aceptar.

### AppImage

Descarga `aio-debian-gui_VERSION_x86_64.AppImage` y ejecútalo:

```bash
chmod +x aio-debian-gui_VERSION_x86_64.AppImage
./aio-debian-gui_VERSION_x86_64.AppImage
```

Antes de abrirlo, instala sus dependencias del anfitrión:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91 librsvg2-common pkexec
```

Requiere arquitectura `x86_64` y FUSE 2 (`libfuse2` en Debian 12 o `libfuse2t64` en Debian 13). Instala `fastfetch` para usar su acceso en la terminal. La aplicación no necesita que instales el paquete DEB.

Para actualizar, usa **Menú → Buscar actualizaciones**: consulta GitHub Releases y descarga el nuevo AppImage tras verificar SHA-256, sin sustituir el ejecutable activo. Cierra AiO y abre el archivo nuevo; actualiza también cualquier acceso directo que apunte al anterior. Si usas programación, vuelve a guardar el horario con el nuevo AppImage antes de retirar el archivo antiguo.

### Flatpak

Para las actualizaciones desde el repositorio firmado del proyecto, instala Flatpak y la referencia oficial:

```bash
sudo apt install flatpak
flatpak install --user https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakref
```

También puedes descargar `aio-debian-gui_VERSION_x86_64.flatpak` desde GitHub Releases e instalarlo con `flatpak install --user ./aio-debian-gui_VERSION_x86_64.flatpak`. Este bundle por sí solo no configura el repositorio de actualizaciones; para recibirlas, usa el `.flatpakref`. Consulta la [guía de actualizaciones Flatpak](docs/flatpak-actualizaciones.md).

Para abrirla:

```bash
flatpak run io.github.julioayusoalende_hue.aio_debian_gui
```

Para actualizar únicamente AiO desde su origen configurado:

```bash
flatpak update --user io.github.julioayusoalende_hue.aio_debian_gui
```

También puedes usar **Menú → Buscar actualizaciones**. Cierra y vuelve a abrir AiO para cargar la nueva versión. La interfaz se distribuye desde el repositorio propio del proyecto, independiente de Flathub; Flathub proporciona el runtime.

### Verificar las descargas

Descarga `SHA256SUMS` junto con los paquetes que quieras comprobar y ejecuta:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

## Programación y permisos

Las ediciones DEB, Flatpak y AppImage usan el mismo asistente y programador del anfitrión. AiO comprueba la integración al abrirse y reutiliza una instalación compatible, independientemente de la versión de la interfaz.

Programar, pausar o eliminar un horario requiere autorización de administrador. Los temporizadores de systemd conservan sus horarios durante las actualizaciones. Si AiO recupera un horario existente, respeta si estaba activado o pausado.

Antes de cambiar kernel, Mesa, repositorios o controladores, haz una copia de seguridad y revisa las advertencias de la tarea. La vuelta de kernel y Mesa desde Backports no cambia por sí sola el kernel de arranque; NVIDIA puede quedar bloqueado cuando la compatibilidad no se pueda verificar. La opción de Polkit sin contraseña es opcional, está desactivada inicialmente y reduce la protección de la cuenta.

### Integración del programador para AppImage y Flatpak

Al abrir Flatpak o AppImage, AiO comprueba la integración y deja en cola las actualizaciones o reparaciones que el servicio firmado puede aplicar. Cuando se necesita instalar la integración, puedes hacerlo desde **Menú → Guía de integración del anfitrión**. El sistema solicita la autorización de administrador al confirmar esa acción.

Si el asistente lo proporciona un DEB, APT se encarga de actualizarlo. Si se instaló desde Flatpak o AppImage, systemd aplica las actualizaciones firmadas cuando no hay mantenimiento ni operaciones de paquetes en curso. Los horarios se guardan en el anfitrión y se comparten entre los formatos.

## Desarrollo

Para clonar el proyecto, ejecutar las comprobaciones y consultar la estructura de paquetes:

```bash
git clone https://github.com/julioayusoalende-hue/AIO-Debian-GUI.git
cd AIO-Debian-GUI
./scripts/check.sh
```

El catálogo de traducciones de la interfaz está en
`package/usr/lib/aio-debian-gui/aio_core/translations.py`; la selección del
idioma sigue gestionándose en la interfaz. El seguimiento del tema GTK está en
`package/usr/lib/aio-debian-gui/aio_core/gtk_appearance.py` y el diálogo de
programación en `package/usr/lib/aio-debian-gui/aio_core/gtk_scheduler.py`.

## Licencia

GNU GPL v3 o posterior. Consulta [LICENSE](LICENSE). Sin ninguna garantía.

### Mantenimiento de Snap

Si `snapd` está instalado en el anfitrión, aparece **Actualizar y limpiar Snap**, seleccionada en el mantenimiento completo y disponible como tarea opcional del programador. Ejecuta `snap refresh` y, si termina correctamente, elimina mediante `snap remove --revision` las revisiones numéricas deshabilitadas más antiguas. Conserva la revisión activa y una revisión deshabilitada por aplicación para poder volver atrás. No borra datos, instantáneas ni archivos de la caché directamente, y no instala snapd. Si snapd se desinstala después de guardar un horario, la tarea se omite sin interrumpir las demás. Las programaciones existentes mantienen su selección de tareas.
