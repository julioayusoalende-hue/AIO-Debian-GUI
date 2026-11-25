"""Format for sharing recommended app selections between installations."""

import json
import re

LIMITE = 64 * 1024
FORMATO = "aio-debian-gui.recommended-apps"


def exportar(seleccion):
    datos = {
        "format": FORMATO,
        "version": 1,
        "apps": [{"id": app, "channel": canal} for app, canal in sorted(seleccion.items())],
    }
    return (json.dumps(datos, indent=2) + "\n").encode("utf-8")


def importar(contenido):
    error = "El archivo no contiene una lista válida de Apps recomendadas."
    if len(contenido) > LIMITE:
        raise ValueError(error)
    try:
        datos = json.loads(contenido.decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise ValueError(error) from exc
    if (not isinstance(datos, dict) or datos.get("format") != FORMATO
            or type(datos.get("version")) is not int or datos["version"] != 1
            or not isinstance(datos.get("apps"), list) or not 0 < len(datos["apps"]) <= 250):
        raise ValueError(error)
    seleccion = {}
    for entrada in datos["apps"]:
        if not isinstance(entrada, dict) or set(entrada) != {"id", "channel"}:
            raise ValueError(error)
        app, canal = entrada["id"], entrada["channel"]
        if (not isinstance(app, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", app)
                or not isinstance(canal, str) or not re.fullmatch(r"[a-z0-9-]{1,24}", canal)
                or app in seleccion):
            raise ValueError(error)
        seleccion[app] = canal
    return seleccion
