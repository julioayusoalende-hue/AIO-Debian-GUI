#!/usr/bin/env python3
"""Exercise GRUB settings against an isolated boot/configuration fixture."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch


helper_path = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui/aio-grub-settings"
loader = importlib.machinery.SourceFileLoader("grub_settings", str(helper_path))
spec = importlib.util.spec_from_loader(loader.name, loader)
grub = importlib.util.module_from_spec(spec)
loader.exec_module(grub)


class BootSettingsTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.defaults = Path(directory) / "grub"
        self.defaults.write_text("GRUB_TIMEOUT=5\nGRUB_CMDLINE_LINUX_DEFAULT='quiet'\n")
        self.config = Path(directory) / "grub.cfg"
        self.config.write_text(
            "menuentry 'Debian GNU/Linux' $menuentry_id_option 'gnulinux-simple-disk' {\n"
            "}\n"
            "submenu 'Opciones avanzadas' $menuentry_id_option 'gnulinux-advanced-disk' {\n"
            "\tmenuentry 'Debian, con Linux 6.12' --id=linux-6.12 {\n"
            "\t}\n"
            "}\n"
            "if [ x = x ]; then\n"
            "  menuentry 'Windows Boot Manager' --id 'osprober-efi-disk' {\n"
            "  }\n"
            "fi\n"
        )
        self.fragment = self.defaults.with_name("grub.d") / grub.DROP_IN
        self.regenerate = Mock()

    def manage(self, action, request=None):
        return grub.manage(self.defaults, self.config, self.regenerate, action, request)

    def test_effective_boot_settings_without_aio_overrides(self):
        header = (
            'set default="${next_entry}"\n'
            'set default="1>0"\n'
            'set timeout=30\n'
            'set timeout_style=hidden\n'
            'set timeout=0\n'
            '### END /etc/grub.d/00_header ###\n'
        )
        config = header + self.config.read_text()
        self.config.write_text(config)
        status = self.manage("status")
        self.assertEqual(status["settings"], {})
        self.assertEqual(status["effective"], {
            "GRUB_DEFAULT": "gnulinux-advanced-disk>linux-6.12",
            "GRUB_TIMEOUT": "0",
            "GRUB_TIMEOUT_STYLE": "hidden",
        })
        self.config.write_text(config.replace('default="1>0"', 'default="${saved_entry}"'))
        with patch.object(grub, "grub_environment", return_value={"saved_entry": "osprober-efi-disk"}):
            self.assertEqual(self.manage("status")["effective"]["GRUB_DEFAULT"], "osprober-efi-disk")
        self.config.write_text(config + (
            '### BEGIN /etc/grub.d/30_os-prober ###\n'
            'set timeout_style=menu\nif [ "${timeout}" = 0 ]; then\n'
            '  set timeout=10\nfi\n### END /etc/grub.d/30_os-prober ###\n'
        ))
        effective = self.manage("status")["effective"]
        self.assertEqual((effective["GRUB_TIMEOUT"], effective["GRUB_TIMEOUT_STYLE"]), ("10", "menu"))

    def test_apply_and_restore(self):
        old_defaults = self.defaults.read_text()
        status = self.manage("status")
        entries = status["entries"]
        self.assertEqual([entry["id"] for entry in entries],
                         ["gnulinux-simple-disk", "gnulinux-advanced-disk>linux-6.12",
                          "osprober-efi-disk"])
        self.assertEqual(entries[1]["title"], "Opciones avanzadas › Debian, con Linux 6.12")
        settings = {"GRUB_DEFAULT": entries[1]["id"], "GRUB_TIMEOUT": "-1",
                    "GRUB_TIMEOUT_STYLE": "menu"}
        updated = self.manage("apply", {"revision": status["revision"], "settings": settings})
        self.assertEqual(updated["settings"], settings)
        self.assertEqual(self.fragment.read_text(), grub.render(settings))
        self.assertEqual(self.defaults.read_text(), old_defaults)
        self.manage("apply", {"revision": updated["revision"], "settings": {}})
        self.assertFalse(self.fragment.exists())
        self.assertEqual(self.defaults.read_text(), old_defaults)
        self.assertEqual(self.regenerate.call_count, 2)

    def test_reject_invalid_request_without_mutation(self):
        revision = self.manage("status")["revision"]
        for settings in (
            {"GRUB_DEFAULT": "missing"},
            {"GRUB_DEFAULT": "';touch /tmp/invalid;#"},
            {"GRUB_TIMEOUT": "1\n"},
            {"GRUB_TIMEOUT_STYLE": "arbitrary"},
            {"OTHER_VARIABLE": "42"},
            [],
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.manage("apply", {"revision": revision, "settings": settings})
        with self.assertRaisesRegex(ValueError, "Reload"):
            self.manage("apply", {"revision": "stale", "settings": {"GRUB_TIMEOUT": "8"}})
        self.assertFalse(self.fragment.exists())
        self.regenerate.assert_not_called()

    def test_restore_previous_fragment_on_update_failure(self):
        initial = self.manage("status")
        self.regenerate.side_effect = subprocess.CalledProcessError(1, ["update-grub"], stderr="simulated failure")
        with self.assertRaisesRegex(ValueError, "Previous settings restored"):
            self.manage("apply", {"revision": initial["revision"], "settings": {"GRUB_TIMEOUT": "5"}})
        self.assertFalse(self.fragment.exists())
        self.fragment.write_text(grub.render({"GRUB_TIMEOUT": "10"}))
        before = self.manage("status")
        with self.assertRaisesRegex(ValueError, "simulated failure"):
            self.manage("apply", {"revision": before["revision"], "settings": {}})
        self.assertEqual(self.manage("status"), before)

    def test_validate_generated_menu_before_replacing_boot_configuration(self):
        original = self.config.read_text()

        def generate(argv, **_kwargs):
            Path(argv[-1]).write_text("menuentry 'Debian' --id=debian {\n}\n")

        with patch.object(grub.subprocess, "run", side_effect=generate):
            with self.assertRaisesRegex(ValueError, "selected entry is missing"):
                grub.regenerate(self.config, "missing")
            self.assertEqual(self.config.read_text(), original)
            grub.regenerate(self.config, "debian")
        self.assertIn("--id=debian", self.config.read_text())

    def test_decline_modified_fragment_and_missing_grub(self):
        self.fragment.parent.mkdir()
        # Sin esto, con umask 002 la carpeta queda en 0775 y el ayudante se
        # niega antes por permisos, así que la prueba no llegaba a comprobar
        # el fragmento modificado fuera de la aplicación.
        self.fragment.parent.chmod(0o755)
        self.fragment.write_text("GRUB_TIMEOUT=20\n")
        with self.assertRaisesRegex(ValueError, "modified outside"):
            self.manage("status")
        self.config.unlink()
        with self.assertRaisesRegex(ValueError, "generated GRUB"):
            self.manage("status")

    def test_fragment_is_read_last_and_legacy_is_migrated(self):
        self.assertGreater(grub.DROP_IN, "ayusos.cfg")
        directory = self.fragment.parent
        directory.mkdir()
        directory.chmod(0o755)
        legacy = directory / grub.LEGACY_DROP_IN
        legacy.write_text(grub.render({"GRUB_TIMEOUT": "2"}))
        status = self.manage("status")
        self.assertEqual(status["settings"], {"GRUB_TIMEOUT": "2"})
        self.assertTrue(status["legacy"])
        self.manage("apply", {"revision": status["revision"], "settings": {"GRUB_TIMEOUT": "2"}})
        self.assertFalse(legacy.exists())
        self.assertEqual(self.fragment.read_text(), grub.render({"GRUB_TIMEOUT": "2"}))
        self.regenerate.assert_called_once()

    def test_reports_overridden_values(self):
        directory = self.fragment.parent
        directory.mkdir()
        directory.chmod(0o755)
        self.fragment.write_text(grub.render({"GRUB_TIMEOUT": "2"}))
        self.config.write_text("set timeout_style=menu\nset timeout=5\n"
                               "### END /etc/grub.d/00_header ###\n" + self.config.read_text())
        self.assertEqual(self.manage("status")["overridden"], ["GRUB_TIMEOUT"])


if __name__ == "__main__":
    unittest.main()
