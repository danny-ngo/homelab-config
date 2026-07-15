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

    def test_platform_package_manifests_are_consumed_by_ansible(self):
        brewfile = ROOT / "ansible" / "packages" / "macos" / "Brewfile"
        linux_manifest = ROOT / "ansible" / "packages" / "linux" / "packages.yml"
        workstation_tasks = (
            ROOT / "ansible" / "roles" / "workstation" / "tasks" / "main.yml"
        ).read_text()

        self.assertIn("brew \"mise\"", brewfile.read_text())
        self.assertIn("packages/macos/Brewfile", workstation_tasks)

        packages = yaml.safe_load(linux_manifest.read_text())
        self.assertIn("common_packages", packages)
        self.assertIn("infra_host_packages", packages)
        self.assertIn("execution_node_packages", packages)

    def test_raspberry_pis_are_excluded_from_linux_package_manifest_group(self):
        groups = self.inventory["all"]["children"]
        manifest_children = set(groups["non_raspberry_pi_linux"]["children"])
        self.assertEqual(manifest_children, {"infra_hosts", "execution_nodes"})

    def test_bootstrap_uses_focused_library_modules(self):
        bootstrap = (ROOT / "bootstrap.sh").read_text()
        for module in ("detect-platform.sh", "logging.sh", "requirements.sh"):
            self.assertIn(f"bootstrap/lib/{module}", bootstrap)
            self.assertTrue((ROOT / "bootstrap" / "lib" / module).is_file())
        self.assertFalse((ROOT / "bootstrap" / "lib" / "common.sh").exists())


if __name__ == "__main__":
    unittest.main()
