# Open homelab decisions

- Status: active backlog
- Last consolidated: 2026-07-28

This is the canonical list of operator decisions that remain open. Accepted
architecture decisions are not repeated here.

## Phase 0 facts and recovery

| Decision or input | Required outcome | Blocks |
| --- | --- | --- |
| Record actual hardware, RAM, disks, current OS, desired rebuild image, hostname, and recovery media for every node | A reviewed fact sheet and matching production inventory | Trustworthy rebuilds and destructive-storage safeguards |
| Record the real LAN subnet, reservations, local domain, router/DHCP capabilities, current DNS values, and emergency resolver path | Inventory variables plus a tested router rollback procedure | Production inventory, DNS activation, and network-overlap validation |

## DNS hardware and policy

| Decision or input | Required outcome | Blocks |
| --- | --- | --- |
| Select a second supported resolver | Record architecture, RAM, storage, wired interface, address, power source, and expected uptime | Redundant DNS |
| Confirm IPv4 DHCP option 6 and IPv6 RA/DHCPv6 behavior | Prove two filtered resolver addresses can be advertised without an unfiltered IPv6 bypass | Router cutover |
| Choose the common upstream policy | Provider resolvers or local Unbound, DNSSEC behavior, and intentional upstream diversity | Final Pi-hole configuration |
| Choose local DNS policy | Local records, lists, privacy level, retention, and web UI requirement | Final Pi-hole configuration |
| Choose a disposition for the two 256 MB Pi 1 boards | Prefer a GPIO sensor/display or lab-only ARMv6 target; otherwise retain powered off or retire | Hardware inventory closure |

## Access and configuration promotion

| Decision or input | Required outcome | Blocks |
| --- | --- | --- |
| Finalize Tailscale ACLs | Rules, tag ownership, auth-key expiry, and revocation procedure | Production tailnet policy |
| Define immutable dotfiles promotion | How a tested commit becomes the stable rebuild revision | Reproducible user configuration |

## Stateful services and durability

| Decision or input | Required outcome | Blocks |
| --- | --- | --- |
| Select required databases | Products, image/version pins, ports, resource budgets, data ownership, credentials, and health checks | Phase 5 data platform |
| Select the pipeline orchestrator | Product, execution model, state, credentials, and recovery expectations | Phase 5 pipeline platform |
| Choose backup architecture | Repository target, retention, encryption, off-machine/off-site copy, and clean-location restore test | Stateful production services |
| Decide the ThinkCentre non-Git work policy | Encrypted backup, trusted synchronization, or a strict prohibition on unique local work | Execution-node durability |
| Select observability and notifications | Monitoring target, alert ownership, and destination | Phase 6 operations |

## Settled and removed from this backlog

- Both Pi 1 boards have 256 MB RAM and are excluded from Pi-hole and managed
  inventory.
- The Pi 2 is the single dedicated Pi-hole host and is not a K3s worker.
- The MacBook is the Ansible controller.
- The remote macOS installer bootstraps Homebrew and the checkout; local
  bootstrap then installs uv, uv-managed Python 3.14, and uv-tool Ansible.
  Ansible is not a Homebrew package.
- Linux initial bootstrap installs global uv, per-user uv-managed Python 3.14,
  and a per-user global 3.14 pin; system Python executes Ansible modules.
- Ansible Vault, strict OpenSSH host-key checking, Tailscale SSH exclusion,
  tagged unattended nodes, Docker placement, bare-metal Pi-hole, the K3s
  SQLite/control-plane shape, and the no-GitOps baseline are accepted.

See the numbered records in this directory for the rationale behind settled
decisions.
