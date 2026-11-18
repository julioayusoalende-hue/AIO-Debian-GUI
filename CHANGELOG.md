# Cambios

## 1.0.9

- Al pulsar el número verde de versión, se abren las novedades desde el encabezado de la ventana.
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

## 1.0.4

- Añade los iconos de Kitty y Ghostty a Apps recomendadas.
- Permite restaurar el diseño anterior de Fastfetch desde Configuración y mantenimiento. Recupera la copia guardada, o vuelve al diseño predeterminado si antes no había configuración personal.

## 1.0.3

- Añade un menú de edición y atajos para copiar, pegar y seleccionar texto en la terminal integrada.
- Permite aplicar el diseño incluido de Fastfetch desde Configuración y mantenimiento. Guarda una copia de la configuración anterior del usuario cuando existe.
- Ofrece Ghostty como AppImage en Debian. El enlace de descarga prescinde de la API de GitHub.

## 1.0.2

- Muestra la versión de AiO Debian en verde y, debajo, el nombre, la versión y el logotipo del sistema operativo.
- Mueve Kitty de Herramientas auxiliares a Apps recomendadas, con instalación mediante APT.
- Añade Ghostty a Apps recomendadas. En Ubuntu 26.04 o posterior ofrece APT desde los repositorios oficiales. En Debian ofrece el comando comunitario. Ambas distribuciones pueden descargar la AppImage de Ghostty.
- Mantiene needrestart como dependencia del paquete Debian y lo retira de Herramientas auxiliares.

## 1.0.1

- Rediseña la pestaña principal con descripciones visibles de las tareas, selección resaltada y un botón de ejecución que indica cuántas tareas hay seleccionadas.
- Sitúa las actualizaciones de Flatpak y Snap en «Mantenimiento habitual». Cada tarea aparece al abrir la aplicación si su gestor está instalado.
- Amplía la consola desplegada según el tamaño de la ventana y mejora el espaciado entre líneas.

## 1.0.0

- Distribución exclusiva como paquete Debian.
- Mantiene el mantenimiento y la programación de la base 2.11.3.

## 2.11.3

- Flatpak y AppImage consultan el estado del programador sin permisos de administrador. Los cambios del horario siguen autorizándose con Polkit.

## 2.11.2

- La instalación comprueba que el programador responde como usuario antes de confirmar el éxito.
- La ventana de programación indica el motivo si faltan componentes o si el asistente devuelve un error o un protocolo incompatible.

## 2.11.1

- Abrir Flatpak o AppImage comprueba la integración y deja en cola actualizaciones firmadas sin invocar Polkit. La instalación inicial desde la app solicita autorización al confirmarla.
- La recuperación admite instancias conocidas de mantenimiento inactivas o fallidas en systemd y muestra la unidad y su estado si detecta un conflicto.

## 2.11.0

- DEB, Flatpak y AppImage comparten el asistente y el programador del anfitrión. La interfaz usa el protocolo del asistente para comprobar la compatibilidad entre versiones.
- Flatpak y AppImage preparan la integración al abrirse. La recuperación conserva los horarios, las pausas y el historial, y reconstruye temporizadores ausentes.
- APT conserva el control de los archivos del DEB. El actualizador portable verifica las firmas, evita retrocesos y puede reparar archivos ausentes de una instalación portable.

## 2.10.15

- La recuperación automática de la integración Flatpak acepta también horarios compatibles guardados desde Flatpak o AppImage. Conserva sus tareas, su estado y el historial.

## 2.10.14

- La instalación automática de la integración Flatpak puede recuperar la programación compatible de un DEB desinstalado. Conserva el historial, guarda una copia del horario anterior y adapta el lanzador a Flatpak.
- Los horarios pausados conservan su estado. Si falla la instalación o la activación del temporizador, se revierte la migración.

## 2.10.13

- Flatpak reconoce la ausencia del paquete de integración antiguo aunque el anfitrión use otro idioma.
- Cuando falta el asistente del anfitrión, la aplicación indica cómo abrir la guía de integración. Vuelve a comprobar las tareas tras una instalación correcta y registra los fallos del instalador en la consola.

## 2.10.12

