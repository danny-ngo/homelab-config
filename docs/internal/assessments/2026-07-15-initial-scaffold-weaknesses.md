## Repository Weakness Analysis

> Reviewed against the implementation on 2026-07-15. Confirmed defects were
> corrected in the initial repository commit: Pi-hole vault coverage, SSH
> first-use guidance, bootstrap validation ordering/help, fail-fast DNS rollout,
> K3s installation and runtime token propagation, missing-group diagnostics,
> Docker log bounds, local-device preflight, robust filter imports, full
> validation-playbook syntax coverage, configurable dotfiles branches, recovery
> runbooks, and repository hygiene. The remaining observations are either
> intentional design choices documented by the specifications (root-only K3s
> agent configuration, strict host-key checking, disabled Tailscale SSH, no
> persistent fact cache), speculative future risks, or larger acceptance tests
> that require the real heterogeneous fleet rather than a generic CI container.

### Security

1. **K3s agent token is passed in plaintext via Jinja2 template** (`roles/k3s_agent/templates/config.yaml.j2`). The `no_log: true` on the task prevents Ansible output leakage, but the token ends up on disk in `/etc/rancher/k3s/config.yaml` with mode `0600`. If the host is compromised, the token is readable. Consider using `--token` from `ansible.builtin.command` or a systemd drop-in instead of a persistent file.

2. **Pi-hole web password hash is rendered into `/etc/pihole/pihole.toml`** with `mode: '0600'` and `no_log: true` — good — but every host added to `pihole_nodes` also needs a matching key in `vault_pihole_web_password_hashes`. The role now fails with an explicit assertion before the template lookup.

3. **`host_key_checking = True` in `ansible.cfg`** is correct for security, but the first run against a new host will block automation with an interactive prompt. There's no documented way to handle `StrictHostKeyChecking=accept-new` as a stepping stone.

4. **Tailscale command uses `--ssh=false`** which disables Tailscale SSH. The README says "Password SSH remains enabled until both recovery flags are explicitly true," but the `common` role's SSH hardening (`PasswordAuthentication no`) only fires when **both** `ssh_recovery_access_confirmed` and `ssh_hardening_enabled` are true. This is a safe gate, but the comment in `tailscale` role's `--ssh=false` could silently conflict with future Tailscale SSH enablement.

5. **No `.vault-pass` file or `ANSIBLE_VAULT_PASSWORD_FILE` enforcement in CI**. The CI workflow runs `make ci` (lint, syntax, test) which doesn't need vault, but if someone adds vault-encrypted tasks to the playbooks tested in CI, the pipeline will break silently.

### Reliability & Correctness

6. **`bootstrap_run_playbook` has a logic bug** at `bootstrap/lib/common.sh:117-118`. The `[[ -n "$selected_limit" ]]` assertion comes **after** `--limit "$selected_limit"` is already appended to the command. If the limit is empty, Ansible will fail with a confusing error before the bootstrap assertion fires.

7. **`dns.yml` uses `serial: 1`** for rolling Pi-hole updates, but there's no `max_fail_percentage` or `any_errors_fatal` guard. If one Pi-hole fails mid-rollout, the playbook will stop after the failed host, leaving DNS in a split-brain state.

8. **`k3s_server` role doesn't install or start the K3s service** — it only writes the config file. The actual `k3s` binary install and systemd enable/start are missing from the automation. The K3s recovery runbook says "Rebuild the ThinkPad server first" implying manual steps, but this is an automation gap.

9. **`k3s_prereqs` asserts `groups['k3s_servers'] | length == 1`** but doesn't guard against the case where the `k3s_servers` group doesn't exist at all (e.g., wrong inventory). This will produce an unhelpful Jinja2 error.

10. **`execution_node` role installs Docker but doesn't configure `daemon.json`** (log rotation, storage driver, live-restore). Docker defaults can fill disks on small hosts like the ThinkCentre.

11. **`storage` role uses `ansible.posix.mount` with `state: mounted`** but doesn't validate that the source device exists before attempting mount. A typo in `src` will produce a confusing systemd error.

### Testing

12. **No Ansible molecule tests or integration tests** for any role. The `tests/` directory has only unit tests for bootstrap CLI args and the `network.py` filter plugin. There's no validation that roles converge correctly or are idempotent against real or containerized hosts.

13. **`test_network.py` uses `sys.path.insert(0, ...)`** to import the filter plugin. This is fragile; a `conftest.py` or proper package structure would be more robust.

14. **No test for the `validate.yml` playbook** or for any role's `validate` tasks in isolation.

### Code Quality

15. **Duplicated mise config templates** — `execution_node/templates/mise-config.toml.j2` and `workstation/templates/mise-config.toml.j2` are identical. This should be extracted to a shared template or role.

16. **Duplicated mise version variables** — `mise_node_version`, `mise_go_version`, `mise_rust_version` are defined in both `execution_node/defaults/main.yml` and `workstation/defaults/main.yml`. A change in one won't propagate to the other.

17. **`dotfiles` role has `validate.yml` that asserts `dotfiles_branch == 'main'`** — this will fail for anyone who uses a different branch, which contradicts the configurable `dotfiles_branch` variable.

18. **`infra_host` role has a hardcoded path** `/srv/infra` in the default. If this collides with another service's mount point, there's no conflict detection.

### CI/CD

19. **CI runs on `ubuntu-latest` only**. There's no matrix for macOS or Arch, so the platform-specific bootstrap paths (`macos.sh`, `arch.sh`) are never tested in CI.

20. **CI doesn't run `make check`** (Ansible check mode). It only runs lint + syntax + unit tests. A playbook that passes syntax but breaks at runtime won't be caught.

21. **Resolved 2026-07-28:** `requirements-dev.txt` was replaced by
    `pyproject.toml`, `.python-version`, and a committed `uv.lock`; bootstrap
    and CI now synchronize the Python 3.14 environment with `uv sync --frozen`.

### Operational

22. **`--dry-run` mode in bootstrap doesn't propagate to Ansible check mode** — it prints the command but the Ansible playbook itself won't run in `--check` unless `--check` is also passed. The `dry_run` and `check_mode` flags are independent but the help text doesn't clarify this.

23. **No rollback mechanism**. If a playbook run partially fails, there's no documented or automated way to revert changes (e.g., restore SSH config, undo package installs).

24. **Runbooks are minimal** — `dns.md` and `k3s-recovery.md` are 3 lines each. They lack step-by-step commands, failure modes, and expected outputs.

25. **No changelog or versioning**. The repository has no `CHANGELOG.md` or git tags to track which configuration version is deployed to which host.

### Minor / Cosmetic

26. **`.DS_Store` is tracked** in the repo root. It should be in `.gitignore`.

27. **`scripts/` and `files/` directories are empty** — dead scaffold entries that add noise.

28. **`ansible.cfg` has `fact_caching = memory`** which means facts are re-gathered on every run. For large inventories, this adds latency with no benefit.

29. **No `ansible.builtin.package_facts` or `package_facts` caching** — each role that installs packages re-evaluates package state independently.
