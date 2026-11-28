import base64
import io
import json
import socket
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
    onboarding_nvidia,
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
             patch.object(onboarding, "mark_onboarding_done", return_value=True) as save, \
             patch.object(onboarding.OnboardingWizard, "_comprobar_conexion"):
            wizard = onboarding.OnboardingWizard()
            try:
                wizard._resultado_conexion(True)
                steps = [step.id for step in wizard.steps]
                self.assertNotIn("apps", steps)
                wizard._show_step(steps.index("flatpak"))
                wizard.flatpak_enabled.set_active(True)
                wizard.flathub_enabled.set_active(True)
                wizard.btn_next.clicked()
                wizard._show_step(steps.index("nvidia"))
                wizard.nvidia_combo.set_active_id("manual")
                wizard.btn_next.clicked()
                wizard._show_step(len(steps) - 1)
                with patch.object(wizard, "_begin_initial_update") as update, \
                     patch.object(wizard, "_install_nvidia") as install:
                    wizard.btn_next.clicked()
                update.assert_called_once_with()
                install.assert_not_called()
                save.assert_not_called()
                wizard.nvidia_outcome = "Controlador verificado"
                wizard._finish_onboarding()
                saved = save.call_args.args[1]
                self.assertTrue(saved["flatpak"]["flathub"])
                self.assertFalse(saved["apps"]["auto_install"])
                self.assertEqual(saved["nvidia"]["mode"], "manual")
                self.assertTrue(saved["nvidia"]["handled_by_wizard"])
            finally:
                wizard.destroy()

    def test_nvidia_worker_reports_success_and_failure(self):
        wizard = SimpleNamespace(
            config=config.AyusOSConfig(), system_onboarding=False,
        )
        wizard._run_helper = onboarding.OnboardingWizard._run_helper.__get__(wizard)
        report = subprocess.CompletedProcess([], 0, stdout="##NVIDIA:present:1\n", stderr="")
        cases = (
            (0, ["[*] Compilando DKMS", "##RESULT:nvidia-driver:0", "##REBOOT:1"],
             "preparado correctamente", True),
            (1, ["[-] Secure Boot activo", "##RESULT:nvidia-driver:1"], "Secure Boot activo", False),
        )
        for code, output, message, reboot in cases:
            complete, log = Mock(), Mock()
            with self.subTest(output=output), \
                 patch.object(onboarding.subprocess, "run", return_value=report), \
                 patch.object(onboarding.subprocess, "Popen") as popen:
                process = popen.return_value.__enter__.return_value
                process.stdout = iter(output)
                process.wait.return_value = code
                onboarding.OnboardingWizard._nvidia_worker(wizard, log, complete)
                self.assertEqual(popen.call_args.args[0][-2:], ["repos", "nvidia-driver"])
                result, requires_reboot = complete.call_args.args
                self.assertIn(message, result)
                self.assertEqual(requires_reboot, reboot)
                for line in output:
                    if not line.startswith("##"):
                        log.assert_any_call(line)

    def test_system_nvidia_channel_runs_only_one_fixed_request(self):
        wizard = Mock(stdout=iter([
            "texto cualquiera\n", "##AYUSOS-NVIDIA:update\n",
            "##AYUSOS-NVIDIA:driver:1\n", "##AYUSOS-NVIDIA:driver:0\n",
        ]))
        wizard.wait.return_value = 0
        helper = Mock(stdout=iter(["[*] Instalando NVIDIA\n", "##RESULT:nvidia-driver:0\n"]))
        helper.wait.return_value = 0
        update_helper = Mock(stdout=iter(["##RESULT:onboarding-check-upgrade:0\n"]))
        update_helper.wait.return_value = 0
        processes = [Mock(), Mock(), Mock()]
        for context, process in zip(processes, (wizard, update_helper, helper)):
            context.__enter__ = Mock(return_value=process)
            context.__exit__ = Mock(return_value=False)
        with patch.object(onboarding_nvidia.os, "geteuid", return_value=0), \
             patch.object(onboarding_nvidia.subprocess, "Popen", side_effect=processes) as popen:
            self.assertEqual(onboarding_nvidia.run_session(1000, ["wizard"]), 0)
        self.assertEqual(popen.call_count, 3)
        self.assertEqual(popen.call_args_list[1].args[0][-2:], ["upgrade", "onboarding-check-upgrade"])
        self.assertEqual(popen.call_args.args[0][-2:], ["repos", "nvidia-driver"])
        self.assertEqual(popen.call_args.kwargs["env"]["PKEXEC_UID"], "1000")
        wizard.stdin.write.assert_any_call("##RESULT:nvidia-driver:0\n")
        wizard.stdin.write.assert_any_call("##AYUSOS-NVIDIA-EXIT:0\n")
        wizard.stdin.write.assert_any_call("##AYUSOS-NVIDIA-EXIT:2\n")

    def test_update_checkpoint_keeps_nvidia_pending_until_a_different_boot(self):
        from gi.repository import Gtk

        if not Gtk.init_check([])[0]:
            self.skipTest("GTK sin pantalla")
        settings = config.AyusOSConfig()
        settings.nvidia.mode = "manual"
        settings.onboarding.initial_update = "running"
        with patch.object(onboarding, "get_effective_config", return_value=settings), \
             patch.object(onboarding.OnboardingWizard, "_comprobar_conexion"), \
             patch.object(onboarding, "load_user_preferences", return_value={}), \
             patch.object(onboarding, "save_user_preferences", return_value=True) as save:
            wizard = onboarding.OnboardingWizard()
            try:
                complete = Mock()

                def update(operation, steps, _log, progress):
                    self.assertEqual(operation, "update")
                    self.assertEqual(steps, ("upgrade", "onboarding-check-upgrade"))
                    progress("##RESULT:onboarding-check-upgrade:0")
                    progress("##REBOOT:1")
                    return 0

                with patch.object(onboarding, "BOOT_ID") as boot, \
                     patch.object(wizard, "_run_helper", side_effect=update), \
                     patch.object(onboarding.GLib, "idle_add", side_effect=lambda callback: callback()), \
                     patch.object(onboarding.Gtk, "MessageDialog") as dialog, \
                     patch.object(wizard, "_install_nvidia") as install:
                    boot.read_text.return_value = "boot-original"
                    wizard._update_worker(Mock(), complete)
                    saved = save.call_args.args[0]
                    self.assertEqual(saved["onboarding"]["initial_update"], "reboot:boot-original")
                    self.assertFalse(saved["onboarding"]["completed"])
                    self.assertEqual(saved["nvidia"]["mode"], "manual")
                    self.assertTrue(complete.call_args.args[1])
                    wizard.config = config.AyusOSConfig.from_dict(saved)
                    dialog.return_value.run.return_value = Gtk.ResponseType.CLOSE
                    wizard._continue_after_update()
                    install.assert_not_called()
                    boot.read_text.return_value = "boot-nuevo"
                    wizard._continue_after_update()
                    install.assert_not_called()
                    self.assertEqual(wizard.config.onboarding.initial_update, "reboot:boot-original")
                    dialog.return_value.run.return_value = Gtk.ResponseType.OK
                    wizard._continue_after_update()
                    install.assert_called_once_with()
            finally:
                wizard.destroy()

    def test_nvidia_dialog_is_modal_and_offers_reboot_after_success(self):
        from gi.repository import GLib, Gtk

        if not Gtk.init_check([])[0]:
            self.skipTest("GTK sin pantalla")

        def worker(_wizard, log, complete):
            log("[*] Compilando DKMS")
            complete("Controlador preparado correctamente", True)

        with patch.object(onboarding.OnboardingWizard, "_comprobar_conexion"), \
             patch.object(onboarding.OnboardingWizard, "_nvidia_worker", worker):
            wizard = onboarding.OnboardingWizard()
            try:
                with patch.object(wizard, "_finish_onboarding") as finish:
                    wizard._install_nvidia()
                    dialog = next(win for win in Gtk.Window.list_toplevels()
                                  if isinstance(win, Gtk.Dialog) and win.get_transient_for() is wizard)
                    self.assertTrue(dialog.get_modal())
                    self.assertFalse(dialog.get_deletable())
                    self.assertIsNone(dialog.get_widget_for_response(Gtk.ResponseType.YES))
                    while not dialog.get_deletable():
                        GLib.MainContext.default().iteration(True)
                    self.assertIsNotNone(dialog.get_widget_for_response(Gtk.ResponseType.YES))
                    dialog.response(Gtk.ResponseType.YES)
                    self.assertTrue(wizard.reboot_nvidia)
                    finish.assert_called_once_with()
            finally:
                wizard.destroy()

    def test_wizard_blocks_navigation_until_debian_is_reachable(self):
        from gi.repository import Gtk

        if not Gtk.init_check([])[0]:
            self.skipTest("GTK sin pantalla")
        with patch.object(onboarding.OnboardingWizard, "_comprobar_conexion") as check, \
             patch.object(onboarding, "mark_onboarding_done") as save:
            wizard = onboarding.OnboardingWizard()
            try:
                check.assert_called_once()
                self.assertFalse(wizard.btn_next.get_sensitive())
                self.assertFalse(wizard.btn_skip.get_sensitive())
                wizard.btn_next.clicked()
                wizard.btn_skip.clicked()
                self.assertEqual(wizard.current_index, 0)
                save.assert_not_called()
                wizard._resultado_conexion(False)
                self.assertEqual(wizard.aviso_conexion.get_message_type(), Gtk.MessageType.WARNING)
                self.assertIn("Comprueba tu conexión", wizard.estado_conexion.get_text())
                wizard._resultado_conexion(True)
                self.assertEqual(wizard.aviso_conexion.get_message_type(), Gtk.MessageType.INFO)
                self.assertTrue(wizard.btn_next.get_sensitive())
                wizard.btn_next.clicked()
                self.assertEqual(wizard.current_index, 1)
                wizard._resultado_conexion(False)
                self.assertEqual(wizard.aviso_conexion.get_message_type(), Gtk.MessageType.WARNING)
                wizard.btn_next.clicked()
                self.assertEqual(wizard.current_index, 1)
            finally:
                wizard.destroy()

    def test_internet_check_rejects_portal_and_transport_failure(self):
        for header, expected in ((b"-----BEGIN PGP SIGNED MESSAGE-----\n", True),
                                 (b"<html>Login</html>", False)):
            with patch.object(onboarding, "urlopen", return_value=io.BytesIO(header)) as request:
                self.assertIs(onboarding.repositorio_accesible(), expected)
                self.assertEqual(request.call_args.kwargs["timeout"], 4)
        with patch.object(onboarding, "urlopen", side_effect=TimeoutError()):
            self.assertFalse(onboarding.repositorio_accesible())

    def test_first_login_uses_the_active_session_and_applies_its_preferences(self):
        package = ROOT / "package"
        with tempfile.TemporaryDirectory() as tmp, socket.socket(socket.AF_UNIX) as bus:
            root = Path(tmp)
            state = root / "state"
            runtime = root / "runtime" / "1001"
            state.mkdir()
            runtime.mkdir(parents=True)
            bus.bind(str(runtime / "bus"))
            (state / "aio-usuarios").write_text("1000\n1001\n")
            launcher = root / "launcher"
            launcher.write_text((package / "usr/bin/ayusos-onboarding-graphical").read_text()
                                .replace("/var/lib/ayusos", str(state))
                                .replace("/run/user", str(runtime.parent))
                                .replace("/usr/bin/python3 -I", "python3 -I"))
            started = subprocess.run(["bash", "-c", """
                loginctl() {
                    case "$1:$2" in
                        list-sessions:*) printf 'c1 1000 primero seat0\nc2 1001 segundo seat0\n';;
                        show-session:c1) printf 'User=1000\nActive=no\nRemote=no\n';;
                        show-session:c2)
                            if [[ "$*" == *"-p User"* ]]; then
                                printf 'User=1001\nName=segundo\nActive=yes\nRemote=no\nType=x11\nDisplay=:2\n'
                            fi;;
                    esac
                }
                getent() { printf 'segundo:x:1001:1001:Prueba:%s:/bin/bash\n' "$HOME_TEST"; }
                runuser() {
                    [ "$2" = segundo ] || return 1
                    if [[ "$*" == *show-environment* ]]; then printf 'DISPLAY=:8\n'; return; fi
                    [[ "$*" == *"DISPLAY=:8"* && "$*" == *"--onboarding-only"* ]] || return 1
                }
                python3() {
                    [[ "$3" == onboarding_nvidia && "$4" == 1001 && "$5" == /usr/sbin/runuser ]] || return 1
                    shift 5
                    [[ "$*" == *AYUSOS_ONBOARDING_SERVICE=1* ]] || return 1
                    runuser "$@"
                }
                export HOME_TEST="$2"
                source "$1"
            """.replace("$HOME_TEST", "$HOME_TEST"), "_", str(launcher), tmp],
                capture_output=True, text=True, timeout=5)
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assertEqual((state / "onboarding-uid").read_text(), "1001\n")
            self.assertTrue((state / "onboarding-done").exists())

            schedules = root / "schedules"
            schedules.mkdir()
            applicator = root / "apply"
            applicator.write_text(
                "#!/bin/bash\n"
                f'printf "%s\\n" "$1" > "{root / "applied-uid"}"\n'
                f"""echo '{{"enabled": false}}' > "{schedules}/$1.json"\n"""
            )
            applicator.chmod(0o755)
            initial = root / "initial"
            initial.write_text((package / "usr/local/libexec/ayusos-aio-inicial").read_text()
                               .replace("/var/lib/ayusos", str(state))
                               .replace("/etc/aio-debian-gui/schedules", str(schedules))
                               .replace("/usr/local/libexec/ayusos-aplicar-onboarding", str(applicator)))
            applied = subprocess.run(["bash", str(initial)], capture_output=True, text=True, timeout=5)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual((root / "applied-uid").read_text(), "1001\n")

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