- Añade Brave y Gear Lever a las aplicaciones recomendadas, con los iconos aportados por el usuario. Brave ofrece su página oficial de instalación y Flatpak; Gear Lever se instala como Flatpak.

- Detecta snapd en el anfitrión y añade actualización y limpieza Snap al mantenimiento completo y a la programación opcional. No instala snapd.
- Tras actualizar correctamente, elimina solo revisiones numéricas deshabilitadas antiguas; conserva la revisión activa, una revisión anterior por aplicación y las instantáneas de datos. Los fallos se registran y no se limpia si falla la actualización o la consulta.

## 2.10.11

- AppImage y Flatpak reutilizan el programador compatible del anfitrión y evitan el error al instalar sobre archivos del DEB.
- La compatibilidad con el programador 2.10.10 permite mantener horarios y usar la nueva interfaz sin reinstalar la integración.

## 2.10.10

- Flatpak y AppImage incluyen el programador y su contenido firmado; las instalaciones nuevas no necesitan ningún paquete DEB para programar mantenimiento.
- Al abrir una versión nueva, su programador se actualiza automáticamente en el anfitrión sin solicitar otra contraseña, conservando horarios y registros.
- Las actualizaciones verifican la firma, rechazan retrocesos y esperan a que finalicen el mantenimiento y las operaciones de dpkg.
- Las instalaciones anteriores conservan su mecanismo de actualización; no se sobrescriben archivos gestionados por dpkg.

## 2.10.9

- La terminal de Flatpak inicia Bash con terminal de control, sin los errores de control de trabajos.

## 2.10.8

- AppImage y Flatpak instalan la integración del anfitrión como el paquete `aio-debian-gui-host`, descargado de un repositorio APT firmado y aislado (`/host-repo/`), y su servicio con temporizador actualiza el programador desatendidamente a la versión que solicita la app.
- La actualización rechaza versiones anteriores, paquetes retenidos (`hold`), usa `dpkg --force-confold` y espera a que no haya mantenimiento ni otra actualización en curso (bloqueos compartidos/exclusivos).
- El paquete `aio-debian-gui-host` entra en conflicto con `aio-debian-gui`: el DEB conserva su funcionamiento y no se instala la integración portable si está presente. Los horarios no se pierden al pasar del DEB a la integración portable: se restauran los temporizadores activos.
- Si el repositorio del anfitrión no responde, se usa la integración inicial anterior.

## 2.10.7

- Las eliminaciones previstas por `autoremove` y `dist-upgrade` se muestran en la comprobación de seguridad y permiten continuar tras confirmar el aviso.

## 2.10.6

- La terminal inicia Bash sin ejecutar Fastfetch automáticamente; el botón de Fastfetch sigue disponible.

## 2.10.5

- Vuelve a activar `autoremove` por defecto, conservando `libnotify-bin` y `needrestart` en su simulación y ejecución para que la programación de AppImage y Flatpak siga funcionando.

## 2.10.4

- Conserva `libnotify-bin` y `needrestart` en la simulación y ejecución de `autoremove`; la programación en AppImage y Flatpak los necesita.
- La tarea de herramientas instala también `libnotify-bin`.
- `autoremove` queda desmarcado por defecto y el bloqueo indica qué simulación propone eliminaciones.

## 2.10.3

- Instala automáticamente la integración inicial del programador para AppImage y Flatpak con autorización de administrador.
- Rechaza sobrescribir integraciones existentes o archivos gestionados por paquetes; las actualizaciones siguen usando la guía manual.
- Verifica en una VM systemd de CI la instalación, el estado del programador y el rechazo de instalaciones duplicadas.

## 2.10.2

- Modulariza el catálogo de traducciones, el seguimiento del tema GTK y el diálogo de programación, conservando el comportamiento existente.
- Verifica la interfaz GTK, la programación y los formatos AppImage y Flatpak en Debian 13.
- Limita los permisos de escritura del workflow de publicación al job protegido que corre en `main`.

## 2.10.1

- Incluye los iconos de Timeshift y Déjà Dup aunque no estén instalados.
- Incluye los iconos facilitados para Feishin, Google Chrome, HandBrake, Plex, Switcheroo y Video Downloader.

