import runpy
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = runpy.run_path(str(ROOT / 'ansible/roles/infra_host/files/homelab-battery-policy'))


class BatteryPolicyTests(unittest.TestCase):
    def check(self, online, capacities, missing=False, expected_thresholds=None):
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
                start, end = (battery / 'charge_control_start_threshold', battery / 'charge_control_end_threshold')
                if expected_thresholds:
                    self.assertEqual((start.read_text(), end.read_text()), expected_thresholds)
            return shutdowns

    def test_shutdown_only_when_all_batteries_low_without_ac(self):
        for online, capacities, expected_shutdown in (
            (0, [5, 10], True), (1, [5, 10], False), (0, [5, 60], False), (0, [], False),
        ):
            shutdowns = self.check(online, capacities, expected_thresholds=('75\n', '80\n'))
            self.assertEqual(bool(shutdowns), expected_shutdown)

    def test_incomplete_or_invalid_readings_prevent_shutdown(self):
        for online, capacities, missing, expected_thresholds in (
            (0, [5], True, ('95', '100')),
            (0, ['unknown'], False, ('95', '100')),
            (0, [-1], False, ('75\n', '80\n')),
            ('unknown', [5], False, ('95', '100')),
        ):
            shutdowns = self.check(online, capacities, missing, expected_thresholds)
            self.assertFalse(shutdowns)
