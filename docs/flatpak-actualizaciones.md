# Instalación y actualización de Flatpak

AiO Debian GUI se distribuye desde un **repositorio propio firmado**, independiente de Flathub. Flathub se utiliza para el runtime. El identificador es `io.github.julioayusoalende_hue.aio_debian_gui`, rama `stable`.

## Instalación recomendada

```bash
sudo apt install flatpak
flatpak install --user https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakref
flatpak run io.github.julioayusoalende_hue.aio_debian_gui
```

La referencia configura el origen firmado para recibir actualizaciones. Ejecuta los comandos Flatpak como tu usuario habitual, sin sudo.

## Actualizar

```bash
flatpak update --user io.github.julioayusoalende_hue.aio_debian_gui
```

También puedes usar **Menú → Buscar actualizaciones** en AiO o un gestor como GNOME Software/Discover. Las actualizaciones en segundo plano dependen de la configuración del escritorio. Cierra y vuelve a abrir AiO para cargar la versión nueva.

## Bundle descargado de Releases

Las [releases publicadas](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases) incluyen un bundle `.flatpak`. Por ejemplo, para la versión 2.10.9:

```bash
flatpak install --user ./aio-debian-gui_2.10.9_x86_64.flatpak
```

Instalar el bundle no configura por sí solo el repositorio de actualizaciones. Comprueba el origen de tu instalación:

```bash
flatpak info --user --show-origin io.github.julioayusoalende_hue.aio_debian_gui
flatpak remotes --user --show-details
```

Para configurar el remoto firmado del proyecto:

```bash
flatpak remote-add --user --if-not-exists aio-debian-gui https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakrepo
```

Añadir un remoto no cambia automáticamente el origen de una aplicación ya instalada. Si el bundle quedó sin un origen actualizable, guarda tus preferencias y reinstala desde la referencia:

```bash
flatpak install --user --reinstall https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakref
flatpak update --user io.github.julioayusoalende_hue.aio_debian_gui
```

Revisa las confirmaciones de Flatpak y comprueba de nuevo el origen. No necesitas borrar los datos de la aplicación.

## Integración del sistema anfitrión

Flatpak actualiza la interfaz. Las operaciones administrativas y la programación con AiO cerrado necesitan además el asistente en el anfitrión. **No requieren instalar la interfaz DEB.**

Desde AiO, abre **Menú → Guía de integración del anfitrión → Instalar integración automáticamente**. Con autorización administrativa, la versión actual instala `aio-debian-gui-host` desde un repositorio firmado y aislado. Su temporizador actualiza la integración a la versión solicitada por AiO, esperando a que no haya mantenimiento en curso. Incluye las dependencias de notificaciones y comprobación de reinicio.

El paquete de integración entra en conflicto con la interfaz `aio-debian-gui` del DEB. Si tienes el DEB, mantenlo actualizado con APT. Para integraciones manuales antiguas o conflictos de archivos, consulta la guía integrada antes de modificar el sistema. Si el repositorio no responde, la instalación puede recurrir a la copia inicial incluida; esa alternativa no proporciona por sí sola la actualización del paquete host.

Consulta [Programación y permisos](../README.md#programación-y-permisos) para conocer los requisitos de systemd y autorización.

## Publicación y mantenimiento

El workflow [publish-flatpak.yml](../.github/workflows/publish-flatpak.yml) publica en la rama `gh-pages`, bajo `flatpak-repo/`, conservando el repositorio APT. Utiliza los secretos GPG configurados en GitHub; las claves privadas nunca se incluyen en el código.

Antes de anunciar una publicación, comprueba el resultado del workflow, la referencia y el repositorio, y verifica desde un equipo con Flatpak:

```bash
flatpak remote-ls --user aio-debian-gui
flatpak update --user io.github.julioayusoalende_hue.aio_debian_gui
```

Vigila el tamaño del repositorio OSTree y las cuotas de GitHub Pages. Los cambios de clave GPG requieren una transición explícita.
