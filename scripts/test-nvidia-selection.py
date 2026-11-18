#!/usr/bin/env python3
"""Selección sin hardware real, sin red y sin instalar controladores."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('nvidia', ROOT / 'package/usr/lib/aio-debian-gui/aio_core/nvidia.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Selection(unittest.TestCase):
    def setUp(self):
        self.devices = [dict(device=0x1234, subvendorid=0x10de, subdevid=1)]
        self.chips = [dict(devid='0x1234', features=['kernelopen'])]

    def test_branch_and_flavour(self):
        for version, expected in [('550.163.01-2', 'nvidia-kernel-dkms'),
                                  ('1:580.1-1', 'nvidia-open-kernel-dkms')]:
            self.assertEqual(module.select_module(self.chips, self.devices, version), expected)
        self.chips[0]['features'] = []
        self.assertEqual(module.select_module(self.chips, self.devices, '580.1-1'), 'nvidia-kernel-dkms')

    def test_unknown_legacy_and_mixed(self):
        for chips in [[], [dict(devid='0x1234', legacybranch='470.xx')]]:
            with self.assertRaises(ValueError):
                module.select_module(chips, self.devices, '580.1-1')
        with self.assertRaises(ValueError):
            module.select_module(self.chips, self.devices + [dict(device=0xffff, subvendorid=0, subdevid=0)], '580.1-1')
        with self.assertRaises(ValueError):
            module.select_module(self.chips, [], '580.1-1')

    def test_subsystem_specific_legacy_overrides_generic(self):
        self.chips.append(dict(devid='0x1234', subvendorid='0x10de', subdevid='0x0001', legacybranch='470.xx'))
        with self.assertRaises(ValueError):
            module.select_module(self.chips, self.devices, '580.1-1')

if __name__ == '__main__':
    unittest.main()
