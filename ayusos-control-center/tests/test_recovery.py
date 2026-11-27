import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "package/usr/lib/aio-debian-gui/extensions/ayusos"
sys.path.insert(0, str(EXTENSION.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "package/usr/lib/aio-debian-gui"))

from ayusos import extension, recovery
from ayusos.aio_core import ayusos_recovery


class RecoveryTests(unittest.TestCase):
    def test_recovery_parameter_requires_exact_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmdline = Path(tmp) / "cmdline"
            cmdline.write_text("root=UUID=test ayusos-recovery quiet\n", encoding="utf-8")
            self.assertTrue(ayusos_recovery.is_recovery_boot(str(cmdline)))
            cmdline.write_text("root=UUID=test no-ayusos-recovery quiet\n", encoding="utf-8")
            self.assertFalse(ayusos_recovery.is_recovery_boot(str(cmdline)))
            self.assertFalse(ayusos_recovery.is_recovery_boot(str(Path(tmp) / "missing")))

    def test_repair_runs_all_noninteractive_steps(self):
        results = [(True, "dpkg ok"), (False, "apt error"), (True, "update ok")]
        with patch.object(ayusos_recovery, "_run", side_effect=results) as run:
            ok, message = ayusos_recovery.repair_system()
        self.assertFalse(ok)
        self.assertIn("apt error", message)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args_list[0].args[0], ["dpkg", "--configure", "-a"])
        self.assertIn("--fix-broken", run.call_args_list[1].args[0])
        self.assertIn("APT::Update::Error-Mode=any", run.call_args_list[2].args[0])

    def test_regenerate_grub_uses_available_command(self):
        with patch.object(ayusos_recovery.shutil, "which", return_value="/usr/sbin/update-grub"), \
                patch.object(ayusos_recovery, "_run", return_value=(True, "ok")) as run:
            self.assertEqual(ayusos_recovery.regenerate_grub(), (True, "ok"))
        run.assert_called_once_with(["update-grub"], timeout=180)

        with patch.object(ayusos_recovery.shutil, "which", return_value=None):
            ok, message = ayusos_recovery.regenerate_grub()
        self.assertFalse(ok)
        self.assertIn("grub-mkconfig", message)

    def test_restore_validates_snapshot_identifier(self):
        with patch.object(ayusos_recovery.ayusos_snapshots, "restore_timeshift_snapshot",
                          return_value=(True, "restored")) as restore:
            self.assertEqual(
                ayusos_recovery.restore_snapshot("2026-11-26_21-05-13"),
                (True, "restored"),
            )
            restore.assert_called_once_with("2026-11-26_21-05-13")
        for invalid in ("", "-option", "../snapshot", "id with spaces"):
            ok, _ = ayusos_recovery.restore_snapshot(invalid)
            self.assertFalse(ok)

    def test_execute_diagnostics_and_snapshots(self):
        report = {"core": {"ok": True}, "_summary": {"passed": 1, "total": 1}}
        with patch.object(ayusos_recovery.ayusos_diagnostics, "run_full_diagnostics",
                          return_value=report):
            result = ayusos_recovery.execute("diagnostics")
        self.assertTrue(result["success"])
        self.assertEqual(result["diagnostics"], report)

        with patch.object(ayusos_recovery.ayusos_snapshots, "list_timeshift_snapshots",
                          return_value=[{"id": "snap"}]):
            result = ayusos_recovery.execute("snapshots")
        self.assertEqual(result["snapshots"], [{"id": "snap"}])

    def test_cli_rejects_non_root_and_bad_arguments(self):
        with patch.object(ayusos_recovery.os, "geteuid", return_value=1000), \
                redirect_stdout(StringIO()):
            self.assertEqual(ayusos_recovery.main(["repair"]), 1)
        with patch.object(ayusos_recovery.os, "geteuid", return_value=0), \
                redirect_stdout(StringIO()):
            self.assertEqual(ayusos_recovery.main(["restore"]), 2)
            self.assertEqual(ayusos_recovery.main(["unknown"]), 2)

    def test_gui_parses_last_json_line(self):
        payload = recovery._parse_payload('aviso del sistema\n{"success": true, "message": "ok"}\n')
        self.assertEqual(payload, {"success": True, "message": "ok"})
        self.assertEqual(recovery._parse_payload("sin json"), {})

    def test_recovery_boot_skips_onboarding(self):
        with patch.object(extension, "is_recovery_boot", return_value=True), \
                patch.object(extension, "should_launch_onboarding") as onboarding:
            self.assertFalse(extension.Extension().should_launch_onboarding())
            onboarding.assert_not_called()

    def test_timeshift_restore_is_noninteractive(self):
        result = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        with patch.object(ayusos_recovery.ayusos_snapshots, "is_timeshift_installed",
                          return_value=True), \
                patch.object(ayusos_recovery.ayusos_snapshots.subprocess, "run",
                             return_value=result) as run:
            self.assertEqual(
                ayusos_recovery.ayusos_snapshots.restore_timeshift_snapshot("snap-1"),
                (True, "ok"),
            )
        command = run.call_args.args[0]
        self.assertIn("--restore", command)
        self.assertIn("--scripted", command)
        self.assertIn("--yes", command)
        self.assertIs(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_recovery_autostart_and_services_are_conditional(self):
        package = ROOT / "package"
        session = package / "usr/local/libexec/ayusos-recovery-session"
        desktop = package / "etc/xdg/autostart/ayusos-recovery.desktop"
        self.assertIn("ayusos-recovery", session.read_text(encoding="utf-8"))
        self.assertIn("Exec=/usr/local/libexec/ayusos-recovery-session",
                      desktop.read_text(encoding="utf-8"))
        self.assertIn("NoDisplay=true", desktop.read_text(encoding="utf-8"))
        for service in (
            "ayusos-onboarding.service",
            "ayusos-aio-inicial.service",
            "ayusos-aio-autorizacion.service",
            "ayusos-snapshot-inicial.service",
        ):
            content = (package / "etc/systemd/system" / service).read_text(encoding="utf-8")
            self.assertIn("ConditionKernelCommandLine=!ayusos-recovery", content)
        control = (package / "DEBIAN/control").read_text(encoding="utf-8")
        self.assertNotIn("grub-btrfsd", control)

    def test_privileged_entrypoint_and_policy_are_packaged(self):
        wrapper = EXTENSION / "ayusos-recovery"
        policy = ROOT / "package/usr/share/polkit-1/actions/es.aiodebian.gui.recovery.policy"
        self.assertTrue(wrapper.is_file())
        self.assertIn("ayusos_recovery", wrapper.read_text(encoding="utf-8"))
        self.assertIn(str(wrapper).split("extensions/", 1)[1], policy.read_text(encoding="utf-8"))
        build = (ROOT / "build-deb.sh").read_text(encoding="utf-8")
        self.assertIn('extensions/ayusos/ayusos-recovery"', build)


if __name__ == "__main__":
    unittest.main()
