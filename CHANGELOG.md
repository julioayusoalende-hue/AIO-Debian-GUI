# Cambios

## 1.4.4

- Se corrige el error D-Bus `NoReply: Message recipient disconnected from message bus without replying` al instalar extensiones de GNOME: la llamada ahora se dirige directamente a `org.gnome.Shell` (`/org/gnome/Shell`), que mantiene viva la conexión mientras el usuario confirma el diálogo, evitando que el servicio intermedio `org.gnome.Shell.Extensions` (que se apaga a los 2 s de inactividad) corte la respuesta.

## 1.4.3

- La confirmación de instalación de extensiones de GNOME ya no provoca un falso fallo por timeout: la llamada D-Bus espera hasta 10 minutos.
- Si la respuesta D-Bus expira o llega tarde, AiO comprueba el estado real de la extensión antes de marcar la tarea como fallida.

## 1.4.2

- Las extensiones de GNOME se instalan ahora con la API oficial `org.gnome.Shell.Extensions.InstallRemoteExtension`, la misma que usan Extension Manager y la integración web. GNOME Shell muestra la confirmación, descarga la versión compatible, la instala, la carga y la activa sin reiniciar sesión.
- Corregido el fallo de Blur my Shell y de cualquier extensión que no podía cargarse tras una instalación local desde ZIP.

## 1.4.1

- Las extensiones de GNOME se instalan, se activan automáticamente y se intenta recargarlas en caliente con `org.gnome.Shell.Extensions.ReloadExtension`.
- Si GNOME Shell no permite recargarlas sin reiniciar sesión, AiO muestra un aviso explícito en lugar de dejar la extensión inactiva sin explicación.

## 1.4.0

- En **Aplicaciones y repositorios**, solo cuando se detecta GNOME Shell, se ofrecen tareas individuales para instalar AppIndicator y KStatusNotifierItem Support, Blur my Shell, Caffeine, Clipboard Indicator, Dash to Dock, Places Status Indicator y Tiling Shell.
- Las extensiones se descargan desde `extensions.gnome.org` usando una lista blanca de UUID y una versión compatible con el GNOME Shell instalado. El ZIP se valida (integridad, `metadata.json` y UUID) y se instala con los permisos del usuario.
- Las tareas de extensión muestran el estado «Ya instalada» y no aparecen en escritorios que no sean GNOME.

## 1.3.1

- Corregida la limpieza de papelera y miniaturas cuando `pkexec` deja el directorio de trabajo en `/root`: el asistente entra al HOME del usuario antes de ejecutar `runuser`.
- Añadida una prueba de regresión que comprueba el directorio de trabajo de los comandos ejecutados como el usuario solicitante.
- Nuevo preset **Limpieza**, junto a Estándar, Completo y Solo Flatpak. Selecciona las limpiezas disponibles sin actualizar paquetes ni comprobar reinicios.
- Separadas actualización y limpieza de Flatpak y Snap: las tareas de actualización ya no eliminan runtimes o revisiones antiguas; esas acciones quedan en el apartado de limpieza.

## 1.3.0

- Salud del sistema incorpora un botón propio **Actualizar AiO** en la cabecera. Busca e instala solo la actualización de la aplicación, sin iniciar el mantenimiento completo ni actualizar el resto del sistema.
- Nuevo apartado **Limpieza del sistema** en Tareas, con opciones independientes y desactivadas por defecto: caché APT, papelera, miniaturas antiguas, registros de systemd, Flatpak sin uso y revisiones antiguas de Snap.
- La limpieza personal valida que las rutas resueltas permanecen dentro del directorio del usuario y no sigue enlaces que apunten fuera. Las tareas de limpieza no se añaden a la programación automática.

## 1.2.5

- La autorización opcional sin contraseña permanece activada tras reiniciar o volver a iniciar sesión. AiO conserva un marcador de estado legible por el usuario porque Debian restaura `/etc/polkit-1/rules.d` a `0750 root:polkitd` en cada arranque.
- Al actualizar, las reglas de Polkit existentes se migran automáticamente al nuevo marcador. Al desinstalar, se eliminan tanto las reglas como el estado asociado.

## 1.2.4

