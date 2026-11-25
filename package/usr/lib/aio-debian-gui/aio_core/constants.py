"""Constantes y datos compartidos para AIO Debian GUI."""

import json
import os
import pwd
import re
import sys

from .translations import TRADUCCIONES

# Rutas base
PRGNAME = "aio-debian-gui"
APP_ICON_NAME = "aio-debian-gui"
POLKIT_ACTION = "es.aiodebian.gui.mantenimiento"
POLKIT_RULES_DIR = "/etc/polkit-1/rules.d"
PASSWORDLESS_STATE_DIR = "/var/lib/aio-debian-gui/passwordless"

# aio_core vive en <prefijo>/lib/aio-debian-gui/aio_core; el asistente, en el
# directorio padre, y los recursos compartidos en <prefijo>/share/aio-debian-gui.
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_SHARE_DIR = os.path.normpath(os.path.join(_LIB_DIR, "../../../share/aio-debian-gui"))

HELPER = os.path.normpath(os.path.join(_LIB_DIR, "../aio-debian-gui-helper"))
HELPER_SISTEMA = "/usr/lib/aio-debian-gui/aio-debian-gui-helper"
GRUB_HELPER = "/usr/lib/aio-debian-gui/aio-grub-settings"
APT_BACKUP_HELPER = "/usr/lib/aio-debian-gui/aio-apt-sources-backup"
APT_BACKUP_FILENAME = "repositorios-apt.json"
APT_BACKUP_LIMIT = 32 * 1024 * 1024

HOMEPAGE = "https://github.com/julioayusoalende-hue/AIO-Debian-GUI"

DEBIAN_LOGO = os.path.join(_SHARE_DIR, "debian-openlogo.png")
UBUNTU_LOGO = os.path.join(_SHARE_DIR, "ubuntu-logo.svg")
AYUSOS_LOGO = os.path.join(_SHARE_DIR, "ayusos-logo.png")

NOMBRE_AYUSOS = re.compile(r"^AyusOS(?: Linux)?\b", re.IGNORECASE)

FASTFETCH_LAYOUT = os.path.join(_SHARE_DIR, "fastfetch-layout.jsonc")
NOTAS_VERSION = os.path.join(_SHARE_DIR, "release-notes.txt")

RECOMMENDED_ICON_DIR = os.path.join(_SHARE_DIR, "recommended-icons")
BACKUP_ICON_DIR = os.path.join(_SHARE_DIR, "backup-icons")

# Preferencias por defecto
PREFERENCIAS_DEFECTO = {
    "idioma": "es",
    "tema": "sistema",
    "modo_simple": False,
    "carpeta_repositorios": "",
    "canal_actualizaciones": "stable",
    "reloj_inicial_sincronizado": False,
}

IDIOMAS = {"es", "en", "fr", "zh"}
TEMAS = {"sistema", "claro", "oscuro"}

# Variables globales (se inicializan en main)
IDIOMA_ACTUAL = "es"


def traducir(texto):
    return TRADUCCIONES.get(IDIOMA_ACTUAL, {}).get(texto, texto)


def traducir_detalle_diagnostico(texto):
    """Traduce resultados variables; conserva mensajes técnicos no reconocidos."""
    texto_traducido = traducir(texto)
    if texto_traducido != texto:
        return texto_traducido
    disco = re.fullmatch(r"(\d+(?:\.\d+)?) GiB libres \((\d+)% del volumen\)", texto)
    if disco:
        return traducir("%.1f GiB libres (%s del volumen)") % (
            float(disco.group(1)), disco.group(2) + "%")
    pendientes = re.fullmatch(r"(\d+) actualizaciones estimadas por APT(; (\d+) retenidos)?\.", texto)
    if pendientes:
        sufijo = (traducir("; %d retenidos") % int(pendientes.group(3))
                  if pendientes.group(3) else "")
        return traducir("%d actualizaciones estimadas por APT%s.") % (
            int(pendientes.group(1)), sufijo)
    pendientes_locales = re.fullmatch(r"(\d+) actualizaciones disponibles según los índices APT locales\.", texto)
    if pendientes_locales:
        return traducir("%d actualizaciones disponibles según los índices APT locales.") % int(pendientes_locales.group(1))
    indices = re.fullmatch(r"Último índice de paquetes: hace (\d+) días\.", texto)
    if indices:
        return traducir("Último índice de paquetes: hace %d días.") % int(indices.group(1))
    disponible = re.fullmatch(r"Instalada: ([\w.+:~-]+)\. Disponible en APT: ([\w.+:~-]+)\.", texto)
    if disponible:
        return traducir("Instalada: %s. Disponible en APT: %s.") % disponible.groups()
    actualizado = re.fullmatch(r"Instalada: ([\w.+:~-]+)\. Al día según los índices APT locales\.", texto)
    if actualizado:
        return traducir("Instalada: %s. Al día según los índices APT locales.") % actualizado.group(1)
    return texto


