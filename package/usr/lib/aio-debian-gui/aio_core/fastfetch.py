"""Apply the bundled Fastfetch layout to the current user's configuration."""

from pathlib import Path
from tempfile import NamedTemporaryFile


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
    with NamedTemporaryFile(dir=destino.parent, prefix=".fastfetch-", delete=False) as archivo:
        temporal = Path(archivo.name)
        try:
            archivo.write(contenido)
            archivo.close()
            temporal.replace(destino)
        finally:
            temporal.unlink(missing_ok=True)
    return copia
