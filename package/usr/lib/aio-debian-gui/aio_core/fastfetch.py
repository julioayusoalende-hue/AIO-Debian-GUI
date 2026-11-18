"""Apply and restore the current user's Fastfetch configuration."""

from pathlib import Path
from tempfile import NamedTemporaryFile


def _escribir(ruta, contenido):
    with NamedTemporaryFile(dir=ruta.parent, prefix=".fastfetch-", delete=False) as archivo:
        temporal = Path(archivo.name)
        try:
            archivo.write(contenido)
            archivo.close()
            temporal.replace(ruta)
        finally:
            temporal.unlink(missing_ok=True)


def instalar_layout(origen, directorio_config):
    contenido = Path(origen).read_bytes()
    ruta_config = Path(directorio_config) / "fastfetch" / "config.jsonc"
    ruta_config.parent.mkdir(parents=True, exist_ok=True)
    destino = ruta_config.resolve()
    try:
        anterior = destino.read_bytes()
    except FileNotFoundError:
        anterior = None
    if anterior == contenido:
        return None

    copia = None
    if anterior is not None:
        with NamedTemporaryFile(dir=ruta_config.parent, prefix="config.jsonc.",
                                suffix=".bak", delete=False) as respaldo:
            copia = Path(respaldo.name)
            try:
                respaldo.write(anterior)
                respaldo.flush()
            except OSError:
                copia.unlink(missing_ok=True)
                raise
    marcador = ruta_config.with_name(".aio-fastfetch-original")
    _escribir(marcador, copia.name.encode("utf-8") if copia else b"")
    _escribir(destino, contenido)
    return copia


def restaurar_layout(origen, directorio_config):
    ruta_config = Path(directorio_config) / "fastfetch" / "config.jsonc"
    destino = ruta_config.resolve()
    try:
        activo = destino.read_bytes()
    except FileNotFoundError:
        return False
    if activo != Path(origen).read_bytes():
        return False

    marcador = ruta_config.with_name(".aio-fastfetch-original")
    try:
        nombre = marcador.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Las versiones anteriores solo guardaban la copia de seguridad.
        copias = ruta_config.parent.glob("config.jsonc.*.bak")
        copia = max(copias, key=lambda ruta: ruta.stat().st_mtime_ns, default=None)
    else:
        if nombre and (Path(nombre).name != nombre or not
                       (nombre.startswith("config.jsonc.") and nombre.endswith(".bak"))):
            raise ValueError("Copia de Fastfetch no válida.")
        copia = ruta_config.with_name(nombre) if nombre else None

    if copia is None:
        destino.unlink()
    else:
        _escribir(destino, copia.read_bytes())
    marcador.unlink(missing_ok=True)
    return True
