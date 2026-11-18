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

Si `snapd` está instalado en el anfitrión, aparece **Actualizar y limpiar Snap**, seleccionada en el mantenimiento completo y disponible como tarea opcional del programador. Ejecuta `snap refresh` y, si termina correctamente, elimina mediante `snap remove --revision` las revisiones numéricas deshabilitadas más antiguas. Conserva la revisión activa y una revisión deshabilitada por aplicación para poder volver atrás. No borra datos, instantáneas ni archivos de la caché directamente, y no instala snapd. Si snapd se desinstala después de guardar un horario, la tarea se omite sin interrumpir las demás. Las programaciones existentes mantienen su selección de tareas.