## 2.10.0

- La salida de mantenimiento también se muestra en la terminal, accesible desde la consola integrada.
- Añade accesos en la terminal para `clear`, `fastfetch` y `nautilus admin:/`.
- Limita el atajo Enter para iniciar mantenimiento a su propia pestaña, sin interferir con las demás.

## 2.9.0

- Añade una pestaña de terminal interactiva que inicia Fastfetch cuando está disponible.

## 2.8.3

- Incluye los iconos facilitados para Celluloid, GIMP, Spotify y VLC en «Apps recomendadas».

## 2.8.2

- Corrige el identificador de Video Downloader en Flathub para permitir su instalación.
- Muestra el estado instalado por formato en las apps recomendadas y deja de abrirlas automáticamente al pulsar sus botones o completar la instalación.

## 2.8.1

- Usa iconos de categoría diferenciados en «Apps recomendadas» cuando no está disponible el icono propio de una aplicación.

## 2.8.0

- Añade «Apps recomendadas» en dos columnas, ordenadas alfabéticamente, con GIMP, VLC, Celluloid, Plex, Switcheroo, Video Downloader, HandBrake, Spotify, Feishin y Google Chrome.
- Distingue los canales DEB y Flatpak disponibles para cada aplicación. Las instalaciones APT usan lista permitida, autorización y `--no-remove`; Flatpak se instala para el usuario actual.
- Los DEB externos abren las páginas oficiales para descarga y requieren instalación manual.
- Conserva las descripciones de Timeshift y Respaldos (Déjà Dup), y elimina los iconos duplicados junto a sus botones.

## 2.7.10

- Corrige la inicialización de la interfaz Backup para conservar disponibles la consola y los controles de mantenimiento.

## 2.7.9

- Añade una pestaña «Backup» con accesos a Timeshift y Respaldos (Déjà Dup).
- Si una aplicación no está instalada, permite solicitar su instalación desde los repositorios APT tras confirmación explícita y autorización de administrador.
- Deshabilita los controles durante las operaciones y evita cerrar la ventana mientras haya una acción en curso.

## 2.7.8

- Guía en la interfaz para instalar o actualizar la integración del anfitrión en Flatpak y AppImage.
- Separa extracción y revisión de archivos de la instalación autorizada; no ejecuta comandos automáticamente y evita sobrescribir archivos gestionados por paquetes.
- Accesible desde el menú, la programación y los errores de actualización de índices del diagnóstico.

## 2.7.7

- Antes de diagnosticar, actualiza los índices APT mediante el asistente autorizado por Polkit, sin instalar ni eliminar paquetes.
- Si se cancela la autorización o falla alguna fuente, el diagnóstico indica que las actualizaciones APT no se han podido comprobar con índices actualizados.
- En Flatpak, las comprobaciones del sistema se ejecutan sin privilegios en el anfitrión; para renovar los índices se requiere el asistente actualizado.

## 2.7.6

- Diagnosticar cuenta los paquetes actualizables según los índices APT, incluidos los que una simulación de `upgrade` puede dejar pendientes.
- El diagnóstico indica cómo renovar los índices APT sin instalar paquetes cuando puedan ocultar actualizaciones del sistema o de AiO.
- README actualizado para reflejar los formatos disponibles en la release estable.

## 2.7.5

- `needrestart` se instala como dependencia del DEB; si falta o falla, la comprobación de reinicio informa del error en lugar de afirmar que no hace falta reiniciar.
- Documentada la instalación de `needrestart` en el anfitrión para AppImage y Flatpak.

## 2.7.4

- Corregido el envío de notificaciones de escritorio y el aviso de reinicio al resolver el UID del usuario al nombre que requiere `runuser`.

## 2.7.3

- Si el mantenimiento programado recomienda reiniciar, abre AiO en la sesión gráfica del usuario y muestra el aviso habitual, sin reiniciar automáticamente.
- Conserva el lanzador elegido al configurar la programación y registra el resultado en el journal si no hay sesión gráfica disponible.

## 2.7.2

