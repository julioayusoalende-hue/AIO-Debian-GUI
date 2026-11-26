"""Carga genérica de extensiones para aio-debian-gui.

Una extensión vive en <directorio>/<nombre>/ y exporta una clase Extension
en extension.py (o __init__.py). El core no conoce nombres de distribuciones.
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path


def extensions_dir() -> Path:
    """Directorio de extensiones; permite pruebas con AIO_EXTENSIONS_DIR."""
    override = os.environ.get("AIO_EXTENSIONS_DIR")
    if override:
        return Path(override)
    core = Path(__file__).resolve()
    # <prefix>/lib/aio-debian-gui/aio_core/extensions.py
    return core.parent.parent / "extensions"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(path.parent)]
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_extensions():
    """Devuelve instancias de Extension disponibles, en orden alfabético."""
    root = extensions_dir()
    if not root.is_dir():
        return []

    extensions = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith((".", "__")):
            continue
        init_file = entry / "__init__.py"
        extension_file = entry / "extension.py"
        try:
            if extension_file.is_file():
                module = _load_module(f"aio_extension_{entry.name}", extension_file)
            elif init_file.is_file():
                module = _load_module(f"aio_extension_{entry.name}", init_file)
            else:
                continue
            factory = getattr(module, "Extension", None)
            if factory is None:
                raise AttributeError("no exporta Extension")
            extensions.append(factory())
        except Exception as exc:  # noqa: BLE001
            print(f"No se pudo cargar la extensión {entry.name}: {exc}", file=sys.stderr)
    return extensions
