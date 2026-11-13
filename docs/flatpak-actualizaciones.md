# Actualizaciones automáticas del Flatpak (repositorio propio)

Esta distribución es **independiente de Flathub**. Los paquetes se publican firmados en la rama `gh-pages`, bajo `flatpak-repo/`, sin eliminar el repositorio APT existente.

- Archivo de instalación que configura el origen: https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakref
- Archivo del repositorio: https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakrepo

**Instalación nueva (cuando la publicación termine con éxito):**

```bash
flatpak install --user https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakref
```

**Usuarios que ya instalaron el .flatpak sin origen:** añadir el remoto firmado desde el archivo .flatpakrepo y comprobar el origen existente con `flatpak info --show-origin io.github.julioayusoalende_hue.aio_debian_gui`. Si su instalación fue sin remoto, reinstalar desde .flatpakref (guardar preferencias antes) para asociarla al repositorio. No asumir que una instalación anterior recibe actualizaciones por arte de magia.

```bash
flatpak remote-add --user --if-not-exists aio-debian-gui https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakrepo
flatpak update --user
```

Tras publicar nuevas versiones, se instalan mediante `flatpak update --user`, GNOME Software/Discover u otro actualizador Flatpak (la instalación en segundo plano depende de cada escritorio).

## CI

El workflow `.github/workflows/publish-flatpak.yml` se dispara al cambiar los archivos relevantes en `main` y admite ejecución manual. Reutiliza `secrets.GPG_PRIVATE_KEY` y `secrets.GPG_PASSPHRASE` del repositorio APT; **no subas ninguna clave privada al código**. No se crea un origen sin firmas. El primer workflow debe terminar correctamente antes de compartir enlaces del repositorio.

Cada ejecución utiliza como base la rama `gh-pages` existente, añade nuevas revisiones OSTree y actualiza los archivos .flatpakref/.flatpakrepo. La publicación del bundle en GitHub Releases se actualiza para incluir la URL del repositorio y su clave, de modo que futuras instalaciones desde ese bundle registren su origen.

**Limitaciones:** las actualizaciones se refieren únicamente a la interfaz Flatpak. El helper privilegiado y la política Polkit que el usuario haya instalado manualmente en Debian **no se actualizan por Flatpak**. La tarea de host debe actualizarse mediante el paquete .deb o un procedimiento administrativo explícito y verificado. Si se cambia la clave GPG, se necesita un plan de transición; no sustituirla silenciosamente.

**Mantenimiento:** vigilar cuotas/limitaciones de GitHub Pages y el tamaño creciente del repositorio OSTree; para un repositorio grande, migrar a un hosting apto para ficheros OSTree conservando el endpoint o usando una redirección correcta. Comprobar que `flatpak remote-ls --user aio-debian-gui` y `flatpak update --user` funcionan antes de anunciarlo públicamente.
