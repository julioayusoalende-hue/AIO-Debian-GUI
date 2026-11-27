import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "package/usr/lib/aio-debian-gui/extensions"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "package/usr/lib/aio-debian-gui"))

import gi

gi.require_version("Gtk", "3.0")
from ayusos.recovery import open_recovery
from gi.repository import Gtk


class RecoveryUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Gtk.init_check([])[0]:
            raise unittest.SkipTest("Sin pantalla: pruebas GTK omitidas")

    def setUp(self):
        self.parent = Gtk.Window()
        self.parent._iniciar_operacion = lambda _name: "token"
        self.finalizadas = []
        self.parent._finalizar_operacion = self.finalizadas.append

    def tearDown(self):
        window = getattr(self.parent, "recovery_window", None)
        if window is not None:
            window.destroy()
        self.parent.destroy()

    def test_window_actions_snapshots_diagnostics_and_terminal(self):
        window = open_recovery(self.parent)
        self.assertIs(self.parent.recovery_window, window)
        self.assertTrue(window.get_visible())
        self.assertIn("repair", window.buttons)
        self.assertIn("grub", window.buttons)
        self.assertIn("diagnostics", window.buttons)
        self.assertIn("terminal", window.buttons)

        window._action_done(
            "snapshots", 0,
            json.dumps({"success": True, "snapshots": [
                {"id": "snap-1", "date": "2026-11-26", "comment": "Antes de cambios"}
            ]}),
            "",
        )
        self.assertEqual(window.snapshot_store.get_value(window.snapshot_store.get_iter_first(), 0), "snap-1")

        report = {
            "core": {"ok": True, "details": "correcto"},
            "apt": {"ok": False, "message": "revisar"},
            "_summary": {"passed": 1, "total": 2},
        }
        window._action_done("diagnostics", 0, json.dumps({
            "success": True, "diagnostics": report,
        }), "")
        self.assertEqual(window.diagnostics_store.iter_n_children(None), 2)
        self.assertIn("1/2", window.status.get_text())

        with patch("ayusos.recovery.subprocess.Popen") as popen:
            window.buttons["terminal"].clicked()
        popen.assert_called_once()
        self.assertIn("gnome-terminal", popen.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
