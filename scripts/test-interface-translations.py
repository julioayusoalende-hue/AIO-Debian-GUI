#!/usr/bin/env python3
"""Pruebas de traducción de interfaz y diagnóstico sin abrir GTK."""
import ast
from pathlib import Path
import re

path = Path(__file__).resolve().parents[1] / "package/usr/bin/aio-debian-gui"
source = path.read_text(encoding="utf-8")
tree = ast.parse(source)
namespace = {"re": re}

# Ejecutar exclusivamente declaraciones del catálogo, sin importar Gtk ni
# ejecutar el programa completo.
for node in tree.body:
    if isinstance(node, ast.Assign):
        targets = node.targets
        if any(isinstance(t, ast.Name) and t.id == "TRADUCCIONES" for t in targets):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        elif any(isinstance(t, ast.Subscript) and
                 "TRADUCCIONES" in ast.unparse(t) for t in targets):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
          and isinstance(node.value.func, ast.Attribute)
          and node.value.func.attr == "update"
          and "TRADUCCIONES" in ast.unparse(node.value.func.value)):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    elif isinstance(node, ast.FunctionDef) and node.name in (
            "traducir", "traducir_detalle_diagnostico"):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)

essential = (
    "Programar mantenimiento", "Activar mantenimiento automático", "Guardar programación",
    "Eliminar programación", "Pausar", "Frecuencia", "Hora local", "Programación activa",
    "Próxima ejecución: %s", "Última ejecución: %s · %s",
    "Detalles técnicos", "No comprobado", "Sin incidencias",
    "Mantenimiento habitual", "Aplicaciones y repositorios",
    "Kernel y controladores · Avanzado", "Ejecutar 1 tarea", "Ejecutar %d tareas",
    "No hay tareas seleccionadas.", "Pendiente", "En curso", "Completada", "No ejecutada",
    "La comprobación de actualizaciones de AiO funciona también con APT en español.",
    "2.0.9 — Traducciones completas para los paneles y el diagnóstico preventivo.",
    "Por defecto Polkit solicita contraseña. Esta excepción es voluntaria y aumenta los riesgos de seguridad.",
    "<b>Salida de la consola</b>",
    "No se detectó una GPU NVIDIA PCI.",
    "Buscando GPU NVIDIA…",
    "Análisis de solo lectura. No instala, elimina ni repara paquetes. Las comprobaciones dependen del estado de los índices APT.",
    "Dependencias APT", "Módulos DKMS", "Servicios systemd",
    "No se detectaron paquetes parcialmente instalados.",
    "No hay una solicitud explícita de reinicio registrada.",
    "No hay versión candidata en los índices APT.",
    "%.1f GiB libres (%s del volumen)",
    "%d actualizaciones estimadas por APT%s.",
    "%d actualizaciones disponibles según los índices APT locales.",
    "No se pudo interpretar la lista de actualizaciones APT.",
    "Antes del diagnóstico se actualizarán los índices APT con autorización de administrador. No se instalarán ni eliminarán paquetes.",
    "Actualizando índices APT y analizando el sistema…",
    "No se pudieron actualizar los índices APT; los resultados pueden estar desactualizados.",
    "No se pudieron verificar las actualizaciones con índices APT actualizados.",
    "Guía de integración del anfitrión",
    "La integración instala el asistente, la política Polkit y el programador en el sistema anfitrión. La aplicación no ejecuta estos comandos por ti.",
    "Antes de actualizar, pausa las programaciones de todos los usuarios y espera a que terminen las tareas. Si el DEB está instalado, actualízalo con APT y no uses esta guía.",
    "1. Copia y ejecuta este bloque en una terminal del anfitrión. Anota el directorio mostrado y revisa los archivos extraídos.",
    "2. En la misma terminal, entra en ese directorio con cd. Copia el segundo bloque solo si confías en los archivos y autorizas su instalación como administrador.",
    "3. Reinicia AiO y actualiza el estado de la programación. Tras actualizar AiO, repite estos pasos con la misma versión.",
    "Copiar extracción", "Copiar instalación",
    "No se pudo determinar la ruta absoluta del AppImage.",
    "Para las notificaciones y la comprobación de reinicio, instala libnotify-bin y needrestart en el anfitrión.",
    "Los índices APT pueden estar desactualizados y ocultar actualizaciones del sistema o de AiO. Para renovarlos sin instalar paquetes, ejecuta «sudo apt update» y vuelve a diagnosticar.",
    "Último índice de paquetes: hace %d días.",
    "Crea instantáneas de los archivos del sistema para restaurarlo tras una actualización fallida u otro problema. Por defecto no incluye los archivos personales.",
    "Crea copias de seguridad de las carpetas personales seleccionadas para recuperar archivos perdidos o modificados. No restaura el sistema operativo.",
    "Apps recomendadas", "Aplicaciones recomendadas",
    "Abrir nueva sesión", "La sesión de terminal ha terminado.",
    "No se pudo iniciar la terminal.",
    "Fastfetch no está instalado; instala fastfetch para mostrar la información del sistema.",
    "Instalado", "No se pudo comprobar el estado de algunas aplicaciones.",
    "Catálogo alfabético de aplicaciones recomendadas con formatos DEB y Flatpak.",
    "Añade una terminal interactiva con Fastfetch al iniciar cuando está instalado.",
    "Incorpora iconos para Celluloid, GIMP, Spotify y VLC en las aplicaciones recomendadas.",
    "Corrige Video Downloader y muestra los formatos instalados sin abrir las aplicaciones automáticamente.",
    "Mejora los iconos de las aplicaciones recomendadas cuando falta el icono propio.",
    "Espera a que termine la operación de la aplicación antes de cerrar la ventana.",
    "Elige un formato por aplicación. Los paquetes DEB de los repositorios APT requieren autorización; Flatpak se instala solo para tu usuario y configura Flathub si hace falta.",
    "DEB (APT)", "DEB (web oficial)", "Flatpak",
    "Las páginas de descarga .deb son oficiales; revisa el paquete e instálalo con el gestor de software.",
    "¿Quieres instalar %s en formato %s?", "Comprobando %s…", "Instalando %s…",
    "Se abrió la página oficial para descargar el paquete .deb.",
    "No se pudo configurar Flathub para tu usuario. Comprueba que Flatpak y la conexión estén disponibles e inténtalo de nuevo.",
    "Reproductor de música para servidores Jellyfin, Navidrome y Subsonic.",
    "Convierte imágenes por lotes entre formatos y cambia su tamaño.",
    "Cliente de escritorio para reproducir contenido de tu biblioteca Plex.",
    "Aplicación de escritorio para escuchar música, pódcast y listas de reproducción.",
    "Descarga vídeos de sitios compatibles para verlos sin conexión.",
    "Convierte y comprime vídeos con ajustes para formatos y dispositivos comunes.",
    "Navegador web de Google. El paquete DEB se descarga desde la página oficial.",
    "Editor de imágenes para crear, retocar y componer gráficos y fotografías.",
    "Reproduce vídeos con mpv desde una interfaz GTK sencilla.",
    "Reproductor multimedia para vídeos, música y transmisiones de red.",
)
for lang in ("en", "fr", "zh"):
    dictionary = namespace["TRADUCCIONES"][lang]
    for key in essential:
        assert key in dictionary, f"Falta en {lang}: {key}"
        assert dictionary[key] != key, f"Sin traducir en {lang}: {key}"
    namespace["IDIOMA_ACTUAL"] = lang
    tr = namespace["traducir"]
    det = namespace["traducir_detalle_diagnostico"]
    assert det("753.0 GiB libres (84% del volumen)") != "753.0 GiB libres (84% del volumen)"
    assert det("0 actualizaciones estimadas por APT.") != "0 actualizaciones estimadas por APT."
    assert det("5 actualizaciones estimadas por APT; 2 retenidos.") != "5 actualizaciones estimadas por APT; 2 retenidos."
    assert det("2 actualizaciones disponibles según los índices APT locales.") != "2 actualizaciones disponibles según los índices APT locales."
    assert det("Último índice de paquetes: hace 0 días.") != "Último índice de paquetes: hace 0 días."
    assert det("Instalada: 2.0.8. Al día según los índices APT locales.") != "Instalada: 2.0.8. Al día según los índices APT locales."
    assert det("Instalada: 2.0.8. Disponible en APT: 2.0.9.") != "Instalada: 2.0.8. Disponible en APT: 2.0.9."
    assert det("Módulos DKMS inexistentes.") == "Módulos DKMS inexistentes."
print("✔ Traducciones de interfaz y diagnóstico (en, fr, zh) completas en casos críticos")