- Notificación de escritorio al usuario cuando el mantenimiento programado finaliza correctamente, incluso con AiO cerrado; si no hay sesión gráfica disponible, el resultado sigue guardado y se informa en el journal.

## 2.7.1

- Programación de mantenimiento en Flatpak y AppImage sin instalar el DEB, con integración administrativa persistente en el anfitrión.
- El programador verifica que estén disponibles sus módulos y el servicio systemd; se documentan instalación, actualización y retirada de la integración.

## 2.7.0

- Nueva ventana «Programar mantenimiento» con selección de tareas, frecuencia diaria, semanal o mensual y hora local.
- Ejecución automática con la aplicación cerrada mediante temporizadores de systemd; recuperación de ejecuciones pendientes al encender el equipo.
- Permite programar actualizaciones del sistema y Flatpak, limpieza de caché y comprobación de reinicio. Las eliminaciones y cambios de kernel, controladores y repositorios siguen siendo manuales.
- Activación, pausa y eliminación con autorización de administrador; instalar o actualizar la aplicación no activa ninguna programación.
- Consulta de próxima ejecución, último resultado, tareas completadas o no ejecutadas y recomendación de reinicio, sin reinicios automáticos.
- Configuración validada y guardada por root, bloqueo compartido entre mantenimiento manual y programado y comprobaciones previas de APT.
- Traducciones y pruebas de programación e interfaz en cuatro idiomas, más prueba de integración systemd en CI con una tarea de solo comprobación.

## 2.6.0

- Cabecera compacta con distribución y versión; información técnica en una sección desplegable.
- Tareas agrupadas en mantenimiento habitual, aplicaciones y repositorios, y opciones avanzadas de kernel y controladores, plegadas inicialmente.
- Casillas para seleccionar tareas e interruptor para la preferencia permanente de autorización.
- Resumen de selección actualizado al instante, botón con el número de tareas y confirmación previa.
- Diagnóstico con estado general, incidencias concretas y recomendaciones; las comprobaciones incompletas no se presentan como sistema sano.
- Consola plegada por defecto, disponible bajo demanda y abierta automáticamente ante errores. Se conserva la ventana separada y el registro incluso en modo simple.
- Resultados individuales por tarea: pendiente, en curso, completada, error o no ejecutada.
- Dos paneles de igual ancho en escritorio; por debajo de 900 píxeles se apilan con desplazamiento independiente.
- Corregida la liberación del estado ocupado tras finalizar un proceso y cancelar una ejecución posterior.
- Traducciones y pruebas GTK en español, inglés, francés y chino, ejecutadas también en CI con pantalla virtual.

## 2.5.7

- Los dos paneles principales ocupan partes iguales de la ventana.
- El separador vertical coincide con el centro y permanece centrado al redimensionar o maximizar la aplicación.
- Se conserva el desplazamiento independiente de cada panel.

## 2.5.6

- Corregida la detección de eliminaciones en simulaciones APT mediante los marcadores reales `Remv` y `Purg`.
- El asistente vuelve a simular la actualización tras refrescar los índices y cancela si el plan difiere del aprobado en la interfaz.
- Las actualizaciones se ejecutan con `--no-remove` para impedir eliminaciones durante la operación.
- Flatpak realiza las comprobaciones previas sin privilegios en el anfitrión y bloquea el mantenimiento si no puede verificarlas.
- Sincronizadas las versiones de los formatos de distribución con el asistente e incorporada una comprobación automática para Flatpak.
- Añadidas pruebas de regresión para eliminaciones, cambios de plan y errores de comunicación con el anfitrión.

## 2.5.5

- Corregido el fallo de arranque por cargar GDK 4 junto a GTK 3 en Debian 13.
- Añadida comprobación automática de versiones de introspección GDK/GTK antes de publicar.

## 2.5.4

- Enter inicia las tareas seleccionadas cuando la ventana principal está activa, sin interferir con botones, campos editables ni diálogos.
- Eliminado el botón redundante «Estado de mantenimiento»; «Diagnosticar» sigue disponible.

## 2.5.3

