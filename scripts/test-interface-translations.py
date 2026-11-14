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
    "Último índice de paquetes: hace %d días.",
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
    assert det("Último índice de paquetes: hace 0 días.") != "Último índice de paquetes: hace 0 días."
    assert det("Instalada: 2.0.8. Al día según los índices APT locales.") != "Instalada: 2.0.8. Al día según los índices APT locales."
    assert det("Instalada: 2.0.8. Disponible en APT: 2.0.9.") != "Instalada: 2.0.8. Disponible en APT: 2.0.9."
    assert det("Módulos DKMS inexistentes.") == "Módulos DKMS inexistentes."
print("✔ Traducciones de interfaz y diagnóstico (en, fr, zh) completas en casos críticos")
