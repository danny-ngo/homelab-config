import runpy
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = runpy.run_path(str(ROOT / 'ansible/roles/infra_host/files/homelab-battery-policy'))


class BatteryPolicyTests(unittest.TestCase):
    def check(self, online, capacities, missing=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ac = root / 'AC'
            ac.mkdir()
            (ac / 'type').write_text('Mains')
            (ac / 'online').write_text(str(online))
            for index, capacity in enumerate(capacities):
                battery = root / f'BAT{index}'
                battery.mkdir()
                for name, value in {
                    'type': 'Battery', 'capacity': str(capacity),
                    'status': 'Discharging', 'charge_control_start_threshold': '95',
                    'charge_control_end_threshold': '100',
                }.items():
                    (battery / name).write_text(value)
            if missing:
                (root / 'BAT0' / 'capacity').unlink()
            shutdowns = []
            POLICY['maintain_power'](root, lambda: shutdowns.append(True))
            for battery in root.glob('BAT*'):
                self.assertEqual((battery / 'charge_control_start_threshold').read_text(), '75\n')
                self.assertEqual((battery / 'charge_control_end_threshold').read_text(), '80\n')
            return shutdowns

    def test_shutdown_only_when_all_batteries_low_without_ac(self):
        self.assertTrue(self.check(0, [5, 10]))
        self.assertFalse(self.check(1, [5, 10]))
        self.assertFalse(self.check(0, [5, 60]))
        self.assertFalse(self.check(0, []))

    def test_incomplete_or_invalid_readings_prevent_shutdown(self):
        self.assertFalse(self.check(0, [5], missing=True))
        self.assertFalse(self.check(0, ['unknown']))
        self.assertFalse(self.check(0, [-1]))
        self.assertFalse(self.check('unknown', [5]))
