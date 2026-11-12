# AIO-Debian-GUI

Interfaz gráfica de mantenimiento y configuración todo en uno para Debian.

- Actualiza el sistema con apt (`update`, `dist-upgrade`, `autoremove`, `autoclean`).
- Habilita `contrib` y `non-free`.
- Instala herramientas auxiliares, incluido el soporte FUSE para AppImage.
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
asistente. La opción de autorización sin contraseña requiere que el asistente del sistema incluya
esa función (v1.0.6 o superior). Si no hay `.deb` instalado, el AppImage usa e instala su
asistente y política tras una autorización inicial.

```bash
chmod +x aio-debian-gui_*_x86_64.AppImage
./aio-debian-gui_*_x86_64.AppImage
```

### Opción 4: compilar desde el código

```bash
git clone https://github.com/julioayusoalende-hue/AIO-Debian-GUI.git
cd AIO-Debian-GUI
./scripts/build-deb.sh
APPIMAGETOOL=/ruta/a/appimagetool ./scripts/build-appimage.sh
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
administrador sin volver a pedir contraseña.

## Estructura

```
package/                                  árbol que se instala tal cual en el sistema
  DEBIAN/control                          metadatos y versión
  usr/bin/aio-debian-gui                  interfaz gráfica (GTK 3, se ejecuta como usuario)
  usr/lib/aio-debian-gui/aio-debian-gui-helper   tareas privilegiadas (vía pkexec)
  usr/share/aio-debian-gui/              logotipo de Debian mostrado en la tarjeta de información
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
