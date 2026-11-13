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

Compatible con Debian 12 (bookworm) o superior y, desde la v1.2.0, con Ubuntu 24.04/26.04 LTS (modo nativo por distribución). En otros sistemas la interfaz es informativa y el mantenimiento privilegiado queda bloqueado.

**Actualizaciones:** la instalación mediante `.deb` usa el repositorio APT del proyecto; la instalación mediante `.flatpakref` usa nuestro **repositorio Flatpak firmado**, alojado en GitHub Pages, sin depender de que la aplicación esté publicada en Flathub. **No se ofrece un `.flatpak` independiente**. La edición AppImage se actualiza descargando una nueva versión.

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
superior). Si no hay `.deb` instalado,
el AppImage prepara su asistente en un directorio temporal accesible para Polkit y lo ejecuta
mediante Bash del sistema; la política y el asistente se instalan al activar la autorización sin
contraseña.

```bash
chmod +x aio-debian-gui_*_x86_64.AppImage
./aio-debian-gui_*_x86_64.AppImage
```

### Opción 4: Flatpak con actualizaciones desde nuestro repositorio

La instalación se hace con el archivo `.flatpakref` publicado en GitHub Pages; este
archivo registra automáticamente el repositorio firmado de AiO Debian GUI. **No hace falta
descargar cada nueva versión desde Releases.** Instala antes Flatpak en Debian si aún no
lo tienes (`sudo apt install flatpak`).

```bash
flatpak install --user https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakref
```

Después, las nuevas versiones se reciben desde ese origen con:

```bash
flatpak update --user
```

GNOME Software o Discover también pueden ofrecer actualizaciones en segundo plano si el
sistema tiene configurada la integración Flatpak y la actualización automática. No se garantiza
que todas las instalaciones de Debian actualicen aplicaciones sin intervención del usuario.
Puedes comprobar el origen instalado con:

```bash
flatpak info --user --show-origin io.github.julioayusoalende_hue.aio_debian_gui
```

**¿Ya instalaste un archivo `.flatpak` antiguo?** Comprueba su origen con el comando
anterior. Si no tiene un origen de actualización asociado, instala desde el enlace
`.flatpakref` anterior; si Flatpak no permite asociar ese origen a la instalación
existente, guarda primero tus preferencias/datos y reinstala la aplicación desde el
`.flatpakref`. No borres datos de la aplicación sin una copia. También puedes añadir
manualmente el repositorio de confianza firmado:

```bash
flatpak remote-add --user --if-not-exists aio-debian-gui \
  https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakrepo
```

**Distribución oficial Flatpak:** solo mediante el repositorio firmado y el enlace `.flatpakref`. Ya no distribuimos archivos `.flatpak` independientes en Releases. El manifiesto de `flatpak/` se conserva porque es necesario para compilar la aplicación y publicar las actualizaciones.

**Importante sobre las tareas administrativas:** actualizar la interfaz Flatpak **no
actualiza** el asistente privilegiado instalado manualmente en Debian. Si este asistente
necesita una versión nueva, debes actualizarlo explícitamente o mediante el paquete
`.deb`, según cómo lo instalaras. El repositorio de actualizaciones tampoco concede
privilegios automáticamente.

La instalación Flatpak **incluye la interfaz, el asistente de mantenimiento y la política Polkit** en el paquete obtenido del repositorio firmado. No es necesario descargar ni instalar el `.deb` para obtener estos archivos.
Para administrar APT y el Debian anfitrión, **sí es necesaria una integración
privilegiada explícita**: Flatpak y Flatseal no pueden instalar automáticamente
un servicio de sistema ni conceder privilegios de administrador.

1. Instala la aplicación con el comando `.flatpakref` anterior (requiere el runtime GNOME 51 disponible en Flathub, que Flatpak descargará si fuera necesario).

2. Si quieres utilizar las funciones de mantenimiento, extrae **del Flatpak
instalado** el asistente y la política Polkit en una carpeta temporal. Revísalos
antes de instalarlos con privilegios de administrador:

```bash
APP=io.github.julioayusoalende_hue.aio_debian_gui
mkdir -p "$HOME/aio-debian-gui-integracion"
flatpak run --command=cat "$APP" /app/share/aio-debian-gui/host-integration/aio-debian-gui-helper \
  > "$HOME/aio-debian-gui-integracion/aio-debian-gui-helper"
flatpak run --command=cat "$APP" /app/share/aio-debian-gui/host-integration/es.aiodebian.gui.policy \
  > "$HOME/aio-debian-gui-integracion/es.aiodebian.gui.policy"
less "$HOME/aio-debian-gui-integracion/aio-debian-gui-helper"
less "$HOME/aio-debian-gui-integracion/es.aiodebian.gui.policy"
```

