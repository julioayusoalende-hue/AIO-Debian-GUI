"""Historial privado de mantenimiento: sin dependencias gráficas."""
import datetime
import json
import os
import tempfile

from .scheduler import mensaje_error

MAX_HISTORIAL = 100


def registros_programados(informe):
    ejecuciones = informe.get("history")
    ejecuciones = list(ejecuciones) if isinstance(ejecuciones, list) else []
    ultima = informe.get("last_result")
    if isinstance(ultima, dict) and ultima.get("status") != "running":
        if not any(isinstance(e, dict) and e.get("started") == ultima.get("started")
                   for e in ejecuciones):
            ejecuciones.append(ultima)
    estados = {"success": "correcto", "error": "error", "blocked": "bloqueado",
               "skipped": "omitido", "interrupted": "interrumpido"}
    estados_tarea = {"success": "Completada", "error": "Error", "not-run": "No ejecutada"}
    registros = []
    for ejecucion in ejecuciones:
        if not isinstance(ejecucion, dict):
            continue
        fecha, tareas = ejecucion.get("started"), ejecucion.get("tasks")
        estado = ejecucion.get("status")
        if (not isinstance(fecha, str) or not isinstance(tareas, dict)
                or not isinstance(estado, str) or estado not in estados):
            continue
        errores = ejecucion.get("errors", {})
        registros.append({
            "fecha": fecha, "origen": "Programada", "tareas": list(tareas),
            "resultado": estados[estado], "mensaje": ejecucion.get("detail", ""),
            "reinicio_recomendado": bool(ejecucion.get("reboot_required")),
            "detalles": {
                tarea: {"estado": estados_tarea.get(valor, "Sin datos"),
                        "mensaje": errores.get(tarea, "") if isinstance(errores, dict) else ""}
                for tarea, valor in tareas.items() if isinstance(valor, str)
            },
        })
    return registros

def tareas_fallidas(registro, disponibles):
    detalles = registro.get("detalles")
    if not isinstance(detalles, dict):
        return []
    return list(dict.fromkeys(
        tarea for tarea in registro["tareas"]
        if isinstance(tarea, str) and tarea in disponibles
        and isinstance(detalles.get(tarea), dict)
        and detalles[tarea].get("estado") == "Error"
    ))


def referencia(registro):
    return {"fecha": registro["fecha"], "origen": registro.get("origen", "Manual")}


def flatpak_del_sistema(registro):
    return (registro.get("origen") == "Programada"
            or registro.get("flatpak_sistema") is True
            or registro["tareas"] != ["flatpak-update"])


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
                                   formato="desarrollo", version="desarrollo", detalles=None, mensaje="",
                                   reintento_de=None, flatpak_sistema=False):
    ruta = ruta or ruta_historial()
    registros = leer_historial(ruta)
    registro = {
        "fecha": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "formato": formato,
        "version": version,
        "tareas": [str(t) for t in tareas][:40],
        "resultado": resultado,
        "reinicio_recomendado": bool(reinicio),
    }
    if reintento_de is not None:
        registro["reintento_de"] = reintento_de
    if flatpak_sistema:
        registro["flatpak_sistema"] = True
    if detalles is not None:
        registro["detalles"] = detalles
    if mensaje:
        registro["mensaje"] = mensaje_error(mensaje)
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

