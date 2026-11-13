# AIO-Debian-GUI

Interfaz gráfica de mantenimiento y configuración todo en uno para Debian.

- Actualiza el sistema con apt (`update`, `dist-upgrade`, `autoremove`, `autoclean`).
- Habilita `contrib` y `non-free`.
- Instala herramientas auxiliares, incluido el soporte FUSE para AppImage.
- Permite instalar opcionalmente el kernel y los controladores Mesa desde Debian Backports.
- Indica si las tareas de repositorios, herramientas y Backports ya están completadas.
- Sincroniza el reloj, instala Flatpak + Flathub y actualiza las apps Flatpak.
- Complementos para GNOME (plugin Flatpak de GNOME Software, Extension Manager).
- Comprueba si hace falta reiniciar y lo ofrece al terminar.

Es un proyecto independiente: no necesita el script de consola
[aio-debian](https://github.com/julioayusoalende-hue/aio-debian) (puedes tener ambos).

## Instalación

Pensado para Debian 12 (bookworm) o superior y derivados con `apt`.

### Opción 1: descargar el .deb

Descarga el último `aio-debian-gui_X.Y.Z_all.deb` desde [Releases](../../releases/latest) y:

```bash
sudo apt install ./aio-debian-gui_*_all.deb
```

Al instalarlo se configura automáticamente el repositorio APT, así que las
actualizaciones llegarán con `sudo apt update && sudo apt upgrade`.

### Opción 2: instalar el repositorio y la aplicación con un comando

Este comando configura la clave y el repositorio APT, actualiza el índice e instala
AiO Debian GUI:

```bash
sudo bash -c 'set -euo pipefail; key=$(mktemp); trap "rm -f $key" EXIT; python3 -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.gpg "$key"; install -D -m 0644 "$key" /usr/share/keyrings/aio-debian-gui.gpg; printf "%s\n" "Types: deb" "URIs: https://julioayusoalende-hue.github.io/AIO-Debian-GUI" "Suites: stable" "Components: main" "Architectures: all" "Signed-By: /usr/share/keyrings/aio-debian-gui.gpg" > /etc/apt/sources.list.d/aio-debian-gui.sources; apt-get update; apt-get install aio-debian-gui'
```

### Opción 3: AppImage

Descarga el archivo `aio-debian-gui_X.Y.Z_x86_64.AppImage` desde [Releases](../../releases/latest),
dale permiso de ejecución y ábrelo. El AppImage incluye la interfaz y el asistente; requiere
en el sistema `python3-gi`, GTK 3, `pkexec`, APT y FUSE 2 (`libfuse2` en Debian 12,
`libfuse2t64` en Debian 13). No hace falta instalar el `.deb`. Si hay un asistente instalado
por el paquete `.deb`, el AppImage reutiliza ese asistente para respetar la ruta fija de Polkit,
aunque sea de otra versión. Las tareas normales dependen de las funciones disponibles en ese
asistente. La tarea de kernel y Mesa desde Backports requiere que incluya esa función (v1.0.7 o
superior); la autorización sin contraseña requiere v1.0.6 o superior. Si no hay `.deb` instalado,
el AppImage prepara su asistente en un directorio temporal accesible para Polkit y lo ejecuta
mediante Bash del sistema; la política y el asistente se instalan al activar la autorización sin
contraseña.

```bash
chmod +x aio-debian-gui_*_x86_64.AppImage
./aio-debian-gui_*_x86_64.AppImage
```

### Opción 4: Flatpak

El Flatpak ofrece la interfaz gráfica dentro de un sandbox. Por diseño, no instala
ni modifica componentes privilegiados del sistema anfitrión. Para ejecutar tareas
de mantenimiento (APT, repositorios, Backports, Flatpak del anfitrión y Polkit),
**primero instala en Debian el paquete .deb de AiO Debian GUI de la misma versión**.
El Flatpak delega esas operaciones al asistente del anfitrión mediante
`flatpak-spawn` y Polkit; no concede acceso general al sistema de archivos ni
incluye permisos privilegiados dentro del sandbox.

Descarga `aio-debian-gui_1.0.16_x86_64.flatpak` desde [Releases](../../releases/latest)
y, con Flathub configurado, instala el runtime y la aplicación:

```bash
flatpak install flathub org.gnome.Platform//48
flatpak install --user ./aio-debian-gui_1.0.16_x86_64.flatpak
```

Si no tienes Flathub configurado:

```bash
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```

**Importante:** el Flatpak no es una instalación autónoma para administrar Debian.
Sin el paquete .deb anfitrión, la interfaz puede abrirse, pero las tareas administrativas
no estarán disponibles. Para una instalación independiente y completa, utiliza el .deb
o la AppImage.

### Opción 5: compilar desde el código

```bash
git clone https://github.com/julioayusoalende-hue/AIO-Debian-GUI.git
cd AIO-Debian-GUI
./scripts/build-deb.sh
APPIMAGETOOL=/ruta/a/appimagetool ./scripts/build-appimage.sh
flatpak-builder --user --force-clean --install-deps-from=flathub --repo=flatpak-repo \
  flatpak-build flatpak/io.github.julioayusoalende_hue.aio_debian_gui.yml
flatpak build-bundle flatpak-repo dist/aio-debian-gui_1.0.16_x86_64.flatpak \
  io.github.julioayusoalende_hue.aio_debian_gui stable
sudo apt install ./dist/aio-debian-gui_*_all.deb
```

El AppImage se construye para `x86_64` y usa el runtime de Debian; instala
`appimagetool` para generarlo.

## Uso

Busca *AiO Debian GUI* en el menú de aplicaciones, o ejecuta `aio-debian-gui` como usuario
normal. Por defecto, solicita autorización de administrador al pulsar «Iniciar tareas». La opción
de autorización sin contraseña queda desactivada inicialmente; al activarla, se solicita
autorización una vez y se crea una regla persistente de Polkit para el usuario actual, limitada
al asistente de AiO en sesiones locales activas. Desactívala desde la misma opción para revocarla.
Mientras esté activa, todas las tareas de mantenimiento de AiO podrán ejecutarse como
administrador sin volver a pedir contraseña. La instalación del kernel y Mesa desde Backports
también está desactivada por defecto; al activarla, puede añadirse la fuente oficial
`<codename>-backports` y puede ser necesario reiniciar después.
Las tareas de repositorios, herramientas, Backports y complementos de GNOME se marcan cuando ya
están completas y su selector queda desactivado; el estado se vuelve a comprobar al abrir la
aplicación. Si la espera de autorización de Polkit no responde, puede cancelarse desde la interfaz
y se cancela automáticamente tras 90 segundos.
La comprobación inicial de las tareas se ejecuta en segundo plano: las opciones permanecen
disponibles mientras se comprueba y el botón de inicio se habilita al terminar. Si la comprobación
se bloquea, se cancela automáticamente tras 30 segundos.
El menú superior permite elegir el idioma de la interfaz (español, inglés, francés o chino),
el tema claro u oscuro y el modo simple, que oculta la salida detallada de las tareas. Las
preferencias se guardan para el usuario actual; el español, el tema claro y la interfaz completa
son los valores iniciales.
La ventana «Acerca de» muestra el crédito del autor y permite abrir una dedicatoria con una foto
proporcionada por el usuario.

## Estructura

```
package/                                  árbol que se instala tal cual en el sistema
  DEBIAN/control                          metadatos y versión
  usr/bin/aio-debian-gui                  interfaz gráfica (GTK 3, se ejecuta como usuario)
  usr/lib/aio-debian-gui/aio-debian-gui-helper   tareas privilegiadas (vía pkexec)
  usr/share/aio-debian-gui/              logotipo de Debian y foto de la dedicatoria
  usr/share/polkit-1/actions/             política de autenticación
scripts/
  build-deb.sh                            construye dist/aio-debian-gui_X.Y.Z_all.deb
  build-appimage.sh                       construye dist/aio-debian-gui_X.Y.Z_x86_64.AppImage
  appimage/AppRun                         lanzador del AppImage
  check.sh                                comprobaciones previas a publicar
  publish-apt-repo.sh                     añade el .deb al repositorio APT y lo firma
  recolor-icon.py                         regenera los iconos con otro color de fondo
assets/icon-original-512.png              icono original (fondo azul), base de recolor-icon.py
.github/workflows/                        CI y publicación automática
```

## Cambiar el color del icono

El icono usa fondo verde para distinguirse del de `aio-debian`. Para otro color
(necesita `python3-pil` y `python3-numpy`):

```bash
./scripts/recolor-icon.py 28      # naranja · 275 violeta · 350 rojo · 145 verde (actual)
```

## Publicar una versión nueva

1. Sube `Version` en `package/DEBIAN/control`.
2. Añade la novedad en `NOVEDADES` (`package/usr/bin/aio-debian-gui`) y una sección
   `## X.Y.Z` en `CHANGELOG.md`.
3. Comprueba: `./scripts/check.sh`
4. Construye los paquetes:

   ```bash
   ./scripts/build-deb.sh
   APPIMAGETOOL=/ruta/a/appimagetool ./scripts/build-appimage.sh
   ```

5. Publica ambos archivos en la *Release* de GitHub y actualiza el repositorio APT con
   `scripts/publish-apt-repo.sh` sobre la rama `gh-pages`.

## Configuración inicial en GitHub (una sola vez)

1. **Secretos** (*Settings → Secrets and variables → Actions*):
   - `GPG_PRIVATE_KEY`: la clave privada con la que se firma el repositorio.
   - `GPG_PASSPHRASE`: su contraseña (si la tiene).

   La publicación comprueba que la clave coincide con la clave pública incluida en
   `package/usr/share/keyrings/aio-debian-gui.gpg`; si no, se aborta para no romper las
   actualizaciones de los equipos ya instalados.
2. **Pages** (*Settings → Pages*): *Deploy from a branch* → `gh-pages` / `/ (root)`.
   La rama se crea sola con la primera publicación.

### Sobre la clave de firma

El paquete incluye la clave pública `04A5 2381 A203 5D5B 9524 CA6A E0E6 4B8E E0F9 000C`
(la misma del repositorio de `aio-debian`), de modo que puedes usar la clave privada que
ya tienes. Si prefieres una clave propia para este proyecto, **antes de la primera
publicación**:

```bash
gpg --quick-gen-key "AIO-Debian-GUI repositorio <tu@correo>" rsa4096 sign 5y
gpg --export <HUELLA> > package/usr/share/keyrings/aio-debian-gui.gpg
gpg --armor --export-secret-keys <HUELLA>     # contenido para el secreto GPG_PRIVATE_KEY
```

## Licencia

GNU GPL v3 o posterior. Consulta [LICENSE](LICENSE). Sin ninguna garantía.