3. Si aceptas otorgar permisos administrativos a este asistente, instala los
archivos en el anfitrión (se solicitará la contraseña de administrador):

```bash
sudo install -D -o root -g root -m 0755 \
  "$HOME/aio-debian-gui-integracion/aio-debian-gui-helper" \
  /usr/lib/aio-debian-gui/aio-debian-gui-helper
sudo install -D -o root -g root -m 0644 \
  "$HOME/aio-debian-gui-integracion/es.aiodebian.gui.policy" \
  /usr/share/polkit-1/actions/es.aiodebian.gui.policy
```

Reinicia AiO Debian GUI para que compruebe el asistente del anfitrión. Las tareas
administrativas requieren autorización Polkit; desde la v1.0.19 no se admite habilitar una autorización permanente sin contraseña. Si ya hay un asistente instalado por un paquete
`.deb`, no lo sobrescribas sin comprobar la versión y el origen.

Para eliminar la integración manual, **solo si no la gestiona el paquete .deb**:

```bash
sudo rm /usr/lib/aio-debian-gui/aio-debian-gui-helper
sudo rm /usr/share/polkit-1/actions/es.aiodebian.gui.policy
```

#### Permisos opcionales con Flatseal

Puedes instalar Flatseal desde Flathub y modificar los permisos de AiO Debian GUI.
Los permisos predeterminados permiten la interfaz gráfica y la comunicación con
`flatpak-spawn --host`. **Flatseal no sustituye el asistente Polkit**.
No concedas `filesystem=host`, `--device=all`, acceso indiscriminado al bus
D-Bus ni permisos equivalentes: no son necesarios para este flujo y amplían el
riesgo. Si revocas el permiso de comunicación con `org.freedesktop.Flatpak`,
la integración con el anfitrión dejará de funcionar.

**Aviso de seguridad:** el asistente se ejecuta como administrador cuando
Polkit lo autoriza y puede modificar paquetes, repositorios y kernel. Comprueba
siempre que el archivo procede de una versión confiable. La instalación manual
del asistente no se actualiza automáticamente al actualizar el Flatpak: repite
la extracción e instalación tras cada actualización que cambie el asistente.

### Opción 5: compilar desde el código

```bash
git clone https://github.com/julioayusoalende-hue/AIO-Debian-GUI.git
cd AIO-Debian-GUI
./scripts/build-deb.sh
APPIMAGETOOL=/ruta/a/appimagetool ./scripts/build-appimage.sh
flatpak-builder --user --force-clean --install-deps-from=flathub --repo=flatpak-repo \
  flatpak-build flatpak/io.github.julioayusoalende_hue.aio_debian_gui.yml
flatpak remote-add --user --if-not-exists aio-debian-gui \
  https://julioayusoalende-hue.github.io/AIO-Debian-GUI/aio-debian-gui.flatpakrepo
sudo apt install ./dist/aio-debian-gui_*_all.deb
```

El AppImage se construye para `x86_64` y usa el runtime de Debian; instala
`appimagetool` para generarlo.

## Actualizar desde la interfaz (v1.0.19 y posteriores)

La cabecera indica si estás utilizando **DEB**, **AppImage** o **Flatpak**. En los tres formatos aparece el botón **«Buscar actualizaciones»**, que consulta las versiones disponibles y solicita confirmación antes de aplicar cambios.

- **AppImage:** consulta la última versión estable en GitHub Releases. Si existe una versión nueva, descarga el AppImage en **Descargas**, comprueba su integridad con el archivo `SHA256SUMS` oficial y lo deja preparado para ejecutarlo. No sobrescribe ni elimina el AppImage actualmente abierto: cierra la versión anterior y ejecuta el archivo recién descargado.
- **Flatpak:** ejecuta `flatpak update --user --noninteractive -y io.github.julioayusoalende_hue.aio_debian_gui` en el anfitrión mediante `flatpak-spawn --host`. Requiere instalar desde nuestro `.flatpakref` y conservar el repositorio firmado. Reinicia la aplicación para cargar la nueva versión si se ha actualizado.
- **Paquete .deb:** utiliza el asistente Polkit existente para comprobar el repositorio APT e instalar solamente una actualización del paquete `aio-debian-gui`, si existe. Se solicita autorización de administrador; no se realiza una actualización general del sistema.

**Aviso:** actualizar el Flatpak **no modifica el asistente privilegiado ni la política Polkit instalados manualmente en Debian**. Desde la v1.0.19, el Flatpak comprueba que la versión del asistente anfitrión coincide con la aplicación antes de ejecutar tareas administrativas; si no coincide, actualiza la integración manual siguiendo estas instrucciones.

## Historial y vista previa (desde v1.0.20)