- Gestor de software: instala aplicaciones desde archivos .flatpakref. Se pueden abrir con doble clic, desde el botón de la pestaña Flatpak o arrastrándolos a la ventana. La instalación es para el usuario o para todo el sistema, según el ámbito elegido.
- Arrastrar un .deb o un .flatpakref a cualquier parte de la ventana lo abre en el gestor de software.
- El archivo .flatpakref se valida antes de instalar: debe ser una aplicación, con identificador válido y direcciones HTTPS.
- Inicio: nuevo interruptor para activar o desactivar os-prober (detección de otros sistemas operativos). Al cambiarlo se regenera GRUB, como con update-grub, para que el cambio surta efecto.

## 1.2.3

- NVIDIA: si el equipo arranca en EFI y falta mokutil, la app lo instala antes de instalar el controlador. Sin él no se puede comprobar Secure Boot y la instalación se rechazaba.
- NVIDIA: la comprobación del módulo DKMS acepta el estado installed aunque dkms añada una nota detrás. Si la comprobación falla, el registro muestra el kernel, la versión del módulo y la línea de dkms status para saber qué pasa.
- NVIDIA: corregido el falso error «no se verificó el módulo DKMS». Debian instala el módulo con el nombre nvidia-current y la app solo buscaba nvidia, así que no lo encontraba aunque estuviera compilado.
- NVIDIA: la instalación sigue los pasos de la wiki de Debian para Trixie. Activa nvidia-drm modeset=1 y fbdev=1. En equipos con una sola gráfica activa además PreserveVideoMemoryAllocations y NVreg_TemporaryFilePath=/var/tmp, necesarios para la suspensión y para que GDM use Wayland. En portátiles con gráfica Intel y NVIDIA no se activan, como indica la wiki.
- NVIDIA: si faltan el servidor gráfico X11 (xserver-xorg) o las sesiones X11 de GNOME (gnome-session-xsession), se instalan. GDM pasa a X11 cuando no puede usar Wayland con NVIDIA y, sin ellos, abortaba con «no session desktop files installed» y la pantalla se quedaba en negro. AyusOS no los trae y Debian sí.
- NVIDIA: se instala el panel de control de NVIDIA (nvidia-settings). nvidia-driver solo lo recomienda y podía quedar fuera.
- NVIDIA: se instala el metapaquete de cabeceras del kernel (por ejemplo linux-headers-amd64) para que el módulo se compile también con los kernels futuros. Con dracut, el initramfs incluye la configuración de NVIDIA.
- NVIDIA: si el controlador ya estaba instalado sin esta configuración, la tarea vuelve a aparecer para completarla.

## 1.2.2

- Inicio: los ajustes de GRUB que guardas (tiempo de espera, visibilidad del menú, entrada predeterminada) ahora se leen los últimos, así que ya no los pisa otro archivo del sistema como el de AyusOS. Al aplicar, los ajustes guardados con la versión anterior se migran solos.
- Inicio: si otro archivo sigue cambiando un valor guardado, la pestaña lo avisa y muestra el que se usa al arrancar.

## 1.2.1

- Autorización de administrador: el interruptor «No solicitar contraseña» ya no aparece apagado cuando la regla está activa pero el sistema no deja leerla a tu usuario; permanece activado hasta que lo desactives tú.
- Apps recomendadas: vuelven a marcarse con «✓ Instalado» las aplicaciones que ya están en el sistema (DEB o Flatpak). El indicador existía, pero dejó de actualizarse al abrir la pestaña.

## 1.2.0

