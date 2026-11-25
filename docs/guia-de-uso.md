# Guía de uso de AiO Debian GUI

[← Volver a la página principal](../README.md)

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


## Mantenimiento de Snap

Si `snapd` está instalado en el anfitrión, aparece **Actualizar aplicaciones Snap**, seleccionada en el mantenimiento estándar y disponible como tarea opcional del programador. Ejecuta `snap refresh` y no elimina revisiones antiguas. La limpieza de revisiones se hace por separado con **Eliminar revisiones antiguas de Snap**, en el apartado **Limpieza del sistema**: usa `snap remove --revision` y conserva la revisión activa y una revisión deshabilitada por aplicación para poder volver atrás. No borra datos, instantáneas ni archivos de la caché directamente, y no instala snapd. Si snapd se desinstala después de guardar un horario, la tarea se omite sin interrumpir las demás. Las programaciones existentes mantienen su selección de tareas.

## Actualizar AiO desde Salud del sistema

Abre **Salud del sistema** desde la tarjeta **Información del sistema**. El botón **Actualizar AiO** de la cabecera busca e instala únicamente la actualización de la aplicación; no ejecuta el mantenimiento completo ni actualiza el resto de paquetes. La tarjeta **Versión de AiO Debian GUI** también ofrece el mismo acceso cuando detecta una versión nueva.

La actualización usa el canal configurado en **Preferencias** (Estable o Testing) y el formato instalado (DEB, Flatpak o AppImage). En DEB se realiza mediante APT y el repositorio firmado del proyecto.

## Limpieza del sistema

En **Configuración y mantenimiento → Tareas**, el apartado **Limpieza del sistema** ofrece opciones independientes, todas desactivadas por defecto. Selecciona solo las que quieras ejecutar y pulsa **Ejecutar**; no es necesario activar el mantenimiento completo. El preset **Limpieza**, junto a Estándar, Completo y Solo Flatpak, selecciona todas las limpiezas disponibles sin actualizar paquetes ni comprobar reinicios.

- **Limpiar caché de APT**: elimina los `.deb` descargados en `/var/cache/apt/archives`. No desinstala paquetes y los archivos pueden volver a descargarse.
- **Vaciar papelera del usuario**: borra el contenido de `~/.local/share/Trash`. No toca archivos fuera de la papelera.
- **Eliminar miniaturas antiguas**: borra miniaturas de más de 7 días en `~/.cache/thumbnails`. Se regeneran al abrir los archivos.
- **Limpiar registros del sistema**: conserva los últimos 30 días del diario de systemd y elimina registros rotados más antiguos.
- **Eliminar Flatpak sin uso**: ejecuta `flatpak uninstall --unused` para el sistema y el usuario. No elimina aplicaciones instaladas.
- **Eliminar revisiones antiguas de Snap**: conserva la revisión activa y la última revisión deshabilitada de cada snap para permitir volver atrás.

Las tareas de papelera y miniaturas se ejecutan con los permisos de tu cuenta. AiO comprueba que las rutas resueltas permanecen dentro de tu directorio personal y no sigue enlaces que apunten fuera de él. Las tareas de limpieza no se incluyen en la programación automática.


## Extensiones recomendadas de GNOME

Cuando AiO detecta el paquete `gnome-shell`, el grupo **Aplicaciones y repositorios** muestra tareas individuales para instalar:

- AppIndicator y KStatusNotifierItem Support.
- Blur my Shell.
- Caffeine.
- Clipboard Indicator.
- Dash to Dock.
- Places Status Indicator.
- Tiling Shell.

AiO consulta `extensions.gnome.org` para elegir una versión compatible con el GNOME Shell instalado, descarga el ZIP por HTTPS y comprueba su integridad, `metadata.json` y UUID antes de instalarlo con los permisos de tu usuario. La extensión se instala pero no se activa automáticamente; puedes activarla desde **Extension Manager** o **Extensiones**. En escritorios distintos de GNOME estas tareas no se muestran.