# Historial
MAX_HISTORIAL = 100

def ruta_historial():
    from gi.repository import GLib

    from .history import ruta_historial as _ruta_historial
    return _ruta_historial(GLib.get_user_state_dir())

def leer_historial(ruta=None):
    from .history import leer_historial as _leer_historial
    return _leer_historial(ruta or ruta_historial())

def guardar_registro_mantenimiento(tareas, resultado, reinicio=False, ruta=None, **detalle):
    from .history import guardar_registro_mantenimiento as _guardar
    from .updates import version_app as _version_app
    return _guardar(tareas, resultado, reinicio, ruta or ruta_historial(),
                    formato=formato_actualizacion() or "desarrollo",
                    version=_version_app(), **detalle)


def ruta_preferencias():
    from gi.repository import GLib
    return os.path.join(GLib.get_user_config_dir(), PRGNAME, "preferences.json")

def cargar_preferencias(ruta=None):
    from .preferences import cargar_preferencias as _cargar
    return _cargar(ruta or ruta_preferencias(), PREFERENCIAS_DEFECTO)

def guardar_preferencias(preferencias, ruta=None):
    from .preferences import guardar_preferencias as _guardar
    return _guardar(preferencias, ruta or ruta_preferencias())


# Utilidades del sistema
def es_flatpak():
    return bool(os.environ.get("FLATPAK_ID"))

def comando_host(*argumentos):
    if es_flatpak():
        return ["flatpak-spawn", "--host", *argumentos]
    return list(argumentos)

def leer_texto(ruta):
    if es_flatpak():
        try:
            import subprocess
            resultado = subprocess.run(
                comando_host("cat", ruta), capture_output=True, text=True, timeout=10
            )
            return resultado.stdout if resultado.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None
    try:
        with open(ruta, encoding="utf-8") as archivo:
            return archivo.read()
    except OSError:
        return None

