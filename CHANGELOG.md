# Cambios

Al publicar una versión nueva: sube `Version` en `package/DEBIAN/control`, añade la
novedad en `NOVEDADES` (`package/usr/bin/aio-debian-gui`) y una sección `## X.Y.Z` aquí.
`scripts/check.sh` lo verifica.

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
