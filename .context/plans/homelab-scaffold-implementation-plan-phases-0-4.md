# Homelab Scaffold Implementation Plan — Phases 0–4

## Summary

Implement the empty repository through the supported K3s baseline:

1. Establish reproducible Ansible tooling, safe example inventory, Vault integration, validation, and operator commands.
2. Configure the MacBook, Debian ThinkPad, and CachyOS ThinkCentre.
3. Move package ownership out of the dotfiles installer and into Ansible; use the dotfiles repository only for GNU Stow-managed configuration.
4. Provision the dedicated Pi 2 Pi-hole, then add a second supported resolver
   later for redundancy.
5. Install a single-server K3s cluster on the ThinkPad with two supported Pi 3 workers.

Phases 5–6—databases, pipeline orchestration, backup products, and observability—remain out of scope. Do not create empty roles or placeholder playbooks for them.

## Fixed decisions and defaults

- Use uv-managed Python 3.14, `ansible-core==2.20.7`,
  `ansible-lint==26.6.0`, and `yamllint==1.38.0`.
- Install operational Ansible with `uv tool` and keep the repository `.venv`
  for locked development and CI dependencies from `pyproject.toml` and
  `uv.lock`.
- Use the MacBook as the Ansible controller. Linux initial bootstrap installs
  global uv, per-user uv-managed Python 3.14, and a per-user global Python pin,
  then stops; Linux never installs controller Ansible.
- Pin collections to `community.general==13.0.1` and `ansible.posix==2.2.0`.
- Track safe inventory examples in Git. Keep `ansible/inventories/production/`, Vault passwords, generated artifacts, and fetched kubeconfigs ignored.
- Use Ansible Vault for Tailscale enrollment keys and Pi-hole credentials. Supply the Vault password through `ANSIBLE_VAULT_PASSWORD_FILE`; never encode its path in the repository.
- Preserve strict SSH host-key checking. Password SSH remains enabled until `ssh_recovery_access_confirmed: true` and `ssh_hardening_enabled: true` are both explicitly set.
- Enroll the two unattended Linux computers with distinct tagged Tailscale auth keys. Keep Tailscale SSH disabled and preserve OpenSSH/LAN recovery.
- Install the standalone Tailscale macOS client through Homebrew and leave Mac enrollment interactive.
- On Linux, set Tailscale `accept-dns=false`, advertise no routes, and use tags `tag:infra` and `tag:execution-node`.
- Track `https://github.com/danny-ngo/dotfiles` branch `main`; record the resolved commit after each update.
- Never invoke the dotfiles repository’s `install.sh`. Snapshot its package lists from planning revision `0e6bfc094f8c6867fa71684e5aa87b517feeede0` into Ansible.
- Apply Stow packages:
  - MacBook: `fastfetch`, `ghostty`, `git`, `starship`, `zsh`.
  - ThinkPad and ThinkCentre: `fastfetch`, `git`, `starship`, `zsh`.
  - Exclude `karabiner`, `raycast`, `scripts`, `sketchybar`, `wallpapers`, and `wezterm`.
  - Fail on unmanaged target-file conflicts; never use `stow --adopt`.