def paquete_instalado(nombre):
    try:
        import subprocess
        out = subprocess.run(
            comando_host("dpkg-query", "-W", "-f=${Status}", nombre),
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "install ok installed" in out


def version_app(para_apt=False):
    if os.environ.get("SNAP_VERSION"):
        return os.environ["SNAP_VERSION"]
    version = os.environ.get("AIO_DEBIAN_GUI_VERSION")
    if version:
        return version
    try:
        import subprocess
        out = subprocess.run(
            comando_host("dpkg-query", "-W", "-f=${Status}|${Version}", "aio-debian-gui"),
            capture_output=True, text=True, timeout=10,
        ).stdout
        estado, _, version = out.partition("|")
        if "install ok installed" in estado and version:
            return version if para_apt else version.split(":", 1)[-1]
    except (OSError, subprocess.SubprocessError):
        pass
    return "desarrollo (no instalado desde paquete)"


def formato_actualizacion():
    if os.environ.get("SNAP"):
        return "snap"
    if es_flatpak():
        return "flatpak"
    if os.environ.get("APPDIR"):
        return "appimage"
    if os.path.realpath(sys.argv[0]) == "/usr/bin/aio-debian-gui":
        return "deb"
    return None


# Distribución
def datos_distribucion_anfitrion():
    contenido = leer_texto("/etc/os-release")
    valores = {}
    for linea in (contenido or "").splitlines():
        if "=" in linea and not linea.startswith("#"):
            clave, valor = linea.split("=", 1)
            if clave in ("ID", "VERSION_ID", "NAME", "PRETTY_NAME", "LOGO"):
                valores[clave] = valor.strip().strip('"').strip("'")
    return valores

def distribucion_anfitrion(valores=None):
    from .scheduler import maintenance_distro
    if valores is None:
        valores = datos_distribucion_anfitrion()
    return maintenance_distro(valores) or "no-soportada"

def identidad_distribucion(datos):
    sistema = datos.get("ID")
    if sistema == "debian" and (
        any(NOMBRE_AYUSOS.match(datos.get(campo, "")) for campo in ("NAME", "PRETTY_NAME"))
        or datos.get("LOGO") in ("ayusos", "ayusos-logo")
    ):
        return "ayusos"
    return sistema

def logo_distribucion(distribucion):
    if distribucion == "ayusos":
        return AYUSOS_LOGO, "Logotipo de AyusOS Linux"
    if distribucion == "ubuntu":
        return UBUNTU_LOGO, "Logotipo de Ubuntu"
    if distribucion == "debian":
        return DEBIAN_LOGO, "Logotipo de Debian"
    return None, None

def imagen_logo_distribucion(datos, tamano):
    from gi.repository import GdkPixbuf, GLib, Gtk
    ruta, nombre_logo = logo_distribucion(identidad_distribucion(datos))
    if ruta is None:
        return None
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(ruta, tamano, tamano, True)
    except GLib.Error:
        return None
    logo = Gtk.Image.new_from_pixbuf(pixbuf)
    logo.get_accessible().set_name(traducir(nombre_logo))
    logo.set_tooltip_text(traducir(nombre_logo))
    return logo


# Pasos de mantenimiento
PASOS = [
    ("clock", "Sincronizar el reloj",
     "Un reloj desfasado rompe la validación de certificados (apt, Flathub…).", True, "apt"),
    ("repos", "Configurar repositorios oficiales",
     "En Debian habilita contrib/non-free; en Ubuntu LTS habilita universe/restricted/multiverse.", True, "apt"),
    ("tools", "Instalar herramientas auxiliares",
     "Fastfetch y soporte FUSE para AppImage, si faltan.", True, "apt"),
    ("backports-kernel-mesa", "Instalar kernel y Mesa desde Backports",
     "Instala el kernel y los controladores gráficos Mesa de Debian Backports; puede requerir reinicio.",
     False, "apt"),
    ("revertir-backports", "Volver a kernel y Mesa Stable",
     "Prepara la versión Stable, simula APT y conserva el kernel Backports. Requiere elegir Stable en GRUB tras reiniciar.",
     False, "apt"),
    ("nvidia-driver", "Detectar e instalar controlador NVIDIA",
     "En Debian analiza la GPU, el kernel, DKMS y Secure Boot. En portátiles híbridos mantiene PRIME bajo demanda; requiere confirmación.",
     False, "apt"),
    ("ubuntu-hwe", "Instalar kernel HWE oficial de Ubuntu",
     "Instala el metapaquete HWE de Ubuntu LTS solo si está disponible en los repositorios oficiales; puede requerir reinicio.",
     False, "apt"),
    ("upgrade", "Actualizar los paquetes del sistema",
     "Actualiza con APT y admite dependencias nuevas. No elimina paquetes.", True, "apt"),
    ("autoremove", "Eliminar dependencias huérfanas",
     "apt-get autoremove; puede quitar paquetes que APT considera huérfanos.", False, "apt"),
    ("autopurge", "Purgar dependencias huérfanas",
     "Elimina dependencias sin uso y sus archivos de configuración del sistema.", False, "apt"),
    ("autoclean", "Limpiar la caché de paquetes obsoletos",
     "apt-get autoclean.", True, "apt"),
    ("flatpak-setup", "Instalar soporte Flatpak y añadir Flathub",
     "Flatpak no está instalado en este sistema.", False, "flatpak"),
    ("snap-update", "Actualizar aplicaciones Snap",
     "Actualiza los snaps instalados desde su tienda; no elimina revisiones antiguas.", True, "snap"),
    ("flatpak-update", "Actualizar aplicaciones Flatpak",
     "Actualiza las aplicaciones Flatpak instaladas; no elimina runtimes sin uso.", True, "flatpak"),
    ("gnome-plugin", "Plugin Flatpak para GNOME Software",
     "Permite gestionar apps Flatpak desde la tienda de GNOME.", False, "gnome"),
    ("ext-manager", "Extension Manager",
     "Instila gnome-shell-extension-manager para gestionar extensiones de GNOME Shell.", False, "gnome"),
    ("gnome-ext-appindicator", "AppIndicator y KStatusNotifierItem Support",
     "Muestra indicadores de bandeja y KStatusNotifierItem en el panel de GNOME.", False, "gnome"),
    ("gnome-ext-blur-shell", "Blur my Shell",
     "Añade desenfoque configurable al fondo de GNOME Shell.", False, "gnome"),
    ("gnome-ext-caffeine", "Caffeine",
     "Evita temporalmente que GNOME suspenda la sesión.", False, "gnome"),
    ("gnome-ext-clipboard-indicator", "Clipboard Indicator",
     "Añade un indicador y gestor del portapapeles.", False, "gnome"),
    ("gnome-ext-dash-to-dock", "Dash to Dock",
     "Convierte el dash de GNOME en un dock configurable.", False, "gnome"),
    ("gnome-ext-places-status", "Places Status Indicator",
     "Añade un acceso rápido a lugares del sistema.", False, "gnome"),
    ("gnome-ext-tiling-shell", "Tiling Shell",
     "Organiza las ventanas en mosaico desde GNOME Shell.", False, "gnome"),
    ("clean-apt", "Limpiar caché de APT",
     "Elimina los .deb descargados en /var/cache/apt/archives; no borra paquetes instalados.", False, "cleanup"),
    ("clean-trash", "Vaciar papelera del usuario",
     "Elimina el contenido de ~/.local/share/Trash. No toca archivos fuera de la papelera.", False, "cleanup"),
    ("clean-thumbnails", "Eliminar miniaturas antiguas",
     "Borra miniaturas de más de 7 días en ~/.cache/thumbnails; se regeneran al abrir archivos.", False, "cleanup"),
    ("clean-journal", "Limpiar registros del sistema",
     "Conserva los últimos 30 días del diario de systemd y elimina registros rotados más antiguos.", False, "cleanup"),
    ("clean-flatpak", "Eliminar Flatpak sin uso",
     "flatpak uninstall --unused para el sistema y el usuario; no elimina aplicaciones instaladas.", False, "cleanup"),
    ("clean-snap", "Eliminar revisiones antiguas de Snap",
     "Quita revisiones deshabilitadas y conserva la última revisión anterior de cada snap para poder volver atrás.", False, "cleanup"),
    ("rebootcheck", "Comprobar si hace falta reiniciar",
     "Revisa kernel y servicios críticos al terminar.", True, "final"),
]

GRUPOS = [
    ("apt", "Sistema (APT)"),
    ("flatpak", "Flatpak"),
    ("gnome", "GNOME"),
    ("cleanup", "Limpieza del sistema"),
    ("final", "Al terminar"),
]


# Apps recomendadas (abreviado para brevedad - completo en el original)
APPS_RECOMENDADAS = [
    {"id": "audacity", "name": "Audacity", "category": "Multimedia",
     "icon": "org.audacityteam.Audacity", "bundled_icon": "audacity.png",
     "fallback_icon": "audio-x-generic",
     "description": "Graba y edita audio con varias pistas y efectos.",
     "channels": [{"type": "deb", "package": "audacity", "command": "audacity"},
                  {"type": "flatpak", "app_id": "org.audacityteam.Audacity"}]},
    {"id": "btop", "name": "btop", "category": "Sistema",
     "icon": "btop", "bundled_icon": "btop.png",
     "fallback_icon": "utilities-system-monitor",
     "description": "Monitor de recursos en terminal con gráficos de CPU, memoria, disco y red.",
     "channels": [{"type": "deb", "package": "btop", "command": "btop"}]},
    {"id": "vlc", "name": "VLC", "category": "Multimedia",
     "icon": "vlc", "bundled_icon": "vlc.png",
     "fallback_icon": "multimedia-player",
     "description": "Reproductor multimedia para vídeos, música y transmisiones de red.",
     "channels": [{"type": "deb", "package": "vlc", "command": "vlc"},
                  {"type": "flatpak", "app_id": "org.videolan.VLC"}]},
    # ... (resto en constants.py original)
]

APLICACIONES_BACKUP = {
    "timeshift": {
        "name": "Timeshift", "package": "timeshift", "command": "timeshift-launcher",
        "icon": "timeshift", "bundled_icon": "timeshift.png",
        "fallback_icon": "drive-harddisk",
        "description": "Crea instantáneas de los archivos del sistema para restaurarlo tras una actualización fallida.",
        "prompt": "Timeshift no está instalado. ¿Quieres instalarlo desde los repositorios APT configurados?"},
    "deja-dup": {
        "name": "Respaldos (Déjà Dup)", "package": "deja-dup", "command": "deja-dup",
        "icon": "org.gnome.DejaDup", "bundled_icon": "deja-dup.png",
        "fallback_icon": "document-save",
        "description": "Crea copias de seguridad de las carpetas personales seleccionadas.",
        "prompt": "Respaldos (Déjà Dup) no está instalado. ¿Quieres instalarlo?"},
}


def nombre_icono_recomendada(app, tema=None):
    from gi.repository import Gtk
    tema = tema or Gtk.IconTheme.get_default()
    for nombre in (app["icon"], app["fallback_icon"], "application-x-executable"):
        if tema.has_icon(nombre):
            return nombre
    return "application-x-executable"


def icono_recomendada(app):
    from gi.repository import GdkPixbuf, GLib, Gtk
    if "bundled_icon" in app:
        ruta = os.path.join(RECOMMENDED_ICON_DIR, app["bundled_icon"])
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(ruta, 48, 48, True)
            return Gtk.Image.new_from_pixbuf(pixbuf)
        except GLib.Error as exc:
            print("No se pudo cargar el icono %s: %s" % (ruta, exc.message), file=sys.stderr)
    icono = Gtk.Image.new_from_icon_name(nombre_icono_recomendada(app), Gtk.IconSize.DIALOG)
    icono.set_pixel_size(48)
    return icono


# Ghostty
GHOSTTY_APPIMAGE_RELEASES = "https://github.com/pkgforge-dev/ghostty-appimage/releases"

def canales_ghostty(distribucion):
    sistema = distribucion.get("ID")
    version = distribucion.get("VERSION_ID", "")
    appimage = {"type": "appimage"}
    if sistema in ("debian", "ayusos"):
        return [appimage]
    if sistema == "ubuntu":
        if re.fullmatch(r"[0-9]{2,}\.[0-9]{2}", version) and tuple(map(int, version.split("."))) >= (26, 4):
            return [{"type": "deb", "package": "ghostty", "command": "ghostty"}, appimage]
        return [appimage]
    return []


# UI helpers
def etiqueta(texto, markup=False, dim=False, xalign=0.0):
    from gi.repository import Gtk
    texto = traducir(texto)
    lbl = Gtk.Label(xalign=xalign)
    if markup:
        lbl.set_markup(texto)
    else:
        lbl.set_text(texto)
    lbl.set_line_wrap(True)
    if dim:
        lbl.get_style_context().add_class("dim-label")
    return lbl


ESTILO_APLICACION = b"""
.aio-header-title { font-size: 1.05em; font-weight: 700; }
.aio-header-version { color: mix(@theme_fg_color, #279457, 0.66); font-weight: 700; }
button.aio-header-version-button { min-width: 0; min-height: 0; padding: 0 4px; margin: 0; }
.aio-header-system { font-size: 0.90em; }
.aio-page { background-color: shade(@theme_bg_color, 0.985); }
.aio-page frame.aio-card > border { border: 1px solid alpha(@theme_fg_color, 0.16); border-radius: 12px; background-color: @theme_base_color; }
.aio-page .aio-heading { font-size: 1.26em; font-weight: 700; }
.aio-page .aio-icon { color: @theme_fg_color; background-color: alpha(@theme_selected_bg_color, 0.14); border-radius: 8px; padding: 6px; }
.aio-page .aio-group { font-weight: 600; }
.aio-page .aio-light-icon-background { background-color: #f6f5f4; border-radius: 8px; }
.aio-page flowbox.aio-card-grid { background-color: transparent; }
.aio-page flowbox.aio-card-grid > flowboxchild { padding: 0; }
.aio-maintenance list.aio-tasks { background-color: transparent; }
.aio-maintenance list.aio-tasks row { padding: 2px 0; }
.aio-maintenance checkbutton.aio-task { border: 1px solid transparent; border-radius: 8px; padding: 7px 9px; }
.aio-maintenance checkbutton.aio-task.aio-selected { background-color: alpha(@theme_selected_bg_color, 0.10); border-color: alpha(@theme_selected_bg_color, 0.13); }
.aio-maintenance checkbutton.aio-task:hover { background-color: alpha(@theme_selected_bg_color, 0.17); }
.aio-maintenance checkbutton.aio-task label.aio-task-name { font-weight: 600; }
.aio-maintenance checkbutton.aio-task label.aio-task-detail { font-size: 0.90em; }
.aio-maintenance button.aio-run { font-weight: 700; }
"""

def cabecera_mantenimiento(texto, icono, clase="aio-heading"):
    from gi.repository import Gtk
    cabecera = Gtk.Box(spacing=9)
    imagen = Gtk.Image.new_from_icon_name(icono, Gtk.IconSize.BUTTON)
    imagen.get_style_context().add_class("aio-icon")
    cabecera.pack_start(imagen, False, False, 0)
    titulo = etiqueta(texto)
    titulo.get_style_context().add_class(clase)
    cabecera.pack_start(titulo, True, True, 0)
    return cabecera

def tarjeta_mantenimiento(espacio):
    from gi.repository import Gtk
    marco = Gtk.Frame()
    marco.get_style_context().add_class("aio-card")
    contenido = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=espacio)
    contenido.set_border_width(14)
    marco.add(contenido)
    return marco, contenido


