import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inventory_path = ROOT / "ansible" / "inventories" / "example" / "hosts.yml"
        cls.inventory = yaml.safe_load(inventory_path.read_text())

    def test_baseline_and_experimental_k3s_groups_are_separate(self):
        groups = self.inventory["all"]["children"]
        baseline_children = set(groups["k3s_cluster"]["children"])
        self.assertEqual(baseline_children, {"k3s_servers", "k3s_workers_supported"})
        self.assertNotIn("k3s_workers_experimental", baseline_children)

        servers = set(groups["k3s_servers"]["hosts"])
        workers = set(groups["k3s_workers_supported"]["hosts"])
        self.assertTrue(servers.isdisjoint(workers))

    def test_k3s_agent_uses_only_the_runtime_discovered_token(self):
        template = (
            ROOT / "ansible" / "roles" / "k3s_agent" / "templates" / "config.yaml.j2"
        ).read_text()
        self.assertIn("k3s_runtime_node_token", template)
        self.assertNotIn("RETRIEVE_SERVER_NODE_TOKEN_AT_RUNTIME", template)

    def test_pinned_k3s_checksums_are_sha256_values(self):
        defaults_paths = [
            ROOT / "ansible" / "roles" / role / "defaults" / "main.yml"
            for role in ("k3s_server", "k3s_agent")
        ]
        for defaults_path in defaults_paths:
            defaults = yaml.safe_load(defaults_path.read_text())
            for architecture, checksum in defaults["k3s_binary_checksums"].items():
                with self.subTest(role=defaults_path.parts[-3], architecture=architecture):
                    self.assertRegex(checksum, re.compile(r"^[0-9a-f]{64}$"))


if __name__ == "__main__":
    unittest.main()
