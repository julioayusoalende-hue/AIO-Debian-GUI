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

    def test_completion_survives_missing_preferences_for_the_original_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "onboarding-done"
            marker.touch()
            (marker.parent / "aio-usuarios").write_text("1000\n1001\n", encoding="ascii")
            with patch.object(ayusos_config, "MARKER_ONBOARDING_DONE", marker), \
                 patch.object(ayusos_config, "load_system_config", return_value={}), \
                 patch.object(ayusos_config, "load_user_preferences", return_value={}), \
                 patch.object(ayusos_config.os, "getuid", return_value=1000) as uid:
                self.assertTrue(ayusos_config.is_onboarding_completed())
                marker.with_name("onboarding-uid").write_text("1001\n", encoding="ascii")
                self.assertFalse(ayusos_config.is_onboarding_completed())
                uid.return_value = 1001
                self.assertTrue(ayusos_config.is_onboarding_completed())
                marker.unlink()
                self.assertFalse(ayusos_config.is_onboarding_completed())

    def test_save_handles_unwritable_config_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "file"
            directory.touch()
            with patch.object(ayusos_config, "USER_CONFIG_DIR", directory):
                self.assertFalse(ayusos_config.save_user_preferences({}))


if __name__ == "__main__":
    unittest.main()
