import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "bootstrap.sh"
INSTALLER = ROOT / "install.sh"


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
        self.assertIn("brew install uv", result.stdout)
        self.assertIn("uv python install --managed-python 3.14", result.stdout)
        self.assertIn("uv tool install --managed-python --python 3.14 --force ansible-core==2.20.7", result.stdout)
        self.assertIn(".local/bin/ansible-playbook", result.stdout)
        self.assertNotIn(".venv/bin/ansible-playbook", result.stdout)
        self.assertLess(
            result.stdout.index("uv python install"),
            result.stdout.index("uv tool install"),
        )
        self.assertLess(
            result.stdout.index("uv tool install"),
            result.stdout.index("uv venv"),
        )
        self.assertIn("ansible/playbooks/workstations.yml", result.stdout)
        self.assertIn("limit: workstations", result.stdout)

    def test_macos_bootstrap_leaves_homebrew_to_remote_installer(self):
        platform_script = (ROOT / "bootstrap" / "platforms" / "macos.sh").read_text()
        installer = INSTALLER.read_text()
        self.assertIn("Homebrew/install/HEAD/install.sh", installer)
        self.assertNotIn("Homebrew/install/HEAD/install.sh", platform_script)
        self.assertIn("bootstrap_require_command brew", platform_script)
        self.assertLess(
            platform_script.index("brew install uv"),
            platform_script.index("bootstrap_prepare_controller"),
        )

    def test_arch_prepare_only_installs_global_uv_then_python_and_pin(self):
        result = self.run_bootstrap("--platform", "arch", "--prepare-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pacman --sync --needed --noconfirm uv git openssh python", result.stdout)
        self.assertIn("uv python install --managed-python 3.14", result.stdout)
        self.assertIn("uv python pin --global 3.14", result.stdout)
        self.assertLess(
            result.stdout.index("pacman --sync"),
            result.stdout.index("uv python install"),
        )
        self.assertLess(
            result.stdout.index("uv python install"),
            result.stdout.index("uv python pin"),
        )
        self.assertNotIn("uv tool install", result.stdout)
        self.assertNotIn("uv venv", result.stdout)
        self.assertNotIn("ansible-playbook", result.stdout)

    def test_linux_without_prepare_only_points_to_workstation_controller(self):
        result = self.run_bootstrap("--platform", "debian")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Linux hosts are managed nodes", result.stderr)
        self.assertIn("--prepare-only", result.stderr)
        self.assertIn("macOS workstation", result.stderr)

    def test_debian_prepare_only_installs_systemwide_uv_then_python_and_pin(self):
        result = self.run_bootstrap("--platform", "debian", "--prepare-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "apt-get install --yes ca-certificates curl git openssh-client python3",
            result.stdout,
        )
        self.assertIn("https://astral.sh/uv/0.11.32/install.sh", result.stdout)
        self.assertIn("UV_INSTALL_DIR=/usr/local/bin", result.stdout)
        self.assertIn("uv python install --managed-python 3.14", result.stdout)
        self.assertIn("uv python pin --global 3.14", result.stdout)
        self.assertIn(
            "install --directory --mode 0755 /etc/systemd/logind.conf.d",
            result.stdout,
        )
        self.assertIn(
            "install --mode 0644 "
            + str(ROOT / "ansible/roles/infra_host/templates/logind-lid.conf.j2")
            + " /etc/systemd/logind.conf.d/60-homelab-lid.conf",
            result.stdout,
        )
        self.assertIn("systemctl reload systemd-logind.service", result.stdout)
        self.assertIn("the lid can now be closed", result.stdout)
        self.assertNotIn("uv tool install", result.stdout)
        self.assertNotIn("ansible-playbook", result.stdout)

    def test_workstation_controller_forwards_profile_limit_and_check_mode(self):
        result = self.run_bootstrap(
            "--platform", "macos", "--profile", "pihole", "--limit", "pihole1", "--check"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ansible/playbooks/site.yml", result.stdout)
        self.assertIn("limit: pihole1", result.stdout)
        self.assertIn("--check", result.stdout)

    def test_pi1_profiles_use_the_purpose_specific_playbooks(self):
        cases = {
            "pi1-sentinel": (
                "ansible/playbooks/pi1-sentinel.yml",
                "pi1_sentinel_nodes",
            ),
            "pi1-probe": ("ansible/playbooks/pi1-probe.yml", "pi1_probe_nodes"),
        }
        for profile, (playbook, default_limit) in cases.items():
            with self.subTest(profile=profile):
                result = self.run_bootstrap(
                    "--platform",
                    "macos",
                    "--profile",
                    profile,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(playbook, result.stdout)
                self.assertIn(f"limit: {default_limit}", result.stdout)
                self.assertNotIn("ansible/playbooks/site.yml", result.stdout)

    def test_linux_explicit_profile_is_rejected_after_prerequisite_preview(self):
        result = self.run_bootstrap("--platform", "arch", "--profile", "execution-node")
        self.assertEqual(result.returncode, 2)
        self.assertIn("uv python pin --global 3.14", result.stdout)
        self.assertIn("profiles must be applied from the macOS workstation", result.stderr)


if __name__ == "__main__":
    unittest.main()
