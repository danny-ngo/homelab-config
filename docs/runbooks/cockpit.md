---
layout: default
title: Cockpit over Tailscale
---

# Cockpit over Tailscale

`ansible/playbooks/cockpit.yml` targets `non_raspberry_pi_linux`: the Arch/CachyOS
execution node and Debian infrastructure host. Raspberry Pi groups and macOS
are excluded. It installs the distribution's `cockpit` package and enables and
starts `cockpit.socket`; systemd starts the web service on demand.

The full `site.yml` run invokes this playbook after the infrastructure and
execution roles enroll their hosts in Tailscale. For an existing enrolled host:

```sh
make check PLAYBOOK=ansible/playbooks/cockpit.yml LIMIT=thinkcentre
make apply PLAYBOOK=ansible/playbooks/cockpit.yml LIMIT=thinkcentre
```

Replace `thinkcentre` with `thinkpad` for the Debian infrastructure host. These
are inventory names; the production ThinkCentre currently connects as JARVIS.
The focused playbook also ensures the distribution firewall package is present.

## Inventory settings

Set individual management-device Tailscale IPv4 addresses in
`ansible/inventories/production/group_vars/non_raspberry_pi_linux/main.yml`:

```yaml
cockpit_allowed_clients: [REPLACE_WITH_MAC_TAILSCALE_IPV4]
```

The private production inventory contains the management Mac's current address.
The tracked example inventory uses a placeholder that must be replaced. Empty lists, LAN addresses, IPv6
addresses, and CIDR ranges are rejected. The server address is discovered from
the `tailscale0` interface on each node; no Debian address needs to be guessed.
You can override `cockpit_tailscale_address` with an individual Tailscale IPv4
address, for example when reviewing a fresh-host check run before enrollment.
Check mode skips firewall rules if that address is not yet available. A real
apply requires enrollment or an explicit server address.

## Firewall behavior

On Arch, the firewall role adds a firewalld rich rule in both runtime and
permanent configuration, without a global reload. Its default zone is `public`;
set `cockpit_firewalld_zone` if another zone handles Tailscale traffic. For
JARVIS, the generated rule matches the manually configured rule:

```text
rule family=ipv4 source address=MAC_TAILSCALE_IPV4/32 destination address=SERVER_TAILSCALE_IPV4/32 service name=cockpit accept
```

On Debian, it adds the equivalent UFW TCP 9090 rule restricted to incoming
`tailscale0`, the selected client, and the server's Tailscale address. The
existing baseline does not activate an inactive UFW firewall, and this
playbook preserves that behavior. Review `sudo ufw status verbose` separately
before relying on UFW for isolation. Setting `firewall_enabled: false` skips
rule management; it does not disable an existing firewall or restrict Cockpit.

These tasks do not add a general Cockpit service allowance, trust the entire
Tailscale interface, or change tailnet ACLs. Existing broader allowances remain
in effect. Rules are additive: remove an old rule explicitly from runtime and
permanent firewalld configuration (or UFW) when retiring a client or changing
addresses. Merely removing an address from the variable does not revoke it.

## Connect and verify

With Tailscale connected on the Mac, open
`https://SERVER_TAILSCALE_IPV4:9090`. Find JARVIS's current address with
`tailscale ip -4` on the server.
Sign in with the existing Linux account. No SSH tunnel, local port listener,
router forwarding, or Tailscale Serve configuration is needed.

Cockpit's default certificate may produce a browser certificate warning.
Handle certificate trust interactively, or configure a trusted certificate
separately; this playbook does not disable HTTPS or certificate checking.

`validate.yml` checks that the socket is enabled and active, and that the
configured rules exist (both runtime and permanent on Arch). Browser access
from the management Mac is still the end-to-end check, including tailnet ACLs.
If a connection is refused, inspect firewalld as well as iptables: an ACCEPT
in Tailscale's iptables chain does not override a later firewalld rejection.

Package and socket setup follows the [Cockpit installation guide](https://cockpit-project.org/running.html).
