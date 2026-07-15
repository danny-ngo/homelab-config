# Homelab configuration

Safe, inventory-driven Ansible automation for the Phase 0–4 homelab baseline.

`./bootstrap.sh` is the single public bootstrap entry point. It detects macOS,
Debian-family Linux, or Arch-family Linux, prepares the local Python 3.12
Ansible environment through the matching module under `bootstrap/platforms/`,
and dispatches a machine profile under `bootstrap/profiles/` to its Ansible
playbook. The internal scripts are implementation details and are not intended
to be invoked directly.

macOS defaults to `workstation`, and Arch/CachyOS defaults to
`execution-node`. Debian requires an explicit profile because this fleet uses
Debian-family systems for several responsibilities:

```sh
./bootstrap.sh --profile infra                 # stable ThinkPad infra plays
./bootstrap.sh --profile execution-node        # ThinkCentre configuration
./bootstrap.sh --profile pihole --limit pihole1
./bootstrap.sh --profile k3s-worker --limit pi3a
./bootstrap.sh --prepare-only                   # tooling only, used by CI
./bootstrap.sh --profile infra --check          # Ansible check mode
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

The ThinkPad is modeled as the persistent infrastructure host and K3s server.
It can run Ansible, but neither its inventory membership nor bootstrap flow
makes it the mandatory controller; the same public entry point can be run from
any supported operator machine.

Node, Go, and Rust are managed exclusively by Ansible through each user’s
global `mise` configuration (`~/.config/mise/config.toml`).

Use `make check PLAYBOOK=... LIMIT=host` before `make apply`. Password SSH remains enabled until both recovery flags are explicitly true. Router/DHCP changes, experimental Pi 2 admission, destructive storage, and K3s reboot testing are intentionally opt-in. Docker group membership is root-equivalent. See [DNS runbook](docs/runbooks/dns.md) and [K3s recovery](docs/runbooks/k3s-recovery.md).
