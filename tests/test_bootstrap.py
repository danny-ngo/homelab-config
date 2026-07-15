import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "bootstrap.sh"


class BootstrapTests(unittest.TestCase):
    def run_bootstrap(self, *arguments):
        return subprocess.run(
            [str(BOOTSTRAP), "--dry-run", *arguments],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_macos_defaults_to_workstation_playbook(self):
        result = self.run_bootstrap("--platform", "macos")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Profile: workstation", result.stdout)
        self.assertIn("ansible/playbooks/workstations.yml", result.stdout)
        self.assertIn("limit: workstations", result.stdout)

    def test_arch_defaults_to_execution_node_playbook(self):
        result = self.run_bootstrap("--platform", "arch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Profile: execution-node", result.stdout)
        self.assertIn("ansible/playbooks/execution-node.yml", result.stdout)

    def test_debian_requires_an_explicit_profile(self):
        result = self.run_bootstrap("--platform", "debian")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Debian hosts require --profile", result.stderr)

    def test_infra_profile_uses_site_with_infra_limit(self):
        result = self.run_bootstrap("--platform", "debian", "--profile", "infra")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ansible/playbooks/site.yml", result.stdout)
        self.assertIn("limit: infra_hosts", result.stdout)

    def test_explicit_limit_and_check_mode_are_forwarded(self):
        result = self.run_bootstrap(
            "--platform", "debian", "--profile", "pihole", "--limit", "pihole1", "--check"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("limit: pihole1", result.stdout)
        self.assertIn("--check", result.stdout)

    def test_prepare_only_does_not_select_a_profile(self):
        result = self.run_bootstrap("--platform", "debian", "--prepare-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Profile:", result.stdout)
        self.assertNotIn("ansible-playbook", result.stdout)


if __name__ == "__main__":
    unittest.main()