- Eliminada la integración de Timeshift y Snapper de la interfaz y del asistente privilegiado.
- Mantenimiento sin diálogos de instantáneas; se mantienen las comprobaciones previas de seguridad.
- Corregidos saltos de línea literales en los mensajes de autorización de la consola.

## 2.5.2

- Detección de Timeshift y Snapper instalados y configurados.
- No se ofrece crear instantáneas si no hay proveedores disponibles.
- Selección explícita de proveedor cuando ambos están disponibles.
- Cancelación del mantenimiento si falla la instantánea solicitada.
- Correcciones de GTK, preflight y comprobaciones Btrfs.

## 2.5.1

- Vista previa de paquetes APT con versiones.
- Panel de salud asíncrono y accesibilidad mejorada.
- Traducciones y pruebas de regresión.

## 2.5.0

- Panel de salud con espacio libre y reinicio solicitado.
- Instantáneas opcionales Snapper en Btrfs antes del mantenimiento.
- Traducciones nuevas en inglés, francés y chino.
- Protección de fallo seguro de instantáneas.

## 2.4.0

- Prevención de ejecuciones simultáneas desde la interfaz.
- Bloqueo conservador si no se puede verificar el estado de los locks APT/dpkg.
- Bloqueo si falta dpkg o la comprobación APT falla; se evitan simulaciones innecesarias.
- Pruebas de regresión para fallos de detección y dependencias ausentes.

## 2.3.0

- Comprobaciones de seguridad asíncronas sin bloquear GTK.
- Detección de bloqueos activos de APT/dpkg.
- Vista previa de paquetes que se instalarán o actualizarán.
- Traducciones y pruebas adicionales del modo seguro.

## 2.2.0

- Nuevo modo de mantenimiento seguro: comprobaciones previas de espacio libre, dpkg, dependencias APT y DKMS.
- Simulaciones de actualización y limpieza de dependencias; bloqueo preventivo ante propuestas de eliminación de paquetes.
- Confirmación adicional para avisos y bloqueo de operaciones con incidencias críticas.
- Pruebas automatizadas de las condiciones de bloqueo y continuidad.
- Las simulaciones son orientativas y no garantizan el resultado de la ejecución real.


## 2.1.0

- Nueva tarea **Volver a kernel y Mesa Stable** para Debian: prepara el retorno desde Backports a las versiones de la rama Stable.
- Selección explícita de versiones de Stable, Stable Security y Stable Updates para metapaquetes de kernel y cabeceras y controladores Mesa instalados.
- Vista previa con versiones concretas de paquetes y confirmación independiente. La reversión debe ejecutarse sola, sin mezclar operaciones de mantenimiento.
- Simulación APT obligatoria y bloqueo si hay eliminaciones de paquetes, incompatibilidades, módulos DKMS externos o controlador NVIDIA propietario.
- No elimina los kernels antiguos, no modifica GRUB ni desactiva repositorios. Tras instalar, es necesario reiniciar seleccionando y comprobando el kernel Stable desde GRUB.
- Pruebas de selección de origen Stable, simulación y bloqueos de seguridad.


## 2.0.9

- Traducciones revisadas para inglés, francés y chino: novedades de la versión, mensajes de NVIDIA, aviso de Polkit y encabezado de la consola.
- Traducción de resultados y recomendaciones del diagnóstico preventivo, incluyendo medidas y contadores variables de espacio, actualizaciones e índices APT.
- Las cadenas técnicas desconocidas se conservan, sin traducir arbitrariamente la salida de comandos del sistema.
- Prueba automatizada que exige las traducciones críticas y verifica los textos dinámicos en los tres idiomas.


## 2.0.8

- Corregida la comprobación de la versión de AiO desde «Diagnosticar» en Debian con idioma español u otros idiomas distintos del inglés.
- Las consultas internas de APT fuerzan LC_ALL=C para interpretar correctamente el campo Candidate sin modificar el idioma de la interfaz.
- Corregido el mismo problema en el asistente privilegiado usado para buscar actualizaciones de la edición DEB.
- Prueba de regresión con entorno de idioma español.


## 2.0.7

