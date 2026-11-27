import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "package/usr/lib/aio-debian-gui/extensions"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "package/usr/lib/aio-debian-gui"))

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
        self.assertEqual(payload["tasks"], ["upgrade", "clean-journal"])

    def test_disabled_maintenance(self):
        config = json.loads(json.dumps(app.SYSTEM_DEFAULTS))
        config["maintenance"]["schedule"] = "disabled"
        with patch.object(app, "run", return_value=Result()) as run:
            app.apply_maintenance(config, 1000, False)
        payload = json.loads(run.call_args.args[0][-1])
        self.assertFalse(payload["enabled"])

    def test_apps_filters_unavailable_packages(self):
        config = json.loads(json.dumps(app.SYSTEM_DEFAULTS))
        config["apps"]["profile"] = "development"

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

    def test_kernel_mapping(self):
        config = json.loads(json.dumps(app.SYSTEM_DEFAULTS))
        config["kernel"]["variant"] = "backports"
        with patch.object(app, "helper", return_value=Result()) as helper:
            app.apply_kernel(config, 1000, False)
        helper.assert_called_once_with(["backports-kernel-mesa"], 1000)


if __name__ == "__main__":
    unittest.main()
