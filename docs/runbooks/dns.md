# DNS operations

## Deployment status

Both Raspberry Pi 1 boards are confirmed to have 256 MB RAM, below Pi-hole's
supported 512 MB minimum. They are intentionally absent from managed inventory,
and the role's memory guard must not be lowered. DietPi's smaller base system
does not change this limit.

The 1 GB Raspberry Pi 2 is the selected single dedicated Pi-hole node. It is in
`pihole_nodes`, excluded from every K3s worker group, and must not run a K3s
agent. Before deployment, replace the example address and upstreams, confirm
the wired interface name, and add `pi2`'s web password hash to the encrypted
production vault.

Keep router/DHCP DNS unchanged until the Pi 2 passes direct validation. A
single resolver is not redundant, so retain the documented emergency resolver
path and select a second independently powered, always-on host with at least
512 MB RAM and a wired network interface. Add it to production inventory only
after recording its architecture, memory, storage, address, interface, and
upstream policy. See
[edge-node architecture decision](../decisions/0002-edge-node-architecture.md)
for the expanded Raspberry Pi OS/DietPi comparison and
[open homelab decisions](../decisions/open-decisions.md) for the remaining
operator inputs.

## Deployment and validation

The commands below use `pi2` as the selected first resolver. Keep router/DHCP
DNS unchanged until it has passed direct UDP and TCP queries, and record the
current router DNS values before any cutover. Add the second resolver
sequentially later and validate both before advertising a redundant pair.

## Deploy and validate

Deploy one resolver at a time so a broken change cannot remove both DNS paths:

```sh
make check PLAYBOOK=ansible/playbooks/dns.yml LIMIT=pi2
make dns LIMIT=pi2
dig @192.0.2.33 example.com A
dig +tcp @192.0.2.33 example.com A
```

Replace documentation addresses and `example.com` with production addresses,
a known public name, and a configured local name. Expected results are a
successful response over both transports and the intended local answer. Confirm
the Pi-hole service and port before router cutover:

```sh
ssh pi2 'sudo systemctl --no-pager --full status pihole-FTL'
ssh pi2 'sudo ss -lntup | grep ":53"'
```

Configure the router to advertise both resolver addresses only after both pass.
Renew one test client's DHCP lease and verify that it received both addresses.
Do not add a public resolver to the DHCP list; that creates an unfiltered bypass.
Clients control ordering, balancing, and retry behavior when DHCP supplies
multiple DNS servers, so test through a representative sample of clients.

Stop `pihole-FTL` on one resolver, query directly through the other, then test
normal name resolution from at least one DHCP client before immediately
restarting the stopped service:

```sh
ssh pi2 'sudo systemctl stop pihole-FTL'
dig @SECONDARY_PIHOLE_ADDRESS example.com A
dig example.com A
ssh pi2 'sudo systemctl start pihole-FTL'
```

Repeat with the other node during a maintenance window. This proves redundant
resolver discovery and actual client retry behavior; it is not a keepalived
floating-IP cluster.

## Roll back a bad deployment

1. Leave the healthy peer running and remove the failed resolver from DHCP if
   clients are experiencing delays.
2. Inspect `journalctl -u pihole-FTL` and validate `pihole.toml` ownership and
   mode before changing configuration.
3. Restore the pre-Ansible `/etc/pihole` backup for that host, then restart
   `pihole-FTL` and repeat direct UDP/TCP tests.
4. If neither resolver works, restore the recorded emergency resolvers in the
   router/DHCP configuration. Renew a client lease and verify public resolution.

Never publish a Pi-hole web password hash, the Vault password, or production
local-DNS data in an incident report.

Treat Ansible inventory as the source of truth for upstreams and local records.
Do not make independent persistent configuration changes in one Pi-hole web UI.
Query history is intentionally local and is not synchronized between nodes.

## Rebuild a resolver

Reimage only one node at a time. Restore its original static DHCP reservation,
verify its SSH fingerprint from the console, update `known_hosts`, and apply the
base playbook before the DNS playbook. Validate it directly while clients still
use the surviving peer. Add the rebuilt resolver back to DHCP only after the
same UDP, TCP, local-name, and public-name checks pass.
