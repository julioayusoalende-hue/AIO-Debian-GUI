# Cambios

## 1.1.2

- Abre btop en la propia consola y recupera la sesión de Bash al salir.
- Conserva los colores de Fastfetch al ejecutarlo desde el menú Comandos de la terminal.
- Permite arrastrar el separador de la pestaña principal y conserva el reparto de ancho al redimensionar la ventana.
- Explica cuándo volver a iniciar sesión tras restaurar GNOME y ofrece el botón «Cerrar sesión…» en el aviso final.

## 1.1.1

- Ajusta la cabecera para mantener el nombre y el icono del sistema dentro de la barra de título.
- Permite elegir entre Estable y Testing para actualizar AiO desde repositorios APT firmados.
- Añade Steam y RetroArch a Apps recomendadas con sus iconos.
- Añade Audacity, Kdenlive y Heroic Games Launcher a Apps recomendadas con sus iconos oficiales.
- Añade metadatos AppStream, capturas, licencia y novedades para GNOME Software, y declara el tamaño instalado del paquete DEB.
- El mantenimiento programado notifica las tareas pendientes o con error y ofrece abrir AiO para revisarlas y ejecutarlas manualmente.
- Añade la purga opcional de dependencias huérfanas, con vista previa y revisión del plan dentro del mismo mantenimiento si cambia.
- Actualiza los paquetes con APT sin eliminarlos y detiene la operación si no se pueden actualizar todos los índices.
- Deja la limpieza de dependencias desmarcada por defecto y comprueba que el plan sigue siendo el aprobado antes de aplicarlo.

## 1.1.0

- Agrupa los accesos de la terminal en un único menú Comandos para dejar más espacio a la consola.
- Añade un botón para abrir btop desde la terminal e instalarlo por APT si falta.
- Añade la pestaña Inicio para elegir la entrada predeterminada de GRUB, el tiempo de espera y la visibilidad del menú, con restauración de los ajustes del sistema.
- Permite separar la terminal en una ventana redimensionable y volver a acoplarla conservando la sesión, los comandos en curso y la salida.
- Permite seleccionar varias aplicaciones, elegir DEB (APT) o Flatpak por aplicación e iniciar todas las instalaciones con un solo botón.
- Añade instalación por Flatpak desde Flathub para Deluge, Google Chrome y qBittorrent.
- Añade Deluge, qBittorrent, btop, htop y GParted a Apps recomendadas con instalación vía APT.

## 1.0.9

- Muestra la tarea de instalación del controlador cuando se detecta una GPU NVIDIA en Debian.
- Al pulsar el número verde de versión, las novedades se abren en una ventana amplia y redimensionable con desplazamiento. Las notas se consultan desde el encabezado.
- La interfaz simple oculta la columna de información del sistema para dar más espacio a las tareas.

## 1.0.8

- Rediseña Backup con una carpeta de copia compartida y tarjetas para repositorios APT, ajustes del escritorio y aplicaciones de respaldo.
- Rediseña Apps recomendadas con tarjetas de una o dos columnas según el ancho de la ventana, acciones por formato y un indicador de instalación más legible.

## 1.0.7

- Ajusta el tamaño inicial de «Comprobaciones de seguridad» a 680 × 526 píxeles y lo adapta al área disponible en pantallas pequeñas.
- Verifica las GPU NVIDIA contra la lista del paquete candidato, selecciona la variante DKMS según soporte y rama, comprueba el módulo del kernel activo y prohíbe eliminaciones en la instalación. Detiene los casos sin compatibilidad verificable.

- Añade copia y restauración de ajustes, extensiones y widgets del usuario en GNOME y KDE Plasma, con una copia previa antes de restaurar.
- Añade botones en Backup para copiar y restaurar los repositorios APT desde una misma carpeta.

## 1.0.6

- El aviso Comprobaciones de seguridad muestra la simulación APT completa en un panel desplazable, con Cancelar y Continuar siempre visibles.

## 1.0.5

- La interfaz simple deja visible solo Configuración y mantenimiento y oculta la salida de la consola, incluso cuando una tarea falla.
- La aplicación muestra las novedades de su propio paquete a partir del historial de cambios.

## 1.0.1

- Rediseña la pestaña principal con descripciones visibles de las tareas, selección resaltada y un botón de ejecución que indica cuántas tareas hay seleccionadas.
- Sitúa las actualizaciones de Flatpak y Snap en «Mantenimiento habitual». Cada tarea aparece al abrir la aplicación si su gestor está instalado.
- Amplía la consola desplegada según el tamaño de la ventana y mejora el espaciado entre líneas.

## 1.0.0

- Distribución exclusiva como paquete Debian.
- Mantiene el mantenimiento y la programación de la serie anterior.
