# AiO Debian GUI

**Mantenimiento, diagnóstico y configuración de Debian y Ubuntu LTS desde una interfaz gráfica GTK.**

[![Última versión](https://img.shields.io/github/v/release/julioayusoalende-hue/AIO-Debian-GUI?label=versi%C3%B3n)](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest)
[![Licencia GPL-3.0](https://img.shields.io/badge/licencia-GPL--3.0-blue)](LICENSE)
[![Descargas](https://img.shields.io/badge/descargas-Releases-red)](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest)

AiO Debian GUI reúne tareas habituales de administración en una aplicación GTK. Antes de las operaciones delicadas presenta comprobaciones y pide confirmación. Es un proyecto independiente del script de consola [aio-debian](https://github.com/julioayusoalende-hue/aio-debian).

**Descarga la última versión estable desde [Releases](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest).** La distribución incluye el paquete Debian y el archivo `SHA256SUMS`.

## Funciones

- **Mantenimiento APT:** actualizar índices y paquetes, limpiar caché y retirar dependencias innecesarias, con comprobaciones preventivas y confirmación.
- **Programación:** mantenimiento diario, semanal o mensual; consulta de próximas ejecuciones y resultados. No se programan eliminaciones ni cambios de kernel, controladores o repositorios.
- **Diagnóstico:** actualiza los índices APT con autorización de administrador y después informa sobre espacio, APT/dpkg, actualizaciones, DKMS, reinicios y servicios. No instala ni elimina paquetes.
- **Sistema y hardware:** gestión de repositorios, kernel y Mesa de Backports; detección NVIDIA con instalación conservadora en Debian. Algunas operaciones tienen requisitos y bloqueos adicionales.
- **Copias de seguridad:** copia y restauración de repositorios APT, y acceso a Timeshift y Respaldos (Déjà Dup); si no están instalados, AiO ofrece instalarlos con confirmación y autorización de administrador.
- **Apps recomendadas:** catálogo en dos columnas con GIMP, VLC, Celluloid, Plex, Switcheroo, Video Downloader, HandBrake, Spotify, Feishin, Google Chrome, Brave, Gear Lever, Kitty y Ghostty. Distingue DEB y Flatpak, indica qué formato está instalado y no abre las aplicaciones tras instalarlas. Las instalaciones requieren confirmación; los DEB externos se descargan e instalan manualmente.
- **Terminal:** pestaña interactiva con Bash que recibe en directo la salida de mantenimiento. El botón «Ver en Terminal» de la consola integrada abre esta pestaña. Incluye accesos para limpiar la pantalla, ejecutar Fastfetch y abrir Nautilus en `admin:/` (puede solicitar autorización). **Editar** y el menú contextual permiten copiar, pegar y seleccionar. En **Configuración y mantenimiento**, **Aplicar diseño de Fastfetch** instala el diseño incluido para tu usuario y guarda una copia de la configuración anterior. **Restaurar diseño anterior de Fastfetch** recupera esa copia o vuelve a los valores predeterminados si no había configuración de usuario. Los accesos ejecutan procesos independientes, sin enviar texto a la sesión interactiva.
- **Escritorio:** gestión de aplicaciones Flatpak, soporte FUSE y complementos de GNOME; interfaz en español, inglés, francés y chino, con temas claro y oscuro.

La aplicación es compatible con Debian 12 o superior y Ubuntu 24.04/26.04 LTS. Algunas tareas dependen de la distribución y se bloquean cuando no son compatibles.

El diagnóstico solicita autorización para renovar los índices APT antes de comprobar las actualizaciones del sistema y de AiO. Si se rechaza la autorización o falla la actualización, informa del error y no presenta las lecturas APT como actualizadas.

## Instalar

Descarga `aio-debian-gui_1.0.6_all.deb` y abre un terminal en la carpeta de descargas.

```bash
sudo apt install ./aio-debian-gui_1.0.6_all.deb
```

El paquete instala `needrestart` como dependencia para comprobar si hace falta reiniciar y configura el repositorio APT firmado de AiO Debian. Usa **Menú → Buscar actualizaciones** o el gestor de paquetes para instalar futuras versiones. APT identifica esta serie con la época `1:` para permitir la actualización desde las versiones anteriores.

### Verificar las descargas

Descarga `SHA256SUMS` junto con los paquetes que quieras comprobar y ejecuta:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

## Copiar y restaurar repositorios APT

En **Backup**, pulsa **Copiar repositorios APT** y elige una carpeta la primera vez. AiO guarda `repositorios-apt.json` y recuerda la carpeta para **Restaurar repositorios APT**. Usa **Cambiar carpeta de copia** para elegir otra ubicación.

La copia incluye `/etc/apt/sources.list`, las fuentes `.list` y `.sources` de `/etc/apt/sources.list.d` y los llaveros de APT de `/etc/apt`. Las claves instaladas por paquetes en `/usr/share/keyrings` se recuperan reinstalando sus paquetes. Guarda la copia en una ubicación privada si tus fuentes contienen credenciales.

Las dos operaciones piden autorización de administrador. Al restaurar, AiO sustituye las fuentes actuales por las de la copia y conserva las claves adicionales. Después puedes renovar los índices desde **Configuración y mantenimiento**.

## Copiar y restaurar ajustes del escritorio

En **Backup**, usa **Copiar ajustes del escritorio** y **Restaurar ajustes del escritorio** desde tu sesión de GNOME o KDE Plasma. AiO guarda un ZIP por escritorio en la misma carpeta que las copias APT.

- **GNOME** guarda preferencias de GNOME Shell, favoritos del dock, atajos, ajustes de Mutter y las extensiones instaladas en tu cuenta. La posición de cada archivo en el escritorio depende de la extensión que lo gestione.
- **KDE Plasma** guarda paneles, lanzadores, disposición de widgets, atajos, apariencia y ajustes de KWin. Incluye los applets instalados en tu cuenta. Para aplicar la disposición, AiO detiene y reinicia el servicio de usuario de Plasma Shell.

Las extensiones y widgets instalados para todo el sistema se recuperan instalando sus paquetes. La restauración se ejecuta con los permisos de tu cuenta, muestra las versiones y complementa los archivos y ajustes existentes. Cierra sesión y vuelve a entrar para aplicar los cambios. Los paneles y widgets pueden quedar en posiciones distintas si cambian las pantallas.

AiO guarda la configuración previa en `$XDG_STATE_HOME/aio-debian-gui/desktop-backups/` (por defecto, bajo `~/.local/state`). Para volver a esa configuración, copia el ZIP a tu carpeta de copias con el nombre `escritorio-gnome.zip` o `escritorio-plasma.zip` y usa el botón de restauración.

## Programación y permisos

El paquete Debian incluye el asistente y el programador de mantenimiento del anfitrión.

Programar, pausar o eliminar un horario requiere autorización de administrador. Los temporizadores de systemd conservan sus horarios durante las actualizaciones. Si AiO recupera un horario existente, respeta si estaba activado o pausado.

Antes de cambiar kernel, Mesa, repositorios o controladores, haz una copia de seguridad y revisa las advertencias de la tarea. La vuelta de kernel y Mesa desde Backports no cambia por sí sola el kernel de arranque; NVIDIA puede quedar bloqueado cuando la compatibilidad no se pueda verificar. La opción de Polkit sin contraseña es opcional, está desactivada inicialmente y reduce la protección de la cuenta.

## Desarrollo

Para clonar el proyecto, ejecutar las comprobaciones y consultar la estructura de paquetes:

```bash
git clone https://github.com/julioayusoalende-hue/AIO-Debian-GUI.git
cd AIO-Debian-GUI
./scripts/check.sh
```

### Versiones de prueba

Cada cambio en `testing` que supere las comprobaciones publica una preversión
en GitHub Releases, sin modificar `main` ni el repositorio APT estable. Por
ejemplo, si la última versión estable es `1.0.3`, el paquete de prueba se
numera `1.0.4~testing.N.INTENTO`. El número aumenta con cada ejecución y
Debian lo considera anterior a `1.0.4`. Si se publica otra versión estable,
las siguientes pruebas parten de la siguiente versión de esa publicación.

El número de prueba solo se aplica al paquete construido, no a los archivos
de versión del código. Al integrar los cambios en `main`, se asigna y publica
manualmente la versión estable que corresponda; no se arrastra el contador de
pruebas. Las preversiones se descargan desde Releases, no mediante APT.

El catálogo de traducciones de la interfaz está en
`package/usr/lib/aio-debian-gui/aio_core/translations.py`; la selección del
idioma sigue gestionándose en la interfaz. El seguimiento del tema GTK está en
`package/usr/lib/aio-debian-gui/aio_core/gtk_appearance.py` y el diálogo de
programación en `package/usr/lib/aio-debian-gui/aio_core/gtk_scheduler.py`.

## Licencia

GNU GPL v3 o posterior. Consulta [LICENSE](LICENSE). Sin ninguna garantía.

### Mantenimiento de Snap

Si `snapd` está instalado en el anfitrión, aparece **Actualizar y limpiar Snap**, seleccionada en el mantenimiento completo y disponible como tarea opcional del programador. Ejecuta `snap refresh` y, si termina correctamente, elimina mediante `snap remove --revision` las revisiones numéricas deshabilitadas más antiguas. Conserva la revisión activa y una revisión deshabilitada por aplicación para poder volver atrás. No borra datos, instantáneas ni archivos de la caché directamente, y no instala snapd. Si snapd se desinstala después de guardar un horario, la tarea se omite sin interrumpir las demás. Las programaciones existentes mantienen su selección de tareas.