- El diagnóstico preventivo consulta si AiO Debian GUI está actualizado según APT, el repositorio Flatpak o GitHub Releases para AppImage.
- Cuando existe una versión nueva, el informe incluye «Actualizar AiO», que utiliza el mecanismo de actualización existente y su confirmación habitual.
- Las consultas no instalan paquetes y las fuentes inaccesibles se marcan como no comprobadas.
- Nueva casilla voluntaria «Reiniciar AiO automáticamente tras actualizar»; también se ofrece reiniciar al terminar si no se eligió la casilla.
- Tras actualizar DEB se relanza el ejecutable del paquete; Flatpak vuelve a lanzar la aplicación en el host; AppImage ejecuta el nuevo archivo con SHA-256 verificado, conservando el anterior.
- Pruebas automáticas de los estados de actualización en DEB, Flatpak y AppImage.


## 2.0.6

- El diagnóstico comprueba dependencias con `apt-get -o Debug::NoLocking=1 check`, evitando el bloqueo de dpkg reservado a root.
- Un error de acceso o permisos pasa a «No comprobado», no a «Crítico».
- Nuevas pruebas para impedir que un fallo de permisos se confunda con dependencias rotas.


## 2.0.5

- Nuevo diagnóstico preventivo de solo lectura desde «Información del sistema», con ventana independiente y resultados diferenciados.
- Comprueba espacio libre, paquetes dpkg incompletos, dependencias APT, actualizaciones simuladas, antigüedad de índices, DKMS, reinicio pendiente y servicios systemd.
- Muestra recomendaciones cuando hay incidencias. La falta de información se distingue de un resultado correcto.
- Ejecuta las comprobaciones en segundo plano sin congelar GTK y sin usar permisos de administrador.
- Pruebas de detección de anomalías y fallos de comprobación.


## 2.0.4

- Nueva opción «Abrir en otra ventana» en la cabecera de la consola.
- Ventana de salida independiente y redimensionable que comparte el mismo Gtk.TextBuffer y refleja nuevos mensajes en tiempo real.
- «Volver a integrar» o cerrar la ventana independiente restaura la consola integrada sin perder contenido.
- Cierre de la ventana de salida junto a la aplicación y compatibilidad con el modo simple.
- Pruebas automáticas de la separación y reintegración de la consola.


## 2.0.3

- Menú unificado en este orden: Preferencias, Historial de mantenimiento, Buscar actualizaciones y Acerca de.
- Eliminados los accesos independientes de cabecera para evitar duplicaciones, preservando la operativa de las cuatro opciones.
- Buscar actualizaciones permanece visible pero inactivo en ediciones sin mecanismo de actualización integrado.
- Pruebas del orden y presencia de opciones en GTK.


## 2.0.2

- Dos paneles GTK lado a lado con separador horizontal ajustable: sistema y novedades a la izquierda y tareas a la derecha.
- Desplazamiento vertical independiente en cada panel para aprovechar toda la altura de la ventana.
- Eliminada la entrada duplicada de Preferencias del menú; se conserva el botón directo y el acceso a Historial.
- Ventana inicial más ancha y pruebas de orientación del panel y del menú.


## 2.0.1

- Rediseño de la interfaz GTK en secciones apiladas horizontalmente: información del sistema, tareas de mantenimiento, progreso y consola.
- Información del sistema y novedades organizadas en la parte superior, con logotipo de la distribución.
- Botón principal «Iniciar tareas» junto a los indicadores de progreso y estado.
- Acceso directo a Preferencias en la barra de título, manteniendo el menú e historial existentes.
- Cabecera de consola con botón «Borrar», deshabilitado durante la ejecución de tareas.
- Diseño adaptable a ventanas pequeñas mediante desplazamiento de la zona superior; se preserva el modo simple.


## 2.0.0

- Nueva opción NVIDIA exclusiva de Debian, visible tras detectar una GPU NVIDIA PCI.
- Detección de equipos híbridos Intel/AMD + NVIDIA, manteniendo la integrada y utilizando PRIME Render Offload bajo demanda.
- Diagnóstico de driver instalado, versión candidata APT, kernel y Secure Boot.
- Instalación opcional y explícita desde repositorios Debian con comprobaciones de nvidia-detect, cabeceras DKMS y simulación APT.
- Se rechazan configuraciones no verificadas: Secure Boot sin firma DKMS/MOK, kernels de Backports incompatibles, conflictos Bumblebee/Primus y eliminaciones propuestas por APT.
- No se ejecuta instalador NVIDIA .run, no se modifica Xorg ni se fuerza NVIDIA como GPU principal.
- Pruebas de detección PCI/híbrida y bloqueo sin NVIDIA.


