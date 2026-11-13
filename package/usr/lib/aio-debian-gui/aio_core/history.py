"""Historial privado de mantenimiento: sin dependencias gráficas."""
import datetime
import json
import os
import tempfile

MAX_HISTORIAL = 100
def ruta_historial(estado_dir=None):
    estado_dir = estado_dir or os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(estado_dir, "aio-debian-gui", "history.json")

def leer_historial(ruta=None):
    ruta = ruta or ruta_historial()
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if not isinstance(datos, list):
            return []
        return [v for v in datos[-MAX_HISTORIAL:] if
                isinstance(v, dict) and isinstance(v.get("fecha"), str)
                and isinstance(v.get("tareas"), list) and isinstance(v.get("resultado"), str)]
    except (OSError, ValueError, TypeError):
        return []

def guardar_registro_mantenimiento(tareas, resultado, reinicio=False, ruta=None,
                                   formato="desarrollo", version="desarrollo"):
    ruta = ruta or ruta_historial()
    registros = leer_historial(ruta)
    registro = {
        "fecha": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "formato": formato,
        "version": version,
        "tareas": [str(t) for t in tareas][:40],
        "resultado": resultado,
        "reinicio_recomendado": bool(reinicio),
    }
    registros.append(registro)
    directorio = os.path.dirname(ruta)
    os.makedirs(directorio, mode=0o700, exist_ok=True)
    fd, temporal = tempfile.mkstemp(prefix=".history-", dir=directorio)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as archivo:
            json.dump(registros[-MAX_HISTORIAL:], archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")
            archivo.flush()
            os.fsync(archivo.fileno())
        os.chmod(temporal, 0o600)
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)

