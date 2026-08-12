---
layout: default
title: Open homelab decisions
---

# Open homelab decisions

- Status: active backlog
- Last consolidated: 2026-08-12

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
| Choose the Pi 2 deployment form | Select bare metal, standalone Docker, or a dedicated tainted K3s worker; for K3s define the Pi-hole workload, persistence, port 53 exposure, resource limits, and placement | Moving the Pi 2 into the K3s worker group or replacing the current bare-metal role |
| Select a second supported resolver | Record architecture, RAM, storage, wired interface, address, power source, and expected uptime | Redundant DNS |
| Confirm IPv4 DHCP option 6 and IPv6 RA/DHCPv6 behavior | Prove two filtered resolver addresses can be advertised without an unfiltered IPv6 bypass | Router cutover |
| Choose the common upstream policy | Provider resolvers or local Unbound, DNSSEC behavior, and intentional upstream diversity | Final Pi-hole configuration |
| Choose local DNS policy | Local records, lists, privacy level, retention, and web UI requirement | Final Pi-hole configuration |

## Access and configuration promotion

| Decision or input | Required outcome | Blocks |
| --- | --- | --- |
| Complete the Pi 2 tailnet DNS gate | Add an explicit Pi-hole `ALL` listener option, host-firewall rules for TCP/UDP 53 on the wired LAN and `tailscale0`, and tests that keep the web interface private | Enabling remote filtered DNS |
| Finalize Tailscale ACLs | Define Pi 2 tag ownership, remote DNS access on TCP/UDP 53, fixed-command SSH access for WoL, auth-key expiry, and revocation; do not advertise a subnet route unless broader LAN access is deliberately enabled | Production tailnet policy and remote filtered DNS |
| Define immutable dotfiles promotion | How a tested commit becomes the stable rebuild revision | Reproducible user configuration |

## Stateful services and durability

| Decision or input | Required outcome | Blocks |
| --- | --- | --- |
| Select required databases | Products, image/version pins, ports, resource budgets, data ownership, credentials, and health checks | Phase 5 data platform |
| Finalize production deployment identities | Private deployment repository, GitHub-to-Tailscale workload identity, `tag:github-deploy` destination rule, restricted OpenSSH forced command, purpose-scoped K3s identity, credential rotation, and revocation procedure | Automated production deployment |
| Choose backup architecture | Repository target, retention, encryption, off-machine/off-site copy, and clean-location restore test | Stateful production services |
| Decide the ThinkCentre non-Git work policy | Encrypted backup, trusted synchronization, or a strict prohibition on unique local work | Execution-node durability |
| Select observability and notifications | Monitoring target, alert ownership, and destination | Phase 6 operations |

## Settled and removed from this backlog

- Both Pi 1 boards have 256 MB RAM. They are excluded from Pi-hole, K3s, and
  the standard Linux baseline; purpose-specific ARMv6 roles configure a
  32 GB service sentinel and an 8 GB outbound reachability probe.
- The Pi 2 is reserved for Pi-hole and its supporting Tailscale service. It
  sends Wake-on-LAN packets through fixed local commands; subnet routing is
  optional and disabled by default. Remote filtered DNS remains gated on the
  listener, firewall, and tailnet policy above. The Pi-hole deployment form
  remains reopened.
- The MacBook is the Ansible controller.
- GitHub Actions is the CI/CD orchestrator. Portable CI runs on GitHub-hosted
  runners. Production promotion also uses a fresh GitHub-hosted runner, which
  joins the tailnet ephemerally through GitHub OIDC and invokes only a restricted
  OpenSSH forced command on the ThinkPad. Neither the public infrastructure
  repository nor the development-focused ThinkCentre receives a persistent
  production runner. See the
  [development and application deployment workflow](../development-deployment-workflow.md).
- The remote macOS installer bootstraps Homebrew and the checkout; local
  bootstrap then installs uv, uv-managed Python 3.14, and uv-tool Ansible.
  Ansible is not a Homebrew package.
- Linux initial bootstrap installs global uv, per-user uv-managed Python 3.14,
  and a per-user global 3.14 pin; system Python executes Ansible modules.
- Ansible Vault, strict OpenSSH host-key checking, Tailscale SSH exclusion,
  tagged unattended nodes, Docker placement, the current bare-metal Pi-hole
  baseline, the K3s SQLite/control-plane shape, and the no-GitOps baseline are
  accepted.

See the numbered records in this directory for the rationale behind settled
decisions.
