import json
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "package/usr/lib/aio-debian-gui/extensions"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "package/usr/lib/aio-debian-gui"))

from aio_core.scheduler import validate_config
from ayusos.aio_core import ayusos_onboarding_apply as app


class Result:
    def __init__(self, code=0, stdout="", stderr=""):
        self.returncode = code
        self.stdout = stdout
        self.stderr = stderr


class OnboardingApplyTests(unittest.TestCase):
    def test_merge_preserves_defaults(self):
        merged = app._merge(app.SYSTEM_DEFAULTS, {"apps": {"profile": "gaming"}})
        self.assertEqual(merged["apps"]["profile"], "gaming")
        self.assertEqual(merged["maintenance"]["schedule"], "weekly")

    def test_maintenance_uses_selected_schedule(self):
        config = json.loads(json.dumps(app.SYSTEM_DEFAULTS))
        config["maintenance"] = {
            "schedule": "monthly", "time": "23:45",
            "tasks": ["upgrade", "clean-journal"],
        }
        with patch.object(app, "run", return_value=Result()) as run:
            app.apply_maintenance(config, 1000, False)
        cmd = run.call_args.args[0]
        payload = json.loads(cmd[-1])
        self.assertEqual(payload["enabled"], True)
        self.assertEqual(payload["frequency"], "monthly")
        self.assertEqual(payload["hour"], 23)
        self.assertEqual(payload["minute"], 45)
        self.assertEqual(validate_config(payload)["tasks"], ["upgrade"])

    def test_disabled_maintenance(self):
        config = json.loads(json.dumps(app.SYSTEM_DEFAULTS))
        config["maintenance"]["schedule"] = "disabled"
        config["maintenance"]["tasks"] = ["clean-journal"]
        with patch.object(app, "run", return_value=Result()) as run:
            app.apply_maintenance(config, 1000, False)
        payload = json.loads(run.call_args.args[0][-1])
        self.assertFalse(validate_config(payload)["enabled"])

    def test_partial_failure_is_reported_to_the_service(self):
        with ExitStack() as stack:
            for option in ("repos", "flatpak", "kernel", "nvidia", "apps", "extensions", "appearance"):
                stack.enter_context(patch.object(app, f"apply_{option}", return_value=(None, False)))
            stack.enter_context(patch.object(app, "apply_maintenance", return_value=(Result(1), False)))
            stack.enter_context(patch.object(app, "helper", return_value=(Result(), False)))
            self.assertEqual(app.apply({}, "prueba", 1000), 1)

    def test_apps_filters_unavailable_packages(self):
        config = json.loads(json.dumps(app.SYSTEM_DEFAULTS))
        config["apps"] = {"profile": "development", "auto_install": True}

        def fake_run(cmd, **kwargs):
            if cmd[0] == "apt-cache":
                return Result(0 if cmd[2] == "git" else 1)
            return Result()

        with patch.object(app, "run", side_effect=fake_run) as run:
            app.apply_apps(config, 1000, False)
        install_cmd = run.call_args.args[0]
        self.assertEqual(install_cmd[0], "apt-get")
        self.assertIn("git", install_cmd)
        self.assertNotIn("code", install_cmd)

    def test_nvidia_runs_selected_driver_without_dkms_deadline(self):
        for mode in ("auto", "manual"):
            config = app._merge(app.SYSTEM_DEFAULTS, {"nvidia": {"mode": mode}})
            with self.subTest(mode=mode), \
                 patch.object(app, "run", return_value=Result(stdout="##NVIDIA:present:1\n")) as run, \
                 patch.object(app, "notify_nvidia"), \
                 patch.object(app, "helper", return_value=(Result(), True)) as helper:
                self.assertTrue(app.apply_nvidia(config, 1000, False)[1])
            run.assert_called_once_with([app.HELPER, "--nvidia-report"], timeout=15)
            helper.assert_called_once_with(["nvidia-driver"], 1000, timeout=None)

    def test_automatic_nvidia_skips_machine_without_nvidia(self):
        with patch.object(app, "run", return_value=Result(stdout="##NVIDIA:present:0\n")), \
             patch.object(app, "helper") as helper:
            self.assertEqual(app.apply_nvidia(app.SYSTEM_DEFAULTS, 1000, False), (None, False))
        helper.assert_not_called()

    def test_kernel_mapping(self):
        config = json.loads(json.dumps(app.SYSTEM_DEFAULTS))
        config["kernel"]["variant"] = "backports"
        with patch.object(app, "helper", return_value=Result()) as helper:
            app.apply_kernel(config, 1000, False)
        helper.assert_called_once_with(["backports-kernel-mesa"], 1000)


if __name__ == "__main__":
    unittest.main()
