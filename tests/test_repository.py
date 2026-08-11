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

    def test_current_bare_metal_pihole_baseline_guards_are_present(self):
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
        self.assertIn("pi2", vault_example["vault_tailscale_auth_keys"])
        self.assertIn("pihole_nodes", groups["tailscale_nodes"]["children"])
        self.assertEqual(
            {target["name"] for target in pi2["wol_targets"]},
            {"thinkpad", "thinkcentre"},
        )

        dns_playbook = (
            ROOT / "ansible" / "playbooks" / "dns.yml"
        ).read_text()
        for role in ("pihole", "tailscale", "wol"):
            self.assertIn(role, dns_playbook)

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

    def test_pihole_pin_is_explicitly_limited_to_the_installer_source(self):
        defaults = yaml.safe_load(
            (ROOT / "ansible" / "roles" / "pihole" / "defaults" / "main.yml").read_text()
        )
        tasks = (
            ROOT / "ansible" / "roles" / "pihole" / "tasks" / "main.yml"
        ).read_text()

        self.assertIn("pihole_installer_repository", defaults)
        self.assertIn("pihole_installer_version", defaults)
        self.assertNotIn("pihole_version", defaults)
        self.assertIn("pihole_installer_version", tasks)
        self.assertIn("pihole_version is not defined", tasks)

    def test_tailscale_uses_vaulted_keys_only_for_unattended_enrollment(self):
        task_path = (
            ROOT / "ansible" / "roles" / "tailscale" / "tasks" / "main.yml"
        )
        tasks = task_path.read_text()
        parsed_tasks = yaml.safe_load(tasks)

        self.assertIn("vault_tailscale_auth_keys[inventory_hostname]", tasks)
        self.assertIn("tailscale_backend_state", tasks)
        self.assertIn("--auth-key=file:", tasks)
        self.assertIn("Remove the staged Tailscale auth key", tasks)
        self.assertIn("'REPLACE_ME'", tasks)
        self.assertIn("no_log: true", tasks)
        self.assertIn("Enroll {{ inventory_hostname }} with Tailscale manually", tasks)

        preference_task = next(
            task
            for task in parsed_tasks
            if task["name"]
            == "Reapply mutable Tailscale preferences on an authenticated Linux node"
        )
        preference_argv = preference_task["ansible.builtin.command"]["argv"]
        self.assertEqual(
            preference_argv[:2],
            ["tailscale", "set"],
        )
        self.assertFalse(
            any(argument.startswith("--advertise-tags=") for argument in preference_argv)
        )
        self.assertNotIn("no_log", preference_task)

        enrollment_block = next(
            task
            for task in parsed_tasks
            if task["name"] == "Enroll an unauthenticated Linux Tailscale node"
        )["block"]
        enrollment_task = next(
            task
            for task in enrollment_block
            if task["name"] == "Connect Tailscale with the staged auth key"
        )
        self.assertTrue(
            any(
                argument.startswith("--advertise-tags=")
                for argument in enrollment_task["ansible.builtin.command"]["argv"]
            )
        )
        self.assertTrue(enrollment_task["no_log"])

        reconnect_task = next(
            task
            for task in parsed_tasks
            if task["name"]
            == "Connect an authenticated but stopped Linux node to Tailscale"
        )
        self.assertEqual(
            reconnect_task["ansible.builtin.command"]["argv"],
            ["tailscale", "up"],
        )

    def test_fresh_host_service_tasks_are_safe_in_check_mode(self):
        role_tasks = {
            role: yaml.safe_load(
                (ROOT / "ansible" / "roles" / role / "tasks" / "main.yml").read_text()
            )
            for role in ("firewall", "tailscale", "execution_node")
        }

        guarded_services = (
            (
                "firewall",
                "Install firewalld on Arch-family hosts",
                "Enable firewalld on Arch-family hosts",
                "firewall_firewalld_package",
            ),
            (
                "tailscale",
                "Install Tailscale on Linux",
                "Enable and start Tailscale on Linux",
                "tailscale_linux_package",
            ),
            (
                "execution_node",
                "Install execution-node packages",
                "Enable and start Docker",
                "execution_node_package_install",
            ),
        )
        for role, install_name, service_name, register_name in guarded_services:
            with self.subTest(role=role, service=service_name):
                install_task = next(
                    task for task in role_tasks[role] if task["name"] == install_name
                )
                service_task = next(
                    task for task in role_tasks[role] if task["name"] == service_name
                )
                raw_conditions = service_task["when"]
                conditions = (
                    raw_conditions
                    if isinstance(raw_conditions, str)
                    else "\n".join(raw_conditions)
                )

                self.assertEqual(install_task["register"], register_name)
                self.assertIn("ansible_check_mode", conditions)
                self.assertIn(register_name, conditions)

        t3_service = next(
            task
            for task in role_tasks["execution_node"]
            if task["name"] == "Install or update the T3 Code background service"
        )
        self.assertEqual(t3_service["when"], "not ansible_check_mode")

        docker_membership = next(
            task
            for task in role_tasks["execution_node"]
            if task["name"] == "Grant the execution-node user Docker access"
        )
        self.assertIn("ansible_check_mode", docker_membership["when"])
        self.assertIn("execution_node_package_install", docker_membership["when"])

        docker_template = next(
            task
            for task in role_tasks["execution_node"]
            if task["name"] == "Configure bounded Docker logs and live restore"
        )
        self.assertIn("ansible_check_mode", docker_template["when"])
        self.assertIn("execution_node_package_install", docker_template["when"])

    def test_docker_roles_create_the_configuration_directory(self):
        for role in ("execution_node", "infra_host"):
            tasks = yaml.safe_load(
                (ROOT / "ansible" / "roles" / role / "tasks" / "main.yml").read_text()
            )
            directory = next(
                task
                for task in tasks
                if task["name"] == "Create the Docker configuration directory"
            )["ansible.builtin.file"]
            self.assertEqual(directory["path"], "/etc/docker")
            self.assertEqual(directory["state"], "directory")
            self.assertEqual(directory["owner"], "root")
            self.assertEqual(directory["group"], "root")

    def test_ssh_pipelining_avoids_systemd_osc_module_output(self):
        config = (ROOT / "ansible" / "ansible.cfg").read_text()
        self.assertIn("[ssh_connection]", config)
        self.assertRegex(config, r"(?m)^pipelining\s*=\s*True$")

    def test_roles_do_not_rely_on_deprecated_injected_fact_variables(self):
        deprecated_facts = re.compile(
            r"\bansible_(?:architecture|default_ipv4|distribution_release|"
            r"interfaces|memtotal_mb|os_family|service_mgr|system)\b"
        )
        roles_root = ROOT / "ansible" / "roles"
        for path in roles_root.rglob("*"):
            if path.suffix not in {".yml", ".yaml", ".j2"}:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(deprecated_facts.search(path.read_text()))

    def test_ssh_handler_uses_the_platform_service_name(self):
        defaults = (
            ROOT / "ansible" / "roles" / "common" / "defaults" / "main.yml"
        ).read_text()
        handlers = (
            ROOT / "ansible" / "roles" / "common" / "handlers" / "main.yml"
        ).read_text()

        self.assertIn(
            "'sshd' if ansible_facts['os_family'] == 'Archlinux' else 'ssh'",
            defaults,
        )
        self.assertIn("common_ssh_service_name", handlers)

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

    def test_k3s_pin_is_consistent_and_portainer_compatible(self):
        all_vars = yaml.safe_load(
            (
                ROOT
                / "ansible"
                / "inventories"
                / "example"
                / "group_vars"
                / "all"
                / "main.yml"
            ).read_text()
        )
        role_versions = {
            yaml.safe_load(
                (
                    ROOT
                    / "ansible"
                    / "roles"
                    / role
                    / "defaults"
                    / "main.yml"
                ).read_text()
            )["k3s_version"]
            for role in ("k3s_server", "k3s_agent")
        }

        self.assertEqual(role_versions, {all_vars["k3s_version"]})
        self.assertRegex(all_vars["k3s_version"], re.compile(r"^v1\.34\.\d+\+k3s\d+$"))

    def test_k3s_memory_guards_distinguish_servers_and_agents(self):
        defaults = yaml.safe_load(
            (
                ROOT
                / "ansible"
                / "roles"
                / "k3s_prereqs"
                / "defaults"
                / "main.yml"
            ).read_text()
        )
        tasks = (
            ROOT / "ansible" / "roles" / "k3s_prereqs" / "tasks" / "main.yml"
        ).read_text()

        self.assertGreaterEqual(defaults["k3s_server_minimum_memory_mb"], 2048)
        self.assertGreaterEqual(defaults["k3s_agent_minimum_memory_mb"], 512)
        self.assertIn("k3s_server_minimum_memory_mb", tasks)
        self.assertIn("k3s_agent_minimum_memory_mb", tasks)

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
        self.assertIn("operator_linux_packages", packages)
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
        self.assertIn("github-cli", packages["execution_node_packages"])
        self.assertNotIn("gh", packages["execution_node_packages"])
        self.assertNotIn("herdr", packages["execution_node_packages"])

        execution_node_mise = (
            ROOT
            / "ansible"
            / "roles"
            / "execution_node"
            / "templates"
            / "mise-config.toml.j2"
        ).read_text()
        self.assertIn('herdr = "{{ mise_herdr_version }}"', execution_node_mise)

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

    def test_dotfiles_role_applies_host_profiles_with_stow(self):
        role_root = ROOT / "ansible" / "roles" / "dotfiles"
        defaults = yaml.safe_load((role_root / "defaults" / "main.yml").read_text())
        tasks = yaml.safe_load((role_root / "tasks" / "main.yml").read_text())

        stow_task = next(
            task
            for task in tasks
            if task["name"] == "Apply the selected dotfiles profiles with Stow"
        )
        stow_argv = stow_task["ansible.builtin.command"]["argv"]
        revision_task_index = next(
            index
            for index, task in enumerate(tasks)
            if task["name"] == "Record the deployed dotfiles revision"
        )
        stow_task_index = tasks.index(stow_task)

        self.assertEqual(defaults["dotfiles_profiles"], [])
        self.assertIn(
            "ansible_facts['os_family'] == 'Darwin'",
            defaults["dotfiles_target_home"],
        )
        self.assertIn("stow", stow_argv)
        self.assertIn("--restow", stow_argv)
        self.assertIn("dotfiles_checkout", stow_argv)
        self.assertIn("dotfiles_target_home", stow_argv)
        self.assertIn("dotfiles_profiles", stow_argv)
        self.assertNotIn("--adopt", stow_argv)
        self.assertLess(stow_task_index, revision_task_index)

        group_vars_root = (
            ROOT / "ansible" / "inventories" / "example" / "group_vars"
        )
        expected_profiles = {
            "workstations": ["git", "starship", "zsh"],
            "infra_hosts": ["git", "starship"],
            "execution_nodes": ["git", "starship", "zsh"],
        }
        for group, profiles in expected_profiles.items():
            with self.subTest(group=group):
                group_vars = yaml.safe_load(
                    (group_vars_root / group / "main.yml").read_text()
                )
                self.assertEqual(group_vars["dotfiles_profiles"], profiles)

    def test_execution_node_applies_and_validates_its_login_shell(self):
        role_root = ROOT / "ansible" / "roles" / "execution_node"
        tasks = yaml.safe_load((role_root / "tasks" / "main.yml").read_text())
        validation = yaml.safe_load(
            (role_root / "tasks" / "validate.yml").read_text()
        )
        group_vars = yaml.safe_load(
            (
                ROOT
                / "ansible"
                / "inventories"
                / "example"
                / "group_vars"
                / "execution_nodes"
                / "main.yml"
            ).read_text()
        )

        shell_task = next(
            task
            for task in tasks
            if task["name"] == "Set the execution-node user's login shell"
        )
        shell_validation = next(
            task
            for task in validation
            if task["name"] == "Verify the execution-node user's login shell"
        )

        self.assertEqual(
            shell_task["ansible.builtin.user"],
            {"name": "{{ execution_node_user }}", "shell": "{{ login_shell }}"},
        )
        self.assertIn("ansible_check_mode", shell_task["when"])
        self.assertIn("execution_node_package_install", shell_task["when"])
        self.assertIn(
            "ansible_facts.getent_passwd[execution_node_user][5] == login_shell",
            shell_validation["ansible.builtin.assert"]["that"],
        )
        self.assertEqual(group_vars["login_shell"], "/usr/bin/zsh")

    def test_baseline_roles_are_applied_once_through_site_profiles(self):
        for playbook in ("infra-host.yml", "execution-node.yml", "dns.yml"):
            text = (ROOT / "ansible" / "playbooks" / playbook).read_text()
            self.assertNotIn("common", text)
            self.assertNotIn("firewall", text)

        for profile in ("infra.sh", "execution-node.sh", "pihole.sh", "k3s-worker.sh"):
            text = (ROOT / "bootstrap" / "profiles" / profile).read_text()
            self.assertIn("ansible/playbooks/site.yml", text)

    def test_developer_clis_and_t3_background_service_are_managed(self):
        for role in ("workstation", "execution_node"):
            defaults = yaml.safe_load(
                (ROOT / "ansible" / "roles" / role / "defaults" / "main.yml").read_text()
            )
            packages = defaults[f"{role}_developer_cli_packages"]
            self.assertTrue(any("@openai/codex@" in package for package in packages))
            self.assertTrue(any("opencode-ai@" in package for package in packages))

        defaults = yaml.safe_load(
            (
                ROOT
                / "ansible"
                / "roles"
                / "execution_node"
                / "defaults"
                / "main.yml"
            ).read_text()
        )
        self.assertRegex(
            defaults["t3_code_version"],
            re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$"),
        )

        tasks = yaml.safe_load(
            (
                ROOT
                / "ansible"
                / "roles"
                / "execution_node"
                / "tasks"
                / "main.yml"
            ).read_text()
        )
        service_update = next(
            task
            for task in tasks
            if task["name"] == "Install or update the T3 Code background service"
        )
        service_argv = service_update["ansible.builtin.command"]["argv"]
        self.assertIn("t3@{{ t3_code_version }}", service_argv)
        self.assertIn("service", service_argv)
        self.assertIn("update", service_argv)
        self.assertEqual(service_update["become_user"], "{{ execution_node_user }}")

        task_names = {task["name"] for task in tasks}
        self.assertIn("Stop and disable the legacy T3 Code system service", task_names)
        self.assertIn("Enable persistent user services for the execution-node user", task_names)
        self.assertFalse(
            (
                ROOT
                / "ansible"
                / "roles"
                / "execution_node"
                / "templates"
                / "t3-code.service.j2"
            ).exists()
        )

    def test_raspberry_pis_are_excluded_from_linux_package_manifest_group(self):
        groups = self.inventory["all"]["children"]
        manifest_children = set(groups["non_raspberry_pi_linux"]["children"])
        self.assertEqual(manifest_children, {"infra_hosts", "execution_nodes"})

    def test_pi1_nodes_use_only_the_documented_armv6_inventory_exception(self):
        groups = self.inventory["all"]["children"]
        pi1_children = set(groups["pi1_edge_nodes"]["children"])
        linux_children = set(groups["linux_nodes"]["children"])

        self.assertEqual(pi1_children, {"pi1_sentinel_nodes", "pi1_probe_nodes"})
        self.assertTrue(pi1_children.isdisjoint(linux_children))
        self.assertEqual(
            groups["pi1_edge_nodes"]["vars"]["ansible_python_interpreter"],
            "/usr/bin/python3",
        )

        for group_name in pi1_children:
            for host in groups[group_name]["hosts"].values():
                self.assertEqual(host["expected_os_family"], "Debian")
                self.assertEqual(host["expected_architecture"], "armv6l")

    def test_pi1_probe_uses_vaulted_healthchecks_and_no_message_broker(self):
        groups = self.inventory["all"]["children"]
        probe = groups["pi1_probe_nodes"]["hosts"]["pi1probe"]
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
        role_root = ROOT / "ansible" / "roles" / "pi1_probe"
        role_text = "\n".join(
            path.read_text() for path in role_root.rglob("*") if path.is_file()
        )

        self.assertEqual(
            {target["name"] for target in probe["pi1_probe_targets"]},
            {"thinkpad", "thinkcentre"},
        )
        self.assertEqual(probe["pi1_probe_boot_media_gb"], 8)
        self.assertEqual(
            set(vault_example["vault_pi1_probe_healthchecks_urls"]["pi1probe"]),
            {"probe", "thinkpad", "thinkcentre"},
        )
        self.assertIn("Healthchecks", role_text)
        self.assertIn("User={{ pi1_probe_user }}", role_text)
        self.assertIn("NoNewPrivileges=true", role_text)
        self.assertNotIn("mqtt", role_text.lower())
        self.assertNotIn("mosquitto", role_text.lower())

    def test_pi2_installs_fixed_non_root_wake_commands(self):
        groups = self.inventory["all"]["children"]
        wol = groups["pihole_nodes"]["hosts"]["pi2"]
        role_root = ROOT / "ansible" / "roles" / "wol"
        tasks = (role_root / "tasks" / "main.yml").read_text()
        command_template = (role_root / "templates" / "wake-target.sh.j2").read_text()

        self.assertEqual(
            {target["name"] for target in wol["wol_targets"]},
            {"thinkpad", "thinkcentre"},
        )
        self.assertIn("name: wakeonlan", tasks)
        self.assertIn("/usr/local/bin/wake-{{ item.name }}", tasks)
        self.assertIn("/usr/bin/wakeonlan", command_template)
        self.assertNotIn("sudo", command_template)

    def test_pi1_sentinel_checks_pi2_services_with_vaulted_heartbeats(self):
        groups = self.inventory["all"]["children"]
        sentinel = groups["pi1_sentinel_nodes"]["hosts"]["pi1sentinel"]
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
        role_root = ROOT / "ansible" / "roles" / "pi1_sentinel"
        role_text = "\n".join(
            path.read_text() for path in role_root.rglob("*") if path.is_file()
        )

        self.assertEqual(sentinel["pi1_sentinel_dns_server"], "192.0.2.33")
        self.assertEqual(sentinel["pi1_sentinel_boot_media_gb"], 32)
        self.assertEqual(
            set(vault_example["vault_pi1_sentinel_healthchecks_urls"]["pi1sentinel"]),
            {"dns_udp", "dns_tcp", "http", "sentinel"},
        )
        self.assertIn("/usr/bin/dig", role_text)
        self.assertIn("+tcp", role_text)
        self.assertIn("User={{ pi1_sentinel_user }}", role_text)
        self.assertIn("NoNewPrivileges=true", role_text)
        self.assertNotIn("wakeonlan", role_text)

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