## 1.2.4

- Se conserva el icono original de AiO Debian GUI y se recolorea en tonos rojos Debian.
- «Acerca de» muestra el PNG incluido en DEB, AppImage, Flatpak y Snap, sin depender del tema de iconos del sistema.
- La edición Flatpak utiliza su identificador de icono correcto en el lanzador.


## 1.2.3

- Cuando la única tarea seleccionada es actualizar Flatpak, se usa `flatpak --user` sin `pkexec`, también desde la interfaz Flatpak, sin depender del asistente privilegiado del anfitrión.
- Restaurada la casilla opcional «No solicitar contraseña de administrador en AiO». Requiere una autorización inicial, configura una excepción de Polkit para la acción de AiO y el usuario local activo, y puede desactivarse desde la misma casilla.
- Aviso explícito: otros procesos que actúen bajo esa cuenta podrían invocar el asistente privilegiado de AiO sin contraseña; no equivale a desactivar Polkit globalmente.
- Las tareas APT, el kernel, los repositorios, instalaciones Flatpak del sistema y ejecuciones mixtas siguen siendo administrativas salvo que el usuario habilite la excepción.

## 1.2.2

- Nueva opción de apariencia «Seguir el sistema», predeterminada para nuevas instalaciones.
- Cambio automático en vivo del tema claro/oscuro usando el portal freedesktop, GSettings GNOME y respaldo GTK.
- Se conservan las preferencias manuales «Claro» y «Oscuro» de las instalaciones existentes.
- Disponible en los formatos DEB, Flatpak, AppImage y el prototipo Snap.

## 1.2.1

- La tarjeta Información del sistema muestra el logotipo Debian o Ubuntu según `/etc/os-release` del anfitrión.
- Logotipo Ubuntu escalado de forma proporcional y con texto accesible, integrado en los paquetes DEB, AppImage y Flatpak.
- La falta de cargador de imágenes no impide abrir la aplicación.

## 1.2.0

- Detecta Debian y Ubuntu 24.04/26.04 LTS en el anfitrión y bloquea el mantenimiento administrativo en sistemas no compatibles.
- Opciones específicas por distribución: contrib/non-free y Backports solo en Debian; universe/restricted/multiverse y HWE oficial opcional en Ubuntu LTS.
- El asistente privilegiado valida la distribución y rechaza tareas cruzadas aunque se le llame sin interfaz gráfica.
- Pruebas con perfiles Debian y Ubuntu simulados, sin modificar repositorios del equipo de pruebas.

## 1.1.0

- Extrae la lógica de versiones/AppImage, historial y preferencias a `aio_core`, sin dependencias GTK.
- Mantiene una capa de compatibilidad para la interfaz y el asistente Polkit.
- Incluye módulos en los paquetes DEB, AppImage y Flatpak y los prueba directamente en CI.
- Conserva los mecanismos de firma GPG y las actualizaciones de los tres formatos.

## 1.0.20

- Vista previa y confirmación de tareas seleccionadas antes de ejecutar el mantenimiento.
- Historial local de hasta 100 ejecuciones, con fecha, resultado, versión y tareas, sin almacenar el registro completo de comandos.
- Consulta y exportación JSON del historial desde el menú de preferencias.
- Mantiene las protecciones Polkit de la versión 1.0.19.

## 1.0.19

- Endurece Polkit: únicamente sesiones activas y autorización de administrador sin caché persistente.
- Se retira la posibilidad de activar acceso sin contraseña; el paquete DEB revoca reglas antiguas creadas por AiO en el proceso de actualización.
- Los botones DEB, Flatpak y AppImage comprueban si existe una versión nueva y piden confirmación antes de instalar o descargar.
- Comprueba que el asistente privilegiado del anfitrión coincide con la versión Flatpak antes de ejecutar mantenimiento.

