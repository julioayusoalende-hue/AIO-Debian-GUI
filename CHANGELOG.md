# Cambios

Al publicar una versión nueva: sube `Version` en `package/DEBIAN/control`, añade la
novedad en `NOVEDADES` (`package/usr/bin/aio-debian-gui`) y una sección `## X.Y.Z` aquí.
`scripts/check.sh` lo verifica.

## 1.0.8
Detecta si contrib/non-free, las herramientas auxiliares, GNOME Software Plugin Flatpak,
Extension Manager y el kernel/Mesa de Backports ya están configurados o instalados; muestra
el estado y desactiva las tareas completadas.
Añade un botón para cancelar la espera de Polkit y un límite para evitar que la interfaz
quede indefinidamente esperando una autorización que no llega.

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