# Helpers de autorización
def helper_mantenimiento():
    if es_flatpak() or os.environ.get("APPIMAGE") or os.environ.get("SNAP"):
        return HELPER_SISTEMA
    return HELPER

def usa_integracion_portable():
    return es_flatpak() or bool(os.environ.get("APPDIR"))

def helper_disponible(ruta):
    if es_flatpak():
        try:
            import subprocess
            return subprocess.run(
                comando_host("test", "-x", ruta),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    return os.path.isfile(ruta)

def comando_administrativo(operacion, helper, *argumentos):
    if autorizacion_sin_contrasena_activa():
        return comando_host("pkexec", HELPER_SISTEMA, operacion, *argumentos)
    return comando_host("pkexec", helper, *argumentos)

def comando_pkexec(helper, lang, *argumentos):
    if es_flatpak():
        return ["flatpak-spawn", "--host", "pkexec", helper, "--lang", lang, *argumentos]
    return ["pkexec", helper, "--lang", lang, *argumentos]

def helper_admite_autorizacion_sin_contrasena(ruta):
    contenido = leer_texto(ruta)
    if contenido is None:
        return False
    return ("--enable-passwordless" in contenido and "--disable-passwordless" in contenido)

def helper_admite_tarea(ruta, tarea):
    contenido = leer_texto(ruta)
    return contenido is not None and "[%s]=" % tarea in contenido

def _regla_passwordless_valida(contenido, username):
    return (('action.id === "%s"' % POLKIT_ACTION) in contenido
            and ('action.lookup("program") === "%s"' % HELPER_SISTEMA) in contenido
            and ("subject.user === %s" % json.dumps(username)) in contenido
            and "subject.local" in contenido and "subject.active" in contenido)


def _existe_en_anfitrion(ruta):
    if es_flatpak():
        try:
            import subprocess
            return subprocess.run(
                comando_host("test", "-e", ruta), stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=10,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    return os.path.exists(ruta)


def _directorio_legible_en_anfitrion(ruta):
    if es_flatpak():
        try:
            import subprocess
            return subprocess.run(
                comando_host("sh", "-c", 'test -r "$1" && test -x "$1"', "sh", ruta),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    return os.access(ruta, os.R_OK | os.X_OK)


def autorizacion_sin_contrasena_activa():
    uid = os.getuid()
    rule_path = os.path.join(POLKIT_RULES_DIR, "50-aiodebian-gui-%s.rules" % uid)
    marker_path = os.path.join(PASSWORDLESS_STATE_DIR, "%s.rules" % uid)
    try:
        username = pwd.getpwuid(uid).pw_name
    except (OSError, KeyError):
        return False

    contenido = leer_texto(rule_path)
    if contenido is not None:
        return _regla_passwordless_valida(contenido, username)

    # Debian deja rules.d en 0750 root:polkitd. El usuario no puede entrar a
    # comprobar el fichero, aunque polkitd sí lo lee. Si el directorio es
    # accesible y la regla no existe, no hay excepción; en caso contrario se
    # consulta la copia de estado que escribe el asistente privilegiado.
    if (not _existe_en_anfitrion(rule_path)
            and _directorio_legible_en_anfitrion(POLKIT_RULES_DIR)):
        return False
    marcador = leer_texto(marker_path)
    return marcador is not None and _regla_passwordless_valida(marcador, username)


def novedades_version(version):
    try:
        with open(NOTAS_VERSION, encoding="utf-8") as archivo:
            if archivo.readline().strip() == version:
                return archivo.read().strip()
    except (OSError, UnicodeError):
        pass
    return ""
