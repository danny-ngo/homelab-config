# Homelab configuration

Safe, inventory-driven Ansible automation for the Phase 0–4 homelab baseline.

[Browse the rendered documentation](https://danny-ngo.github.io/homelab-config/),
including architecture decisions, installation guides, and operations runbooks.

`install.sh` is the standalone remote entry point for a fresh machine. On
macOS, it installs Homebrew and Git when needed, creates `~/src` by default,
lets `git clone` create a persistent `~/src/homelab-config` checkout, and runs
the controller bootstrap from that checkout. On Linux, it downloads a temporary
repository archive and runs managed-node preparation without retaining a
checkout:

```sh
curl -fsSL https://raw.githubusercontent.com/danny-ngo/homelab-config/main/install.sh | bash
```

Set `HOMELAB_CONFIG_PARENT` on the receiving shell to choose a different macOS
parent directory; Git still names the checkout `homelab-config`:

```sh
curl -fsSL https://raw.githubusercontent.com/danny-ngo/homelab-config/main/install.sh \
  | HOMELAB_CONFIG_PARENT="$HOME/Developer/Homelab" bash
```

An existing checkout with the expected origin is reused without pulling,
resetting, or replacing local changes. After installation, run
`cd ~/src/homelab-config` to enter the checkout; an installer's `cd` cannot
change the calling shell's working directory.

Within a checkout, `./bootstrap.sh` is the local operation entry point. It
detects macOS, Debian-family Linux, or Arch-family Linux and prepares the
current machine through the matching module under `bootstrap/platforms/`. Only
macOS dispatches profiles under `bootstrap/profiles/`; Linux initial bootstrap
installs the managed-node prerequisites and stops. The internal scripts are
implementation details and are not intended to be invoked directly.

The MacBook is the Ansible controller. On a fresh Mac, the remote installer
owns the pre-checkout prerequisites: Homebrew and, only when no Git command is
available afterward, Homebrew Git. The checkout bootstrap installs uv with
Homebrew, installs a uv-managed Python 3.14, and installs
`ansible-core==2.20.7` into uv's user-global tool environment. Operational
Ansible does not use macOS's system Python or the repository virtual
environment. Ansible is not present in the Brewfile.

Run the same remote installer locally on every fresh Linux node except the
ARMv6 Pi 1 boards:

```sh
curl -fsSL https://raw.githubusercontent.com/danny-ngo/homelab-config/main/install.sh | bash
```

It downloads a temporary source archive and makes
`./bootstrap.sh --prepare-only` an internal handoff. That installs a
machine-global `uv` executable, a per-user uv-managed Python 3.14, and
`uv python pin --global 3.14`. It does not retain a checkout, install Ansible,
or run a playbook. Then apply profiles from the MacBook checkout:

Prepare Pi 1 boards through their documented Raspberry Pi OS exception instead
of this installer; see the Pi 1 runbook linked below.

```sh
./bootstrap.sh                                  # bootstrap/apply the Mac workstation
./bootstrap.sh --profile infra                  # stable ThinkPad infra plays
./bootstrap.sh --profile execution-node         # ThinkCentre configuration
./bootstrap.sh --profile pihole --limit pi2
./bootstrap.sh --profile k3s-worker --limit pi3a
./bootstrap.sh --profile pi1-sentinel --limit pi1sentinel
./bootstrap.sh --profile pi1-probe --limit pi1probe
./bootstrap.sh --profile infra --check           # Ansible check mode
./bootstrap.sh --prepare-only                    # controller tooling only
```

Profiles use safe inventory-group limits unless `--limit` is supplied. On the
first run, bootstrap copies the example inventory and stops; replace every
documentation address and fake key before rerunning. Create and encrypt
`ansible/inventories/production/group_vars/all/vault.yml`, and provide its
password only via `ANSIBLE_VAULT_PASSWORD_FILE`.

Strict SSH host-key checking stays enabled. Before the first Ansible run, verify
each host's SSH fingerprint through the console or another trusted channel and
add it to `~/.ssh/known_hosts`. For a disposable first-use environment, you can
temporarily set `ANSIBLE_SSH_ARGS='-o StrictHostKeyChecking=accept-new'`; review
the accepted fingerprints immediately afterward and do not use this shortcut
when a host identity should already be known.

The Linux baseline also exports Ghostty's `xterm-ghostty` entry from the
MacBook controller and compiles it into the SSH user's `~/.terminfo` on each
managed host. This is the persistent, Ansible-managed equivalent of piping
`infocmp` through a separate SSH command. For unmanaged hosts, Ghostty 1.3 and
newer can instead install the entry on interactive connections when
`ssh-terminfo` is added to `shell-integration-features`; that shell wrapper
does not apply to Ansible or other non-interactive SSH callers.

The ThinkPad is modeled as the persistent infrastructure host and K3s server,
not as a second controller. The MacBook applies and recovers all managed-node
profiles. Helm follows the same boundary: use its CLI from the MacBook or
explicit automation with a protected kubeconfig; installing the CLI on the
ThinkPad is optional break-glass tooling, not a cluster requirement. See
[K3s Helm administration and recovery](docs/runbooks/k3s-recovery.md).

Bootstrap keeps controller, development, and managed-node Python
responsibilities separate:

- uv's global tool environment contains the operational Ansible CLI and uses
  uv-managed Python 3.14;
- the checkout-local `.venv` is a locked Python 3.14 environment for lint,
  syntax checks, filters, and tests; and
- each Linux target has a global uv executable plus a per-user uv-managed
  Python 3.14/global pin, while its distribution-owned `/usr/bin/python3`
  executes Ansible modules. The ARMv6 Pi 1 roles are a documented exception:
  they use only distribution Python and do not run the standard Linux
  bootstrap.

The repository environment is declared by `pyproject.toml`, resolved in the
committed `uv.lock`, and recreated with:

```sh
uv venv --clear --managed-python --python 3.14 .venv
uv sync --frozen --managed-python --python 3.14
```

Debian 13's default `python3` package is Python 3.13, but minimal images are not
assumed to include it, so bootstrap installs it explicitly. Arch's minimal
`base` package does not include Python; bootstrap installs the rolling
distribution's `python` package, currently Python 3.14. The distribution
`ansible` package is never installed. Inventory selects `/usr/bin/python3` for
Linux modules and Ansible's uv-tool Python for the local Mac.

See the [detailed bootstrap flow](docs/bootstrap-python-flow.md) and
[Python, Ansible, and uv ownership decision](docs/decisions/0003-python-ansible-uv-bootstrap.md).

Node 24, Go, and Rust are managed exclusively by Ansible through each user’s
global `mise` configuration (`~/.config/mise/config.toml`). The execution node
also installs Herdr through that configuration. Workstation and execution-node
profiles install Codex CLI and OpenCode; the execution-node profile runs T3
Code headlessly behind Tailscale Serve.

Deployment form is selected per service; there is no VM layer without a
specific isolation requirement. T3 Code runs bare metal on the always-on
ThinkCentre, while databases are planned as Docker containers on the ThinkPad
with explicit persistent paths and backups. Project source on the ThinkCentre
must be committed and pushed to GitHub at frequent checkpoints so the execution
node remains rebuildable. See
[ThinkCentre workspace durability](docs/runbooks/thinkcentre-workspaces.md).

The ThinkPad uses Debian 13's native `docker.io`, `docker-cli`, and
`docker-compose` packages. Docker's separate APT repository is deliberately not
configured; it is required only if the host switches to Docker CE packages such
as `docker-ce` and `docker-ce-cli`.

Package changes are reviewed in `ansible/packages/`: macOS workstations use the
tracked `macos/Brewfile`, while the Linux manifest is applied only to the
ThinkPad infrastructure host and ThinkCentre execution node. Raspberry Pi
packages remain owned by their purpose-specific roles. Initial bootstrap owns
only the packages needed before Ansible can run. Tailscale and firewall
packages are installed by the roles that configure them; Stow belongs to the
dotfiles flow (the Linux dotfiles role or the macOS Brewfile).

Both Raspberry Pi 1 A+ boards are confirmed to have 256 MB RAM and remain
excluded from Pi-hole, K3s, and the standard managed-node baseline. They have
purpose-specific ARMv6 roles instead: the 8 GB `pi1probe` publishes host and
self heartbeats to Healthchecks.io after successful pings, while the 32 GB
`pi1sentinel` independently verifies the Pi 2's DNS over UDP and TCP plus its
Pi-hole HTTP endpoint. Neither stores monitoring history locally. Their
`pi1_edge_nodes` inventory parent selects distribution `/usr/bin/python3`
without uv. See the
[Pi 1 edge-services runbook](docs/runbooks/pi1-edge-services.md).

The 1 GB Raspberry Pi 2 is reserved for Pi-hole plus its supporting Tailscale
service and fixed Wake-on-LAN commands. Remote operators invoke those commands
directly over the Pi 2's Tailscale connection; no Pi 1 jump hop or subnet route
is required. The Pi 1 boards remain off the tailnet. A worker-only K3s agent
plus the Pi-hole pod is feasible, but the K3s minimum is a pre-workload
baseline, so this is not generous headroom. The current example inventory
remains on the implemented bare-metal path until the container networking,
persistence, resource limits, and node placement are defined. See the
[DNS runbook](docs/runbooks/dns.md) for WoL, validation, and the gated tailnet
DNS and firewall design.

The Pi 1 sentinel performs the lightweight independent availability checks;
it is not a monitoring control plane. Portainer on another node can manage a
standalone Docker deployment through an ARMv7 Agent or Edge Agent. For K3s,
connect Portainer once to the Kubernetes cluster and observe the Pi-hole
workload there; K3s uses containerd, so the Pi 2 is not a standalone Docker
endpoint. Add a second supported resolver later before claiming DNS
redundancy. See
[edge-node architecture decision](docs/decisions/0002-edge-node-architecture.md).

The remaining operator choices are consolidated in
[Open homelab decisions](docs/decisions/open-decisions.md).

Use `make check PLAYBOOK=... LIMIT=host` before `make apply`. Password SSH remains enabled until both recovery flags are explicitly true. Router/DHCP changes, destructive storage, and K3s reboot testing are intentionally opt-in. Rootful Docker and root-equivalent `docker` group access are accepted for the trusted ThinkCentre execution account. See the [DNS runbook](docs/runbooks/dns.md), [K3s recovery](docs/runbooks/k3s-recovery.md), and [Pi 1 edge-services runbook](docs/runbooks/pi1-edge-services.md).