Un antes y un después en AiO Debian GUI: esta versión cambia por completo la forma de usar la app desde su creación. El estado del sistema deja de ser algo que se consulta a mano y pasa a revisarse solo, con el problema y su solución a la vista.
- Salud del sistema, en ventana propia: se abre con el botón «Salud del sistema» de la tarjeta «Información del sistema» y analiza el equipo automáticamente al abrirse, sin botón de diagnóstico ni diálogos aparte.
- Diagnóstico integrado: barra de progreso abajo y, en cada apartado, su resultado (Correcto, Revisar o No superado) con un punto verde, naranja o rojo.
- Índices actualizados antes de analizar: el diagnóstico refresca los índices APT con el asistente autorizado, de modo que no arranca bloqueado con resultados «Sin comprobar».
- Solución automática: si algo bloquea o falla (por ejemplo, actualizaciones sin aplicar) se abre sola una ventana que ofrece la solución, como ejecutar el mantenimiento estándar.
- Soluciones a un clic: cada apartado que falla tiene su botón (completar paquetes, reparar dependencias, actualizar índices, reiniciar, abrir mantenimiento…) sin salir de la ventana, y el análisis se repite al terminar.
- Tamaño cómodo: la ventana se abre con el tamaño de la app, como máximo 1160×780, para ver las nueve tarjetas sin desplazarse; la barra de desplazamiento solo aparece si no caben.
- Terminal: el botón «Comandos» de la pestaña Terminal tiene un icono de lista propio, distinto del botón de terminal del encabezado.
- Pruebas: nuevas comprobaciones de la ventana, de los estados y de los botones de solución.

## 1.1.10

- **Programación**: el aviso de reinicio abre AiO como mucho una vez por arranque, aunque el mantenimiento acabe con errores o se repita mientras el equipo sigue pendiente de reiniciar.
- **Backup**: la copia de repositorios APT usa un único tope de tamaño de 32 MiB al leer y al escribir; antes se cortaba a 16 MiB al leer y rechazaba copias que cabían en el tope anunciado.
- **Pruebas**: las comprobaciones GTK ya no fallan al lanzar `check.sh` desde un AppImage, Flatpak o Snap, y la prueba de preferencias admite la entrada de menú de la guía de integración.

## 1.1.10 (testing)

### Refactor de arquitectura modular
- **UI completamente modularizada**: 15 archivos en `ui/` (main_window, 6 páginas, 4 diálogos, 4 widgets reutilizables)
- **Constantes centralizadas** en `aio_core/constants.py` + re-exports en `aio_core/__init__.py`
- **Entry point limpio** en `main.py` (~30 líneas)

### GTK4 + libadwaita (prototipo)
- Prototipo funcional en `gtk4_prototype/main.py` usando `Adw.NavigationView`, `Adw.PreferencesGroup/Section/ActionRow`
- Temas automáticos (claro/oscuro/sistema), diálogos nativos, switches integrados

### Software Manager mejorado
- **Caché inteligente** (`CatalogueManager`): TTL 5 min, carga async con callbacks, invalidación selectiva
- **Drag & Drop para .deb**: `analyze_deb_file()` → `DebFileInfo` + diálogo confirmación con plan de instalación
- **Búsqueda instantánea** (`SearchIndex`): índice invertido por nombre, descripción, sección (30+ secciones DEB)
- **Filtros avanzados**: por estado (Instalado/Disponible/Actualizable) + por sección DEB

### Tests y CI/CD
- **39 tests unitarios**: `test_backend.py` (12), `test_admin.py` (18), `test_gui.py` (9)
- **CI/CD completo** (`.github/workflows/ci.yml`): lint (ruff+mypy) → unit-tests → gui-tests (xvfb) → build-deb → integration-test (Docker)
- Configuración en `pyproject.toml`: ruff, mypy, pytest, coverage

### Integraciones y fixes
- **FirmwareSection** integrado en mantenimiento (usa `firmware.py` existente)
- **desktop_backend real** integrado en Backup (copia/restaura GNOME/KDE)
- **EnhancedSoftwareManagerPage** como reemplazo directo compatible

## 1.1.9

- **Gestor de software**: detalles del paquete muestran la «Versión disponible» para actualizables; búsqueda por descripción del paquete (además de nombre e identificador) en la pestaña DEB.
- **Health Dashboard**: nueva pestaña «Salud del sistema» con tarjetas de estado (espacio en disco, actualizaciones, dpkg, APT, índices APT, DKMS, reinicio pendiente, servicios systemd); códigos de color por nivel; botón «Ejecutar diagnóstico completo».
- **Interfaz**: pestaña «Salud del sistema» entre Apps recomendadas y Backup; botón «Diagnosticar» retirado de Información del sistema (redundante).

## 1.1.8

- Reordena las pestañas: Configuración y mantenimiento, Gestor de software, Apps recomendadas, Backup e Inicio.