Antes de iniciar el mantenimiento se muestra una lista de las tareas seleccionadas y
se solicita confirmación. **Esta vista previa no calcula la resolución de dependencias
de APT**, que puede instalar, actualizar o eliminar paquetes adicionales. El usuario
debe prestar atención especial a las operaciones de Backports y eliminación.

Desde el menú superior puedes abrir **Historial de mantenimiento** y exportar los
resultados a JSON. Se registran hasta 100 ejecuciones por usuario, con fecha, versión,
tareas y resultado, en el directorio de estado de usuario (`$XDG_STATE_HOME/aio-debian-gui/history.json`,
o `~/.local/state/aio-debian-gui/history.json`). No se guardan credenciales ni salidas
completas de la consola. El historial no registra operaciones que aún no hayan comenzado.

## Debian y Ubuntu LTS (desde v1.2.0)

La aplicación lee `/etc/os-release` del sistema anfitrión para identificar Debian o Ubuntu. La tarjeta de información inicial muestra automáticamente el logotipo correspondiente (desde v1.2.1), también al usar AppImage o Flatpak.
En **Debian** muestra contrib/non-free y Backports; en **Ubuntu 24.04/26.04 LTS**
muestra la activación de los componentes oficiales `universe`, `restricted` y
`multiverse` mediante `add-apt-repository`, y una tarea opcional para instalar el
metapaquete de kernel **HWE** oficial, **solo si existe** en los repositorios configurados.
No añade repositorios Debian a Ubuntu ni PPAs. La actualización general sigue
utilizando APT; el soporte Flatpak se mantiene. Las tareas incompatibles se bloquean
también en el asistente privilegiado, incluso si se invoca directamente.

**Aviso:** el soporte requiere pruebas de integración y validación en instalaciones reales
para confirmar el funcionamiento completo de cada combinación de Ubuntu, escritorio y formato.
Se recomienda una copia de seguridad antes de habilitar nuevos repositorios o instalar HWE.

## Uso

Busca *AiO Debian GUI* en el menú de aplicaciones, o ejecuta `aio-debian-gui` como usuario
normal. Las operaciones administrativas requieren autenticación de administrador en
una sesión local activa. Desde la versión 1.0.19 se ha retirado la posibilidad de
habilitar autorizaciones Polkit persistentes sin contraseña. El paquete DEB revoca
al actualizar las reglas antiguas que coinciden con la plantilla de AiO. En AppImage
o integraciones manuales, si queda una autorización antigua, utiliza la opción de
revocación (si aparece activa) o retira la regla identificada como
`/etc/polkit-1/rules.d/50-aiodebian-gui-UID.rules` tras comprobar su contenido.
La instalación del kernel y Mesa desde Backports
también está desactivada por defecto; al activarla, puede añadirse la fuente oficial
`<codename>-backports` y puede ser necesario reiniciar después.
Las tareas de repositorios, herramientas, Backports y complementos de GNOME se marcan cuando ya
están completas y su selector queda desactivado; el estado se vuelve a comprobar al abrir la
aplicación. Si la espera de autorización de Polkit no responde, puede cancelarse desde la interfaz
y se cancela automáticamente tras 90 segundos.
La comprobación inicial de las tareas se ejecuta en segundo plano; el botón de inicio
permanece disponible para las tareas seleccionadas aunque falle o se retrase la consulta de estados.
El menú superior permite elegir el idioma de la interfaz (español, inglés, francés o chino),
el tema claro u oscuro y el modo simple, que oculta la salida detallada de las tareas. Las
preferencias se guardan para el usuario actual; el español, el tema claro y la interfaz completa
son los valores iniciales.
La ventana «Acerca de» muestra el crédito del autor y permite abrir una dedicatoria con una foto
proporcionada por el usuario.

## Arquitectura modular (v1.1.0)

La interfaz GTK continúa en `package/usr/bin/aio-debian-gui`, pero la lógica de
actualizaciones AppImage, historial y preferencias está separada en
`package/usr/lib/aio-debian-gui/aio_core/`, sin dependencias GTK.
La interfaz utiliza funciones adaptadoras para mantener la compatibilidad y los tres
formatos incluyen los mismos módulos. Las pruebas offline comprueban cada módulo
sin ejecutar tareas de mantenimiento privilegiadas.

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
  publish-flatpak-repo.sh                 construye y publica el repositorio Flatpak firmado
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

5. Publica los paquetes `.deb` y AppImage en la *Release* de GitHub y actualiza el repositorio APT con
   `scripts/publish-apt-repo.sh` sobre la rama `gh-pages`.
6. El workflow [Publish signed Flatpak update repository](.github/workflows/publish-flatpak.yml)
   actualiza exclusivamente el repositorio Flatpak firmado de GitHub Pages
   al publicar cambios relevantes en `main`. También se puede ejecutar manualmente desde Actions.
   Consulta [actualizaciones Flatpak](docs/flatpak-actualizaciones.md).

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
