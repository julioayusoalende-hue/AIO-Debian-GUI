import base64
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "package/usr/lib/aio-debian-gui/extensions"))
sys.path.insert(0, str(ROOT.parent / "package/usr/lib/aio-debian-gui"))

from ayusos import extension, pages
from ayusos.aio_core import (
    ayusos_branding as branding,
    ayusos_config as config,
    ayusos_diagnostics as diagnostics,
    ayusos_identity as identity,
    ayusos_onboarding_apply as apply,
    ayusos_recovery as recovery,
    ayusos_update as update,
    onboarding,
)


class DesktopIntegrationTests(unittest.TestCase):
    def test_red_accent_uses_the_session_setting(self):
        with patch.object(branding.subprocess, "run") as run:
            self.assertTrue(branding.set_accent_color("ayusos"))
        self.assertEqual(run.call_args.args[0][-2:], ["accent-color", "red"])
        self.assertEqual(branding.ACENTOS["ayusos"]["name"], "AyusOS Rojo")

    def test_installed_extensions_are_excluded_from_installation(self):
        request = {"gnome_extensions": {"enabled_by_default": [
            "gnome-ext-appindicator", "gnome-ext-caffeine",
        ]}}
        with patch.object(apply.pwd, "getpwuid", return_value=SimpleNamespace(pw_dir="/home/prueba")), \
             patch.object(apply, "installed_gnome_tasks", return_value={"gnome-ext-appindicator"}), \
             patch.object(apply, "helper", return_value=(None, False)) as helper:
            apply.apply_extensions(request, 1000, False)
        helper.assert_called_once_with(["gnome-ext-caffeine"], 1000)

    def test_user_metadata_is_recognized_even_for_disabled_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gnome-shell/extensions/caffeine@patapon.info"
            path.mkdir(parents=True)
            (path / "metadata.json").write_text("{}")
            self.assertIn("gnome-ext-caffeine", config.installed_gnome_tasks(tmp))

    def test_wizard_only_displays_missing_extensions(self):
        from gi.repository import Gtk

        if not Gtk.init_check([])[0]:
            self.skipTest("GTK sin pantalla")
        wizard = SimpleNamespace(config=config.AyusOSConfig())
        installed = {"gnome-ext-appindicator", "gnome-ext-blur-shell", "gnome-ext-caffeine",
                     "gnome-ext-dash-to-dock"}
        with patch.object(onboarding, "installed_gnome_tasks", return_value=installed):
            page = onboarding.OnboardingWizard._create_gnome_ext_step(wizard)
        self.assertEqual(list(wizard.ext_checks), ["gnome-ext-tiling-shell"])
        page.destroy()

    def test_wizard_saves_flathub_without_offering_app_profiles(self):
        from gi.repository import Gtk

        if not Gtk.init_check([])[0]:
            self.skipTest("GTK sin pantalla")
        settings = config.AyusOSConfig()
        settings.apps.auto_install = True
        settings.flatpak.flathub = False
        with patch.object(onboarding, "get_effective_config", return_value=settings), \
             patch.object(onboarding, "load_user_preferences", return_value={}), \
             patch.object(onboarding, "mark_onboarding_done", return_value=True) as save:
            wizard = onboarding.OnboardingWizard()
            try:
                steps = [step.id for step in wizard.steps]
                self.assertNotIn("apps", steps)
                wizard._show_step(steps.index("flatpak"))
                wizard.flatpak_enabled.set_active(True)
                wizard.flathub_enabled.set_active(True)
                wizard.btn_next.clicked()
                wizard._show_step(len(steps) - 1)
                wizard.btn_next.clicked()
                saved = save.call_args.args[1]
                self.assertTrue(saved["flatpak"]["flathub"])
                self.assertFalse(saved["apps"]["auto_install"])
            finally:
                wizard.destroy()

    def test_flatpak_without_flathub_does_not_configure_remote(self):
        with patch.object(apply, "run", return_value=Mock(returncode=0)) as run, \
             patch.object(apply, "helper") as helper:
            apply.apply_flatpak({"flatpak": {"enabled": True, "flathub": False}}, 1000, False)
        helper.assert_not_called()
        self.assertEqual(run.call_args.args[0], ["apt-get", "install", "-y", "--no-remove", "flatpak"])

    def test_flathub_diagnostic_checks_exact_remote_name(self):
        with patch.object(diagnostics, "paquete_instalado", return_value=True), \
             patch.object(diagnostics.subprocess, "run") as run:
            run.return_value = Mock(returncode=0, stdout="flathub-beta\n")
            self.assertFalse(diagnostics.check_flatpak_flathub()[0])
            run.return_value.stdout += "flathub\n"
            self.assertTrue(diagnostics.check_flatpak_flathub()[0])
        self.assertEqual(run.call_args.args[0], ["flatpak", "remotes", "--columns=name"])

    def test_snapshot_diagnostic_uses_the_same_list_as_the_tab(self):
        with patch.object(diagnostics, "paquete_instalado", return_value=True), \
             patch("ayusos.aio_core.ayusos_snapshots.list_timeshift_snapshots",
                   return_value=[{"id": "2026-11-27_12-30-00"}]), \
             patch.object(diagnostics.time, "time",
                          return_value=diagnostics.time.mktime((2026, 11, 27, 13, 0, 0, 4, 331, -1))):
            self.assertTrue(diagnostics.check_snapshots_recent()[0])

    def test_missing_repo_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(update, "AYUSOS_REPO_SOURCES", Path(tmp) / "absent"):
            status = json.loads(update.cli_check_updates())
        self.assertIn("error", status)

    def test_recommended_filter_can_be_enabled_and_cleared(self):
        addon = extension.Extension()
        window = Mock()
        addon._on_perfil_changed(SimpleNamespace(get_active_id=lambda: "ayusos"), window)
        app_id = next(iter(addon.ayusos_apps()))
        self.assertTrue(window.recommended_extra_filter(app_id))
        addon._on_perfil_changed(SimpleNamespace(get_active_id=lambda: ""), window)
        self.assertIsNone(window.recommended_extra_filter)
        window._filtrar_recomendadas.assert_called_with(window.recommended_search, window.recommended_empty)

    def test_failed_wallpaper_is_not_reported_as_success(self):
        window = Mock()
        pages.AyusOSPagesMixin._branding_wallpaper_done(window, True, {"success": False})
        self.assertEqual(window.branding_status.set_text.call_args.args[0], "No se pudo aplicar el fondo.")

    def test_identity_rejects_changed_keyring_before_writing_timeshift(self):
        with tempfile.TemporaryDirectory() as tmp:
            keyring = Path(tmp) / "keyring"
            keyring.write_bytes(b"installed")
            timeshift = Path(tmp) / "timeshift.json"
            archive = {identity.TIMESHIFT_ENTRY: (b'{"schedule_daily":"true"}', 0),
                       "apt/ayusos-archive.gpg": (b"changed", 0)}
            with patch.object(identity, "AYUSOS_KEYRING", keyring), \
                 patch.object(identity, "TIMESHIFT_CONFIG", timeshift), \
                 patch.object(identity.os, "geteuid", return_value=0):
                with self.assertRaises(ValueError):
                    identity.restore_system_identity(archive)
                self.assertFalse(timeshift.exists())
                archive["apt/ayusos-archive.gpg"] = (b"installed", 0)
                identity.restore_system_identity(archive)
            self.assertEqual(json.loads(timeshift.read_text()), {"schedule_daily": "true"})
            self.assertEqual(keyring.read_bytes(), b"installed")

    def test_identity_helper_restores_from_validated_archive_on_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "identity.zip"
            identity.save_identity(path, {identity.TIMESHIFT_ENTRY: (b'{"count_daily":"5"}', 0)})
            encoded = base64.b64encode(path.read_bytes())
            timeshift = Path(tmp) / "timeshift.json"
            stdin = SimpleNamespace(buffer=io.BytesIO(encoded))
            with patch.object(recovery.os, "geteuid", return_value=0), \
                 patch.object(identity, "TIMESHIFT_CONFIG", timeshift), \
                 patch.object(sys, "stdin", stdin), patch("builtins.print") as printed:
                self.assertEqual(recovery.main(["identity-restore"]), 0)
            self.assertEqual(json.loads(printed.call_args.args[0]), {"success": True})
            self.assertEqual(json.loads(timeshift.read_text()), {"count_daily": "5"})

    def test_plymouth_restores_config_if_initramfs_update_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "plymouthd.conf"
            previous = "[Daemon]\nTheme=ceratopsian\n"
            conf.write_text(previous)
            with patch.object(branding, "PLYMOUTH_CONF", conf), \
                 patch.object(branding.os, "geteuid", return_value=0), \
                 patch.object(branding, "available_plymouth_themes", return_value=["details"]), \
                 patch.object(branding.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "update-initramfs")):
                with self.assertRaises(subprocess.CalledProcessError):
                    branding.set_plymouth_theme("details")
            self.assertEqual(conf.read_text(), previous)

    def test_identity_restores_dconf_in_the_user_session(self):
        contents = {"dconf/extensions": (b"[example]\nkey=1\n", 0)}
        identity.validate_identity(contents)
        with patch.object(identity.os, "geteuid", return_value=1000), patch.object(identity, "_run") as run:
            identity.restore_user_identity(contents)
        run.assert_called_once_with(["dconf", "load", identity.DCONF_AYUSOS_EXTENSIONS],
                                    data=contents["dconf/extensions"][0])