- Configure the ThinkCentre using the existing personal account and `~/Developer`; do not create a separate agent user, quotas, concurrency controls, or automatic cache deletion.
- Install rootful Docker Engine for compatibility. Do not expose its API over TCP. Document and validate that Docker group membership grants effective root-level access.
- Pin Codex CLI `0.144.4`, using the official x86_64 Linux release archive and checksum. Authentication is a one-time operator action using `codex login --device-auth`; Ansible never manages Codex credentials. Official Codex guidance supports device-code login for headless hosts.
- Use Pi-hole Core `v6.4.3`, its current declarative
  `/etc/pihole/pihole.toml` interface, and sequential deployment. Pi-hole
  currently requires at least 512 MB RAM and 2 GB free space; the confirmed
  256 MB Pi 1 boards are excluded and the 1 GB Pi 2 is the dedicated host.
  [Pi-hole prerequisites](https://docs.pi-hole.net/main/prerequisites/)
- Pin K3s to `v1.35.6+k3s1`, one release line behind the newest current branch. Use SQLite and retain bundled Flannel, CoreDNS, Traefik, ServiceLB, metrics-server, and local-path storage. Do not add GitOps.
- Keep kubeconfig fetching disabled by default.
- Use `docker.io/library/busybox:1.37.0@sha256:9532d8c39891ca2ecde4d30d7710e01fb739c87a8b9299685c63704296b16028` for architecture validation.
- Default cluster and service CIDRs are `10.42.0.0/16` and `10.43.0.0/16`; production preflight must prove they do not overlap the LAN or other routed networks.

## Target repository structure

```text
.
├── .github/workflows/ci.yml
├── .context/
├── ansible/
│   ├── ansible.cfg
│   ├── requirements.yml
│   ├── filter_plugins/network.py
│   ├── inventories/example/
│   ├── playbooks/
│   └── roles/
│       ├── common/
│       ├── storage/
│       ├── firewall/
│       ├── workstation/
│       ├── tailscale/
│       ├── dotfiles/
│       ├── infra_host/
│       ├── execution_node/
│       ├── pihole/
│       ├── k3s_prereqs/
│       ├── k3s_server/
│       └── k3s_agent/
├── bootstrap/
│   ├── lib/common.sh
│   ├── platforms/{macos,debian,arch}.sh
│   └── profiles/{workstation,infra,execution-node,pihole,k3s-worker}.sh
├── docs/
│   ├── decisions/
│   └── runbooks/
├── scripts/
├── tests/
├── .ansible-lint
├── .editorconfig
├── .gitignore
├── .yamllint
├── Makefile
├── README.md
├── bootstrap.sh
├── install.sh
├── pyproject.toml
└── uv.lock
```

Each role must contain real defaults, `meta/argument_specs.yml`, task files, relevant templates, handlers, and `tasks/validate.yml`. Do not generate unused directory trees.

## Public interfaces and variable contracts

### Operator commands

`install.sh` will be the curl-delivered fresh-machine entry point. It will
prepare Homebrew and a persistent checkout on macOS, or download temporary
source and force prerequisite-only preparation on Linux.

`bootstrap.sh` will:

- Be the local operation entry point and detect macOS, Debian-family Linux, or Arch-family Linux unless explicitly overridden.
- Run shared helpers from `bootstrap/lib/`, then the matching local platform module.
- On macOS, prepare controller tooling and dispatch the selected profile module; default to `workstation`.
- On Debian and Arch, require `--prepare-only`, install managed-node
  prerequisites, and never invoke a profile or install Ansible.
- On the controller, create `.venv`, install the exact development requirements, and install pinned Ansible collections under `.ansible/collections`.
- Copy `ansible/inventories/example` to ignored `ansible/inventories/production` only when production does not already exist, then stop so placeholder values cannot be applied.
- Have each profile module invoke the relevant Ansible playbook with a profile-specific inventory limit.
- Support controller preparation without connecting to a managed host; CI
  restores its locked environment directly with uv.

The `Makefile` will expose:

- `bootstrap`, `deps`, `init-inventory`
- `inventory`, `lint`, `syntax`, `test`, `ci`
- `check PLAYBOOK=... LIMIT=...`
- `apply PLAYBOOK=... LIMIT=...`
- `validate LIMIT=...`
- `idempotency PLAYBOOK=... LIMIT=...`
- `phase1`, `phase2`, `dns`, `k3s`
- `k3s-reboot-test`, requiring an explicit limit

### Inventory contract

Tracked example inventory defines:

- `workstations`
- `infra_hosts`
- `execution_nodes`
- `tailscale_nodes`
- `pihole_nodes`
- `k3s_cluster`
- `k3s_servers`
- `k3s_workers_supported`
- `linux_nodes`

`k3s_cluster` contains only the server and supported workers. The Pi 2 stays
outside every K3s worker group.

Required production values include:

- `ansible_host`, `ansible_user`, privilege method, expected OS family, expected architecture
- LAN address, LAN CIDR, local domain, emergency resolvers
- administrator public keys and recovery confirmation
- storage devices, mount points, and minimum free-space thresholds
- Tailscale tags
- dotfiles target user and package allowlist
- K3s node address, labels, taints, and expected architecture
- Pi-hole identity, interface, upstream resolvers, local DNS records, and shared lists

The example inventory uses reserved documentation addresses and fake keys only.

### Vault contract

Production `group_vars/all/vault.yml` contains:

```yaml
vault_tailscale_auth_keys:
  thinkpad: ...
  thinkcentre: ...

vault_pihole_web_password_hashes:
  pi2: ...
```

No K3s token is stored in Vault or inventory. Avoid storing sudo passwords where SSH keys and passwordless narrowly scoped sudo can be used.

## Phase 1 — Automation foundation

### Configuration and testing

- Configure `ansible.cfg` with production inventory as the default, local role/collection paths, retry files disabled, strict host-key checking, and no persistent fact cache.
- Implement `network.py` with Python’s `ipaddress` module for CIDR validation and overlap detection.
- Add YAML lint, Ansible lint, syntax, inventory graph, secret-pattern, group-membership, and network-filter tests.
- Add a GitHub Actions workflow that installs uv, restores the locked
  uv-managed Python 3.14 environment, and runs the same `make ci` path as local
  development.
- Add a second-run parser so `make idempotency` fails when the second recap contains unexplained changes.

### Base roles

- `common`: facts, OS/architecture assertions, hostname, timezone, locale, NTP, administrator keys, sudo, package subsets, and safe SSH hardening.
- `storage`: verify declared devices, create persistent directories, configure existing filesystems/mounts, and install health tooling. Formatting remains disabled unless an explicit destructive variable and tag are supplied.
- `firewall`:
  - Use UFW on Debian/Raspberry Pi OS.
  - Use firewalld on CachyOS.
  - Allow LAN SSH from declared management networks.
  - Allow Tailscale UDP 41641 on tailnet nodes.
  - Allow DNS TCP/UDP 53 and Pi-hole administration only from the LAN on Pi-hole nodes.
  - Allow K3s TCP 6443, TCP 10250, and UDP 8472 only between declared cluster nodes.
  - Do not expose Docker’s TCP API, databases, public ingress, or admin interfaces.

### Foundation playbooks

- `infra-host.yml`: configure the ThinkPad as a persistent infrastructure host without assigning it permanent Ansible controller ownership.
- `base.yml`: run common, storage, and firewall roles once per Linux host despite overlapping groups.
- `validate.yml`: invoke every role’s read-only validation entry point.
- `site.yml`: import stable Phase 1–4 playbooks; exclude reboot testing,
  destructive storage, router changes, and upgrades.

## Phase 2 — Primary computers

### Workstation role

- Migrate the Homebrew formula and cask arrays from the dotfiles macOS installer at revision `0e6bfc0`.
- Manage them with `community.general.homebrew` and `community.general.homebrew_cask`.
- Keep GUI applications Mac-only.
- Do not let future dotfiles branch changes implicitly add packages; package changes require review in this repository.

### Dotfiles role

- Clone or update `main` into `~/Developer/dotfiles`.
- Capture `git rev-parse HEAD` before and after the update and record the resolved revision under `~/.local/state/homelab/dotfiles-revision`.
- Install GNU Stow through the applicable package role.
- Validate every configured Stow package exists.
- Run `stow --restow --target <home> <allowlisted packages>` as the target user.
- Fail with a clear list of conflicting unmanaged files.
- Report no changes when `main` and the resulting links are unchanged.

### Tailscale role

- Use distribution-native packages on Debian and CachyOS.
- Install `tailscale-app` through Homebrew on macOS.
- Enroll Linux hosts only when unauthenticated, passing the Vaulted key under `no_log`.
- Use all desired `tailscale up` flags together so reruns do not accidentally clear preferences.
- Validate daemon state, assigned tailnet address, expected tag identity, `accept-dns=false`, and SSH disabled.
- Document Mac login, ACL/tag ownership, key revocation, and LAN recovery.

### ThinkPad infrastructure host

- Install the utilities needed to operate and recover its persistent infrastructure services.
- Create a named persistent infrastructure root for service-specific roles to use in later phases.
- Keep the ThinkPad a managed infrastructure host rather than an Ansible
  controller.
- Preserve LAN access to every Raspberry Pi independently of Tailscale.

### ThinkCentre execution node

- Install CachyOS packages for shells, build tools, Go, Docker
  Engine/Compose/buildx, `bubblewrap`, Stow, and the selected CLI utilities.
  Initial bootstrap already owns the system Python and global `uv` packages.
- Enable Docker and add only the declared personal account to the Docker group.
- Install Codex CLI `0.144.4` from the official x86_64 Linux asset with checksum verification.
- Configure Codex credential storage as `auto`; do not create or distribute `auth.json`.
- Validate `codex --version`, then report authentication as a required operator action until `codex login status` succeeds.
- Use `~/Developer` for repositories and normal per-user cache locations.
- Smoke-test:
  - LAN and Tailscale SSH.
  - Clone the dotfiles repository into a temporary directory.
  - Run `sh -n install.sh`.
  - Build and run a minimal repository-owned Docker fixture.
  - Remove only the smoke-test checkout and image.

## Phase 3 — Resilient DNS

### Pi-hole role

- Run hardware, OS, architecture, static-address, clock, storage, and RAM assertions before installation.
- Fail unsupported Pi 1 hardware rather than forcing installation below current Pi-hole requirements.
- Clone the official Pi-hole repository at `v6.4.3`, verify the resolved tag, and run its installer noninteractively.
- Back up existing `/etc/pihole` configuration before first Ansible ownership.
- Render `/etc/pihole/pihole.toml` from shared group variables plus host identity, with Vaulted password hashes under `no_log`.
- Manage local A/CNAME records through the TOML DNS settings.
- Manage only adlists marked `managed-by-ansible`; preserve manually created lists.
- Compare current and desired managed lists before changing the gravity database, then run gravity only when the managed set changes.
- Deploy through `dns.yml` with `serial: 1`: primary, protocol validation, secondary, protocol validation.
- Never modify router/DHCP settings automatically.

### DNS validation

- Query each resolver directly over UDP and TCP.
- Resolve a configured local name and a public name.
- Verify a known blocked test domain returns the configured blocking result.
- Verify the peer’s shared configuration checksum matches while identity values differ.
- Stop one resolver during an explicitly tagged failover test, query the other, then restore the stopped service.
- Add `docs/runbooks/dns.md` covering router activation, emergency resolvers, rollback, rebuild, and protected configuration restore.

## Phase 4 — K3s baseline

### Prerequisites

`k3s_prereqs` will:

- Assert exactly one server, unique node names, group separation, expected OS/architecture, systemd, CPU, RAM, disk, time, and DNS.
- Map `x86_64` to K3s `amd64`, `aarch64` to `arm64`, and ARMv7 to `armhf`; reject ARMv6.
- Assert LAN, tailnet, cluster, and service CIDRs do not overlap.
- Configure required modules, sysctls, swap policy, and Raspberry Pi cgroup boot arguments.
- Back up boot configuration before modification and reboot only through a notified handler.
- Re-gather facts and rerun assertions after a prerequisite reboot.

### Installation

- Download the pinned K3s release binary appropriate to each architecture.
- Verify it against the release’s published SHA-256 checksum before replacing `/usr/local/bin/k3s`.
- Manage systemd units directly rather than piping the online installer into a shell.
- Render `/etc/rancher/k3s/config.yaml` with root-only permissions.

Server configuration includes:

- LAN `node-ip`, `advertise-address`, and `tls-san`
- `cluster-cidr`, `service-cidr`, data directory, and `write-kubeconfig-mode: "0600"`
- An explicitly empty disabled-component list
- SQLite/default single-server datastore

Agent configuration includes:

- LAN server URL
- Root-only persisted token
- node name, LAN address, declared labels, and optional taints

### Token flow

1. Converge and validate the server.
2. Read `/var/lib/rancher/k3s/server/node-token` with privilege and `no_log`.
3. Store it as a non-cacheable in-memory fact on the server host.
4. Render root-only agent configuration under `no_log`.
5. Never place the token in inventory, controller artifacts, logs, documentation, or persistent fact caches.

### Baseline validation

- Confirm server and agent services are enabled and active.
- Query the API from the ThinkPad.
- Require exactly the ThinkPad and two Pi 3 nodes.
- Assert node Ready state, OS, architecture, labels, and exclusions.
- Create one disposable BusyBox Job per baseline node, explicitly selecting that node.
- Require successful completion and delete all validation resources in an `always` block.
- Keep controlled reboot validation behind `k3s_reboot_test_enabled=true` and a dedicated Make target.
- Fetch kubeconfig only when `k3s_fetch_kubeconfig=true`, with destination, endpoint, TLS SAN, and mode validated first.
- Add `docs/runbooks/k3s-recovery.md` covering state, token, kubeconfig, node removal, rebuild order, and version upgrades.

## Test cases and acceptance scenarios

### Static and isolated tests

- Every YAML file passes YAML and Ansible lint.
- Every playbook passes syntax check against example inventory.
- Inventory graph has the required overlaps and exclusions.
- No host is both K3s server and worker.
- The Pi 2 is present only in `pihole_nodes` and absent from every K3s group.
- Pi 1 and ThinkCentre hosts never appear in K3s groups.
- CIDR helpers correctly detect contained, adjacent, IPv4/IPv6, and overlapping networks.
- Role argument specifications reject missing, malformed, or contradictory inputs.
- Secret scanning rejects token-, kubeconfig-, private-key-, and password-like values outside encrypted/fixture paths.
- Templates render without secrets appearing in task output.

### Live acceptance

- Base and storage roles have zero unexplained changes on a second run.
- MacBook reaches ThinkPad and ThinkCentre through Tailscale.
- ThinkPad reaches all Linux nodes through LAN SSH.
- Dotfiles rerun unchanged when `main` has not moved and records a new revision when it has.
- ThinkCentre clones, validates, builds, and runs the smoke fixture; Codex version and login status are visible.
- The Pi 2 resolves directly; after a second resolver is added, the pair
  survives the tagged one-node failover test.
- ThinkPad and both Pi 3 workers return Ready after controlled reboot.
- K3s workload validation succeeds on `amd64` and both `arm64` workers.
- A second K3s run does not reinstall binaries, rotate tokens, rewrite configs, restart services, or touch the Pi 2.
- Repository history and generated documentation contain no sensitive values.

## Rollout order

1. Implement tooling, examples, tests, README, and runbooks.
2. Initialize local production inventory and Vault; collect facts only.
3. Bootstrap and validate the ThinkPad infrastructure profile.
4. Apply base/storage/firewall one host at a time with recovery access confirmed.
5. Configure Tailscale, then verify both LAN and tailnet access before SSH hardening.
6. Apply workstation packages and Stow-managed dotfiles.
7. Configure and smoke-test the ThinkCentre.
8. Provision and validate Pi-hole on the Pi 2; add and validate a second
   supported resolver later; change router DNS only through the runbook.
9. Install K3s server, then supported workers, then baseline validation.
10. Run idempotency and controlled reboot acceptance.

## Documentation updates

- Replace the empty README with prerequisites, inventory initialization, Vault setup, Make targets, phase execution, recovery links, and safety warnings.
- Add ADRs recording Vault, Tailscale/OpenSSH, dotfiles/package ownership, Docker Engine risk, Pi-hole placement, and K3s defaults.
- Update both specification documents and `docs/homelab-plan.html` with the resolved decisions, actual version pins, dotfiles branch policy, and Phase 0–4 status.
- Record that package installation in the dotfiles repository is deprecated and ignored by this automation.
