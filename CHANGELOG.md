# Cambios

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


Al publicar una versión nueva: sube `Version` en `package/DEBIAN/control`, añade la
novedad en `NOVEDADES` (`package/usr/bin/aio-debian-gui`) y una sección `## X.Y.Z` aquí.
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

## 1.0.8
Detecta si contrib/non-free, las herramientas auxiliares, GNOME Software Plugin Flatpak,
Extension Manager y el kernel/Mesa de Backports ya están configurados o instalados; muestra
el estado y desactiva las tareas completadas.
Añade un botón para cancelar la espera de Polkit y un límite para evitar que la interfaz
quede indefinidamente esperando una autorización que no llega.

## 1.0.9
Los botones «Completo» y «Solo Flatpak» resaltan el preset seleccionado. El resaltado se
quita si se modifica una tarea individualmente.

## 1.0.7
Añade una opción para instalar el kernel de la arquitectura y los controladores Mesa
disponibles desde Debian Backports. La opción está desactivada por defecto y avisa
que puede requerir reiniciar.

## 1.0.6
Añade una opción para permitir, tras una autorización inicial, tareas sin contraseña
para el usuario actual y solo en la sesión local activa. El AppImage reutiliza el
asistente del sistema aunque sea de otra versión; la opción nueva verifica que el
asistente tenga esa capacidad.

## 1.0.5
Se corrige la autenticación al ejecutar el AppImage cuando está instalado el paquete Debian.

## 1.0.4
La aplicación también se distribuye como AppImage.

## 1.0.5
Se corrige la autenticación al ejecutar el AppImage cuando está instalado el paquete Debian.

## 1.0.3
Las herramientas auxiliares instalan el soporte FUSE necesario para ejecutar AppImage.

## 1.0.2
El logotipo de Debian aparece junto a la información del sistema.

## 1.0.1
El botón principal ahora se llama «Iniciar tareas».

## 1.0.0
Primera versión independiente de la interfaz gráfica de AiO Debian: actualización con
apt, `contrib`/`non-free`, reloj, Flatpak + Flathub, complementos de GNOME y
comprobación de reinicio, todo desde una ventana.
