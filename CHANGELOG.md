# Cambios

Al publicar una versión nueva: sube `Version` en `package/DEBIAN/control`, añade la
novedad en `NOVEDADES` (`package/usr/bin/aio-debian-gui`) y una sección `## X.Y.Z` aquí.
`scripts/check.sh` lo verifica.

## 1.0.0
Primera versión independiente de la interfaz gráfica de AiO Debian: actualización con
apt, `contrib`/`non-free`, reloj, Flatpak + Flathub, complementos de GNOME y
comprobación de reinicio, todo desde una ventana.