## 1.0.18

- La cabecera identifica el formato activo: DEB, AppImage o Flatpak.
- Nuevo botón «Buscar actualizaciones» en DEB, que usa APT a través del asistente Polkit.
- Solo se actualiza el paquete aio-debian-gui; no se actualiza el resto del sistema.
- Las versiones AppImage y Flatpak mantienen su actualizador.

## 1.0.17

- Nuevo botón «Buscar actualizaciones» visible para AppImage y Flatpak.
- Flatpak actualiza desde el repositorio firmado del usuario y aplica cambios al reiniciar la aplicación.
- AppImage consulta la última Release, verifica el archivo con SHA-256 y lo descarga sin sustituir el ejecutable en uso.


## 1.0.16
Comprueba correctamente los errores de `autoremove` y `autoclean`; modifica únicamente
stanzas Deb822 de repositorios oficiales de Debian; actualiza y limpia Flatpak por separado
para instalaciones de sistema y del usuario de la sesión iniciadora. Añade distribución
Flatpak con sandbox reducido y delegación explícita de las tareas administrativas al
asistente instalado en el Debian anfitrión.


Al publicar una versión nueva: sube `Version` en `package/DEBIAN/control` y añade
una sección única `## X.Y.Z` aquí para las novedades incluidas en el paquete.
`scripts/check.sh` lo verifica.

## 1.0.15
Corrige la autorización desde el AppImage en montajes FUSE: prepara una copia temporal del
asistente y la ejecuta mediante Bash del sistema para que Polkit no tenga que abrir el montaje.

## 1.0.14
Mantiene operables las opciones durante la comprobación inicial de tareas y cancela la
comprobación si tarda más de 30 segundos.

## 1.0.13
Amplía el crédito del autor y añade un enlace a una ventana con una foto y una dedicatoria
personal.

## 1.0.12
Corrige la visualización de la consola en modo completo y al desactivar el modo simple.

## 1.0.11
Corrige la visualización del menú de preferencias.

## 1.0.10
Añade preferencias de idioma (español, inglés, francés y chino), tema claro u oscuro e
interfaz simple sin salida detallada de consola.

## 1.0.8 (serie anterior)
Detecta si contrib/non-free, las herramientas auxiliares, GNOME Software Plugin Flatpak,
Extension Manager y el kernel/Mesa de Backports ya están configurados o instalados; muestra
el estado y desactiva las tareas completadas.
Añade un botón para cancelar la espera de Polkit y un límite para evitar que la interfaz
quede indefinidamente esperando una autorización que no llega.

## 1.0.9 (serie anterior)
Los botones «Completo» y «Solo Flatpak» resaltan el preset seleccionado. El resaltado se
quita si se modifica una tarea individualmente.

## 1.0.7 (serie anterior)
Añade una opción para instalar el kernel de la arquitectura y los controladores Mesa
disponibles desde Debian Backports. La opción está desactivada por defecto y avisa
que puede requerir reiniciar.

## 1.0.6 (serie anterior)
Añade una opción para permitir, tras una autorización inicial, tareas sin contraseña
para el usuario actual y solo en la sesión local activa. El AppImage reutiliza el
asistente del sistema aunque sea de otra versión; la opción nueva verifica que el
asistente tenga esa capacidad.

## 1.0.5 (serie anterior)
Se corrige la autenticación al ejecutar el AppImage cuando está instalado el paquete Debian.

## 1.0.4 (serie anterior)
La aplicación también se distribuye como AppImage.

## 1.0.3 (serie anterior)
Las herramientas auxiliares instalan el soporte FUSE necesario para ejecutar AppImage.

## 1.0.2 (serie anterior)
El logotipo de Debian aparece junto a la información del sistema.

## 1.0.1 (serie anterior)
El botón principal ahora se llama «Iniciar tareas».

## 1.0.0 (serie anterior)
Primera versión independiente de la interfaz gráfica de AiO Debian: actualización con
apt, `contrib`/`non-free`, reloj, Flatpak + Flathub, complementos de GNOME y
comprobación de reinicio, todo desde una ventana.
