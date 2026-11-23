"""Componentes independientes de la interfaz gráfica de AiO Debian GUI."""

# Re-exportar funciones principales para compatibilidad
from .clock import sincronizar
from .history import (
    MAX_HISTORIAL, ruta_historial, leer_historial, guardar_registro_mantenimiento
)
from .preferences import (
    cargar_preferencias, guardar_preferencias
)
from .updates import version_numerica, obtener_release_actualizacion
from .diagnostics import run_diagnostics
from .preflight import check as run_preflight
from .host_integration import prepare_host, install_host
from .desktop_backup import (
    detect, restore, version as desktop_version, user_dirs,
    read as desktop_read, snapshot as desktop_snapshot, save as desktop_save, LABELS
)
from .recommended_list import exportar, importar
from .fastfetch import instalar_layout, restaurar_layout
from .gtk_appearance import aplicar_tema
from .gtk_scheduler import ControladorProgramacion as GtkControladorProgramacion
from .health_dashboard import create_health_dashboard
from .translations import TRADUCCIONES

# Constantes y utilidades compartidas
from .constants import (
    PRGNAME, APP_ICON_NAME, POLKIT_ACTION, HELPER, HELPER_SISTEMA,
    GRUB_HELPER, APT_BACKUP_HELPER, APT_BACKUP_FILENAME, APT_BACKUP_LIMIT,
    HOMEPAGE, DEBIAN_LOGO, UBUNTU_LOGO, AYUSOS_LOGO, NOMBRE_AYUSOS,
    FASTFETCH_LAYOUT, NOTAS_VERSION, RECOMMENDED_ICON_DIR, BACKUP_ICON_DIR,
    IDIOMA_ACTUAL, PREFERENCIAS_DEFECTO, IDIOMAS, TEMAS,
    traducir, traducir_detalle_diagnostico,
    MAX_HISTORIAL as _MAX_HISTORIAL, ruta_historial as _ruta_historial,
    leer_historial as _leer_historial, guardar_registro_mantenimiento as _guardar_registro,
    ruta_preferencias, cargar_preferencias, guardar_preferencias,
    es_flatpak, comando_host, leer_texto, paquete_instalado,
    version_app, formato_actualizacion, datos_distribucion_anfitrion,
    distribucion_anfitrion, identidad_distribucion, logo_distribucion,
    imagen_logo_distribucion, PASOS, GRUPOS, APPS_RECOMENDADAS,
    APLICACIONES_BACKUP, nombre_icono_recomendada, icono_recomendada,
    canales_ghostty, etiqueta, ESTILO_APLICACION, cabecera_mantenimiento,
    tarjeta_mantenimiento, helper_mantenimiento, usa_integracion_portable,
    helper_disponible, comando_administrativo, comando_pkexec,
    helper_admite_autorizacion_sin_contrasena, helper_admite_tarea,
    autorizacion_sin_contrasena_activa, novedades_version,
)

__all__ = [
    "sincronizar", "MAX_HISTORIAL", "ruta_historial", "leer_historial",
    "guardar_registro_mantenimiento", "cargar_preferencias", "guardar_preferencias",
    "PREFERENCIAS_DEFECTO", "version_numerica", "obtener_release_actualizacion",
    "run_diagnostics", "run_preflight", "ControladorProgramacion",
    "prepare_host", "install_host", "detect", "restore", "desktop_version",
    "user_dirs", "desktop_read", "desktop_snapshot", "desktop_save", "LABELS",
    "exportar", "importar", "instalar_layout", "restaurar_layout",
    "aplicar_tema", "GtkControladorProgramacion", "create_health_dashboard",
    "TRADUCCIONES", "IDIOMA_ACTUAL", "PREFERENCIAS_DEFECTO", "IDIOMAS", "TEMAS",
    # Constants
    "PRGNAME", "APP_ICON_NAME", "POLKIT_ACTION", "HELPER", "HELPER_SISTEMA",
    "GRUB_HELPER", "APT_BACKUP_HELPER", "APT_BACKUP_FILENAME", "APT_BACKUP_LIMIT",
    "HOMEPAGE", "DEBIAN_LOGO", "UBUNTU_LOGO", "AYUSOS_LOGO", "NOMBRE_AYUSOS",
    "FASTFETCH_LAYOUT", "NOTAS_VERSION", "RECOMMENDED_ICON_DIR", "BACKUP_ICON_DIR",
    "traducir", "traducir_detalle_diagnostico", "novedades_version",
    "ruta_historial", "leer_historial", "guardar_registro_mantenimiento",
    "ruta_preferencias", "cargar_preferencias", "guardar_preferencias",
    "es_flatpak", "comando_host", "leer_texto", "paquete_instalado",
    "version_app", "formato_actualizacion", "datos_distribucion_anfitrion",
    "distribucion_anfitrion", "identidad_distribucion", "logo_distribucion",
    "imagen_logo_distribucion", "PASOS", "GRUPOS", "APPS_RECOMENDADAS",
    "APLICACIONES_BACKUP", "nombre_icono_recomendada", "icono_recomendada",
    "canales_ghostty", "etiqueta", "ESTILO_APLICACION", "cabecera_mantenimiento",
    "tarjeta_mantenimiento", "helper_mantenimiento", "usa_integracion_portable",
    "helper_disponible", "comando_administrativo", "comando_pkexec",
    "helper_admite_autorizacion_sin_contrasena", "helper_admite_tarea",
    "autorizacion_sin_contrasena_activa",
]