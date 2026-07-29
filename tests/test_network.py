import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NETWORK_PLUGIN = ROOT / "ansible" / "filter_plugins" / "network.py"
SPEC = importlib.util.spec_from_file_location("homelab_network", NETWORK_PLUGIN)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load filter plugin from {NETWORK_PLUGIN}")
NETWORK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NETWORK)

cidr_overlaps = NETWORK.cidr_overlaps
cidr_prefix = NETWORK.cidr_prefix
cidr_valid = NETWORK.cidr_valid


class NetworkTests(unittest.TestCase):
    def test_overlap_and_adjacency(self):
        self.assertTrue(cidr_overlaps("10.0.0.0/8", "10.1.0.0/16"))
        self.assertFalse(cidr_overlaps("10.0.0.0/24", "10.0.1.0/24"))

    def test_validation(self):
        self.assertTrue(cidr_valid("2001:db8::/32"))
        self.assertFalse(cidr_valid("not-a-network"))

    def test_prefix(self):
        self.assertEqual(cidr_prefix("192.0.2.0/24"), 24)
        self.assertEqual(cidr_prefix("2001:db8::/48"), 48)
