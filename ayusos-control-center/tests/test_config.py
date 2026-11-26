import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "package/usr/lib/aio-debian-gui/extensions"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "package/usr/lib/aio-debian-gui"))

from ayusos.aio_core import ayusos_config


class ConfigTests(unittest.TestCase):
    def test_toml_round_trip(self):
        config = ayusos_config.AyusOSConfig()
        config.apps.profile = "gaming"
        config.maintenance.tasks = ["upgrade", "clean-journal"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ayusos.conf"
            self.assertTrue(ayusos_config._save_toml_atomic(path, config.to_dict()))
            loaded = ayusos_config._load_toml(path)
        self.assertEqual(loaded["apps"]["profile"], "gaming")
        self.assertEqual(loaded["maintenance"]["tasks"], ["upgrade", "clean-journal"])
        self.assertIs(loaded["repos"]["contrib_nonfree"], True)


if __name__ == "__main__":
    unittest.main()
