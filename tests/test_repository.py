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

    def test_baseline_k3s_groups_contain_only_supported_nodes(self):
        groups = self.inventory["all"]["children"]
        baseline_children = set(groups["k3s_cluster"]["children"])
        self.assertEqual(baseline_children, {"k3s_servers", "k3s_workers_supported"})
        self.assertNotIn("k3s_workers_experimental", baseline_children)

        servers = set(groups["k3s_servers"]["hosts"])
        workers = set(groups["k3s_workers_supported"]["hosts"])
        self.assertTrue(servers.isdisjoint(workers))

    def test_edge_node_architecture_guards_are_present(self):
        groups = self.inventory["all"]["children"]
        pi2 = groups["pihole_nodes"]["hosts"]["pi2"]
        self.assertEqual(pi2["expected_architecture"], "armv7l")
        self.assertNotIn("k3s_workers_experimental", groups)
        self.assertNotIn("pi2", groups["k3s_workers_supported"]["hosts"])
        self.assertFalse(
            (
                ROOT
                / "ansible"
                / "playbooks"
                / "k3s-admit-experimental.yml"
            ).exists()
        )
        self.assertNotIn(
            "k3s-admit-experimental",
            (ROOT / "Makefile").read_text(),
        )

        vault_example = yaml.safe_load(
            (
                ROOT
                / "ansible"
                / "inventories"
                / "example"
                / "group_vars"
                / "all"
                / "vault.yml.example"
            ).read_text()
        )
        self.assertIn("pi2", vault_example["vault_pihole_web_password_hashes"])

        pihole_defaults = yaml.safe_load(
            (ROOT / "ansible" / "roles" / "pihole" / "defaults" / "main.yml").read_text()
        )
        self.assertGreaterEqual(pihole_defaults["pihole_minimum_memory_mb"], 512)

    def test_pihole_role_installs_bare_metal_and_uses_v6_config_keys(self):
        tasks = (
            ROOT / "ansible" / "roles" / "pihole" / "tasks" / "main.yml"
        ).read_text()
        config = (
            ROOT / "ansible" / "roles" / "pihole" / "templates" / "pihole.toml.j2"
        ).read_text()

        self.assertIn("basic-install.sh", tasks)
        self.assertNotIn("docker", tasks.lower())
        self.assertIn("[webserver.api]", config)
        self.assertIn("pwhash =", config)
        self.assertNotIn("\npassword =", config)

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

        brewfile_text = brewfile.read_text()
        self.assertIn("brew \"mise\"", brewfile_text)
        self.assertNotIn("brew \"ansible\"", brewfile_text)
        self.assertIn("packages/macos/Brewfile", workstation_tasks)

        packages = yaml.safe_load(linux_manifest.read_text())
        self.assertIn("common_packages", packages)
        self.assertIn("infra_host_packages", packages)
        self.assertIn("execution_node_packages", packages)
        for profile in ("infra_host_packages", "execution_node_packages"):
            self.assertNotIn("ansible", packages[profile])
            self.assertNotIn("uv", packages[profile])
        self.assertIn("docker.io", packages["infra_host_packages"])
        self.assertIn("docker-cli", packages["infra_host_packages"])
        self.assertIn("docker-compose", packages["infra_host_packages"])
        self.assertIn("docker", packages["execution_node_packages"])
        self.assertIn("docker-buildx", packages["execution_node_packages"])
        self.assertNotIn("docker-buildx-plugin", packages["execution_node_packages"])

    def test_package_ownership_has_no_overlapping_declarations(self):
        linux_manifest = yaml.safe_load(
            (ROOT / "ansible" / "packages" / "linux" / "packages.yml").read_text()
        )
        declared_linux_packages = {
            package
            for package_list in linux_manifest.values()
            for package in package_list
        }
        bootstrap_owned = {
            "ca-certificates",
            "curl",
            "git",
            "openssh",
            "openssh-client",
            "python",
            "python3",
            "uv",
        }
        role_owned = {"firewalld", "stow", "tailscale", "ufw"}

        self.assertTrue(declared_linux_packages.isdisjoint(bootstrap_owned))
        self.assertTrue(declared_linux_packages.isdisjoint(role_owned))
        self.assertNotIn("rsync", declared_linux_packages)

        brewfile = (
            ROOT / "ansible" / "packages" / "macos" / "Brewfile"
        ).read_text()
        self.assertNotIn('cask "tailscale-app"', brewfile)

        tailscale_tasks = (
            ROOT / "ansible" / "roles" / "tailscale" / "tasks" / "main.yml"
        ).read_text()
        self.assertIn("name: tailscale", tailscale_tasks)
        self.assertIn("name: tailscale-app", tailscale_tasks)

    def test_baseline_roles_are_applied_once_through_site_profiles(self):
        for playbook in ("infra-host.yml", "execution-node.yml", "dns.yml"):
            text = (ROOT / "ansible" / "playbooks" / playbook).read_text()
            self.assertNotIn("common", text)
            self.assertNotIn("firewall", text)

        for profile in ("infra.sh", "execution-node.sh", "pihole.sh", "k3s-worker.sh"):
            text = (ROOT / "bootstrap" / "profiles" / profile).read_text()
            self.assertIn("ansible/playbooks/site.yml", text)

    def test_developer_clis_and_t3_headless_service_are_managed(self):
        for role in ("workstation", "execution_node"):
            defaults = yaml.safe_load(
                (ROOT / "ansible" / "roles" / role / "defaults" / "main.yml").read_text()
            )
            packages = defaults[f"{role}_developer_cli_packages"]
            self.assertTrue(any("@openai/codex@" in package for package in packages))
            self.assertTrue(any("opencode-ai@" in package for package in packages))

        service = (
            ROOT
            / "ansible"
            / "roles"
            / "execution_node"
            / "templates"
            / "t3-code.service.j2"
        ).read_text()
        self.assertIn("t3 serve", service)
        self.assertIn("--tailscale-serve", service)

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

    def test_python_tooling_uses_uv_lock_and_python_314(self):
        self.assertEqual((ROOT / ".python-version").read_text().strip(), "3.14")
        self.assertTrue((ROOT / "pyproject.toml").is_file())
        self.assertTrue((ROOT / "uv.lock").is_file())
        self.assertFalse((ROOT / "requirements-dev.txt").exists())

        requirements = (ROOT / "bootstrap" / "lib" / "requirements.sh").read_text()
        self.assertIn("uv python install --managed-python 3.14", requirements)
        self.assertIn("uv python pin --global 3.14", requirements)
        self.assertIn("uv tool install", requirements)

        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("uv tool dir --bin", makefile)


if __name__ == "__main__":
    unittest.main()
