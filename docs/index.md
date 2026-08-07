---
layout: default
title: Homelab configuration documentation
---

# Homelab configuration

Architecture decisions, installation guides, and operations runbooks for a
rebuildable, inventory-driven homelab. The repository uses a MacBook as its
Ansible controller and manages a mixed Linux fleet with narrowly scoped roles.

> Examples use documentation addresses and obvious placeholders. Production
> addresses, credentials, enrollment keys, password hashes, and monitoring
> endpoints belong in the encrypted production inventory and must never be
> committed or published.

## Start here

- [Homelab plan and interactive architecture overview](homelab-plan.html)
- [Bootstrap Python, Ansible, and uv flow](bootstrap-python-flow.md)
- [Open homelab decisions](decisions/open-decisions.md)
- [Repository source and primary usage guide](https://github.com/danny-ngo/homelab-config)

## Operations runbooks

- [DNS operations](runbooks/dns.md)
- [K3s administration and recovery](runbooks/k3s-recovery.md)
- [Raspberry Pi 1 reachability probe and service sentinel](runbooks/pi1-edge-services.md)
- [ThinkCentre workspace durability](runbooks/thinkcentre-workspaces.md)

## Installation and maintenance guides

- [ThinkCentre Arch and CachyOS installation](thinkcentre-arch-cachyos-install.html)
- [ThinkCentre Arch and CachyOS maintenance](thinkcentre-arch-cachyos-maintenance.html)

## Architecture decisions

- [Vault and access](decisions/0001-vault-and-access.md)
- [Raspberry Pi DNS and constrained edge nodes](decisions/0002-edge-node-architecture.md)
- [Python, Ansible, and uv bootstrap ownership](decisions/0003-python-ansible-uv-bootstrap.md)

## Related handoff

- [Make the dotfiles repository configuration-only](dotfiles-config-only-handoff.md)
