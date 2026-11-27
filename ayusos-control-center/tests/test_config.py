import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "package/usr/lib/aio-debian-gui/extensions"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "package/usr/lib/aio-debian-gui"))

from ayusos.aio_core import ayusos_config, onboarding


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

    def test_finish_saves_choices_and_completion_together(self):
        config = ayusos_config.AyusOSConfig()
        config.maintenance.schedule = "disabled"
        wizard = type("Wizard", (), {"version": "1.4"})()
        with patch.object(onboarding, "load_user_preferences", return_value={"tema": "sistema"}), \
             patch.object(ayusos_config, "save_user_preferences", return_value=False) as save:
            self.assertFalse(onboarding.OnboardingWizard._apply_finish(wizard, None, config))
        save.assert_called_once()
        prefs = save.call_args.args[0]
        self.assertEqual(prefs["maintenance"]["schedule"], "disabled")
        self.assertEqual(prefs["onboarding"], {"completed": True, "version": "1.4"})
        self.assertEqual(prefs["tema"], "sistema")

    def test_save_handles_unwritable_config_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "file"
            directory.touch()
            with patch.object(ayusos_config, "USER_CONFIG_DIR", directory):
                self.assertFalse(ayusos_config.save_user_preferences({}))


if __name__ == "__main__":
    unittest.main()