- Sustituye la pestaña Terminal por un botón con icono de terminal en el encabezado, junto al menú de preferencias, que abre la misma consola y conserva su sesión.

- Permite seleccionar varios paquetes DEB o aplicaciones Flatpak y añadirlos a una cola de instalación, actualización o desinstalación que se aplica de forma conjunta.

- Añade el botón «Actualizar todo» para poner en cola y aplicar todas las actualizaciones disponibles de la pestaña activa.

- Muestra la entrada predeterminada, la espera y la visibilidad vigentes de GRUB al cargar Inicio.

- Detecta incidencias pendientes de dpkg antes de instalar una actualización Testing y conserva el aislamiento de la descarga de APT.

- Ejecuta la auditoría de dpkg con la autorización del diagnóstico preventivo.

- Añade un apartado de firmware en Tareas a realizar, con búsqueda y actualización interactiva por dispositivo mediante fwupd.

## 1.1.7

- Los DEB locales sin coincidencia SHA-256 en un índice autenticado de APT requieren autenticación de administrador.

- El Gestor de software, Inicio (GRUB) y las copias de repositorios respetan la autorización sin contraseña de la primera pestaña.
- Permite abrir un .deb local en el Gestor de software, revisar sus dependencias y confirmar la instalación.
- Comprueba y sincroniza el reloj de forma desatendida antes del primer mantenimiento.
- La primera pestaña abre con los desplegables plegados y respeta su estado al redimensionar la ventana.
- El filtro Actualizables del Gestor de software incluye los paquetes DEB y las aplicaciones Flatpak del ámbito seleccionado.
- El Gestor de software muestra la descripción, las dependencias y otros datos del paquete seleccionado.

## 1.1.6

- Añade la pestaña Gestor de software al paquete DEB, con autocompletado y gestión de paquetes DEB, Flatpak y repositorios.
- Sitúa Gestor de software justo después de Apps recomendadas.
- Identifica los paquetes DEB y Flatpak instalados con una marca verde junto a su nombre.
- Retira Synaptic de las herramientas auxiliares que instala AiO.

## 1.1.5

- Reconoce AyusOS Linux y muestra su identidad en la cabecera y en los detalles técnicos.

## 1.1.4

- Ofrece reiniciar los servicios pendientes detectados al terminar el mantenimiento manual.
- Corrige el bloqueo al revisar una lista de aplicaciones importada.
- Incluye las aplicaciones recomendadas ya instaladas al exportar una lista, incluso sin selección manual.
- Los paquetes Testing usan un icono azul para distinguirlos de la edición estable.

## 1.1.3

- Corrección del paquete (revisión 1): incluye las apps recomendadas instaladas al exportar y completa la revisión de listas importadas al recuperar el foco.
- Permite exportar e importar una selección de Apps recomendadas con su formato de instalación.
- Añade Gradia, Flameshot, ONLYOFFICE Desktop Editors y Bitwarden a Apps recomendadas, con sus iconos.
- Añade el reintento de tareas fallidas desde el historial con una referencia a la ejecución original.
- El historial permite abrir ejecuciones manuales y programadas, revisar el estado de cada tarea y consultar los mensajes de error registrados.

- Añade filtros por categoría, una revisión de la selección y el reintento de instalaciones fallidas en Apps recomendadas.
- Añade una búsqueda por nombre y descripción en Apps recomendadas, compatible con la selección múltiple.
- Corrige el ajuste de la ventana al separar la terminal con btop o htop en ejecución.
- Añade HPLIP con HP Toolbox y Zoom Workplace a Apps recomendadas, con sus iconos.

## 1.1.2

- Añade el perfil Estándar como selección predeterminada y la purga de dependencias huérfanas al perfil Completo.
- Muestra la RAM física instalada y traduce los encabezados de tareas e información del sistema.
- Organiza los comandos de la terminal en categorías y añade un acceso rápido para limpiar la consola.
- Mueve los ajustes de diseño de Fastfetch a la terminal y resume el kernel, la arquitectura, el procesador y la RAM en Información del sistema.
- Añade Htop y Análisis del arranque al menú de comandos de la terminal.
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
