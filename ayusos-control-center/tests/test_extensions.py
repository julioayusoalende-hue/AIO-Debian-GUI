import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = Path(__file__).resolve().parents[2] / "package/usr/lib/aio-debian-gui"
sys.path.insert(0, str(CORE))

from aio_core.extensions import load_extensions


class ExtensionLoaderTests(unittest.TestCase):
    def test_loads_simple_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "demo"
            entry.mkdir()
            (entry / "__init__.py").write_text(
                "class Extension:\n"
                "    name = 'demo'\n"
                "    def is_active(self):\n"
                "        return True\n"
            )
            with patch.dict(os.environ, {"AIO_EXTENSIONS_DIR": tmp}):
                extensions = load_extensions()
            self.assertEqual([e.name for e in extensions], ["demo"])

    def test_ignores_broken_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "broken"
            entry.mkdir()
            (entry / "__init__.py").write_text("raise RuntimeError('boom')\n")
            with patch.dict(os.environ, {"AIO_EXTENSIONS_DIR": tmp}):
                extensions = load_extensions()
            self.assertEqual(extensions, [])


from unittest.mock import patch

if __name__ == "__main__":
    unittest.main()
