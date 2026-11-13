"""Preferencias persistentes y validación fuera de GTK."""
import json
import os
import tempfile

def cargar_preferencias(ruta, defaults=None):
    PREFERENCIAS_DEFECTO = defaults or {'idioma': 'es', 'tema': 'claro', 'modo_simple': False}
    IDIOMAS = {'es','en','fr','zh'}
    TEMAS = {'claro','oscuro'}
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except FileNotFoundError:
        return PREFERENCIAS_DEFECTO.copy()
    if not isinstance(datos, dict):
        raise ValueError("El archivo de preferencias debe contener un objeto JSON.")
    preferencias = PREFERENCIAS_DEFECTO.copy()
    preferencias.update({clave: datos[clave] for clave in PREFERENCIAS_DEFECTO if clave in datos})
    if not isinstance(preferencias["idioma"], str) or preferencias["idioma"] not in IDIOMAS:
        raise ValueError("Idioma de interfaz no válido en las preferencias.")
    if not isinstance(preferencias["tema"], str) or preferencias["tema"] not in TEMAS:
        raise ValueError("Tema de interfaz no válido en las preferencias.")
    if type(preferencias["modo_simple"]) is not bool:
        raise ValueError("El modo simple de las preferencias debe ser verdadero o falso.")
    return preferencias


def guardar_preferencias(preferencias, ruta):
    directorio = os.path.dirname(ruta)
    os.makedirs(directorio, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(prefix=".preferences-", dir=directorio)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(preferencias, archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


