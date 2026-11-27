"""Componentes independientes de la interfaz gráfica de AiO Debian GUI."""

from .clock import solicitar_sincronizacion
from .constants import (
    APLICACIONES_BACKUP,
    APP_ICON_NAME,
    APPS_RECOMENDADAS,
    APT_BACKUP_FILENAME,
    APT_BACKUP_HELPER,
    APT_BACKUP_LIMIT,
    BACKUP_ICON_DIR,
    DEBIAN_LOGO,
    ESTILO_APLICACION,
    FASTFETCH_LAYOUT,
    GRUB_HELPER,
    GRUPOS,
    HELPER,
    HELPER_SISTEMA,
    HOMEPAGE,
    IDIOMA_ACTUAL,
    IDIOMAS,
    NOTAS_VERSION,
    PASOS,
    POLKIT_ACTION,
    PREFERENCIAS_DEFECTO,
    PRGNAME,
    RECOMMENDED_ICON_DIR,
    TEMAS,
    UBUNTU_LOGO,
    autorizacion_sin_contrasena_activa,
    cabecera_mantenimiento,
    canales_ghostty,
    cargar_preferencias,
    comando_administrativo,
    comando_host,
    comando_pkexec,
    datos_distribucion_anfitrion,
    distribucion_anfitrion,
    es_flatpak,
    etiqueta,
    formato_actualizacion,
    guardar_preferencias,
    helper_admite_autorizacion_sin_contrasena,
    helper_admite_tarea,
    helper_disponible,
    helper_mantenimiento,
    icono_recomendada,
    identidad_distribucion,
    imagen_logo_distribucion,
    leer_texto,
    logo_distribucion,
    nombre_icono_recomendada,
    novedades_version,
    paquete_instalado,
    ruta_preferencias,
    tarjeta_mantenimiento,
    traducir,
    traducir_detalle_diagnostico,
    usa_integracion_portable,
    version_app,
)
from .desktop_backup import LABELS, detect, restore, user_dirs
from .desktop_backup import read as desktop_read
from .desktop_backup import save as desktop_save
from .desktop_backup import snapshot as desktop_snapshot
from .desktop_backup import version as desktop_version
from .diagnostics import run_diagnostics
from .extensions import load_extensions
from .fastfetch import instalar_layout, restaurar_layout
from .gtk_appearance import aplicar_tema
from .gtk_scheduler import ControladorProgramacion as GtkControladorProgramacion
from .health_dashboard import create_health_dashboard
from .history import MAX_HISTORIAL, guardar_registro_mantenimiento, leer_historial, ruta_historial
from .host_integration import install_host, prepare_host
from .preflight import check as run_preflight
from .recommended_list import exportar, importar
from .translations import TRADUCCIONES
from .updates import obtener_release_actualizacion, version_numerica

__all__ = [
    "solicitar_sincronizacion", "MAX_HISTORIAL", "ruta_historial", "leer_historial",
    "guardar_registro_mantenimiento", "cargar_preferencias", "guardar_preferencias",
    "PREFERENCIAS_DEFECTO", "version_numerica", "obtener_release_actualizacion",
    "run_diagnostics", "run_preflight", "load_extensions",
    "prepare_host", "install_host", "detect", "restore", "desktop_version",
    "user_dirs", "desktop_read", "desktop_snapshot", "desktop_save", "LABELS",
    "exportar", "importar", "instalar_layout", "restaurar_layout",
    "aplicar_tema", "GtkControladorProgramacion", "create_health_dashboard",
    "TRADUCCIONES", "IDIOMA_ACTUAL", "PREFERENCIAS_DEFECTO", "IDIOMAS", "TEMAS",
    "PRGNAME", "APP_ICON_NAME", "POLKIT_ACTION", "HELPER", "HELPER_SISTEMA",
    "GRUB_HELPER", "APT_BACKUP_HELPER", "APT_BACKUP_FILENAME", "APT_BACKUP_LIMIT",
    "HOMEPAGE", "DEBIAN_LOGO", "UBUNTU_LOGO",
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
