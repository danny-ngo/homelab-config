---
layout: default
title: DNS operations
---

# DNS operations

## Deployment status

Both Raspberry Pi 1 boards are confirmed to have 256 MB RAM, below Pi-hole's
supported 512 MB minimum. They are absent from the standard managed-node
baseline and appear only in the purpose-specific `pi1_edge_nodes` inventory
groups. The role's memory guard must not be lowered. DietPi's smaller base
system does not change this limit.

The 1 GB Raspberry Pi 2 is the selected single dedicated Pi-hole node,
Tailscale endpoint, and Wake-on-LAN sender. The current automation places it in
`pihole_nodes` and applies the bare-metal Pi-hole, Tailscale, and WoL roles.
Tailscale currently provides the authenticated network path for SSH and fixed
local wake commands. Remote filtered DNS is an approved but deferred extension
until the listener, host-firewall, and tailnet-policy gates below are
implemented. These are supporting edge services, not permission to place
unrelated workloads on the resolver. A worker-only K3s deployment is feasible,
but do not move it into the K3s group until the Pi-hole workload defines
persistence, DNS port exposure, measured resource limits, and exclusive node
placement. Before deploying the current baseline, replace the example address,
upstreams, wired MAC addresses, and broadcast address; confirm the wired
interface name; and add `pi2`'s web password hash and Tailscale enrollment
credential to the encrypted production vault.

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

## Plan filtered DNS over Tailscale

This deferred design uses direct tailnet DNS; it does not require the Pi 2 to
advertise the home LAN as a subnet route. Do not enable it until every gate in
this section is implemented and reviewed. Enroll the Pi 2 with a dedicated tag
and ensure its Tailscale preferences include:

```sh
sudo tailscale set --accept-dns=false
tailscale ip -4
```

`accept-dns=false` prevents the resolver from depending on the tailnet DNS
service that it supplies. Record its stable `100.x.y.z` address without
committing credentials or production addresses to the example inventory.

The current Pi-hole template selects `eth0` and `LOCAL`. Before enabling
tailnet DNS, extend the role so Pi-hole v6 uses `dns.listeningMode = "ALL"` for
this host. `LOCAL` rejects requests from remote Tailscale peers because their
addresses are not part of the Pi's local subnet. `ALL` must be paired with:

- host-firewall permission for TCP and UDP port 53 from the wired LAN;
- permission for TCP and UDP port 53 on `tailscale0`;
- tailnet policy granting DNS only to the intended users or devices;
- no ISP-gateway port forward for port 53; and
- a strong protected Pi-hole web password.

Do not expose the web interface merely to make DNS work. Web administration
over Tailscale should receive its own explicit policy if it is desired.

In the Tailscale admin console, open **DNS**, add the Pi 2 Tailscale address as
a custom global nameserver, and enable **Override DNS servers**. Every tailnet
client that accepts Tailscale DNS will use it, not only mobile devices. Keep
Tailscale connected on the phone while away from home; an exit node is not
required because only DNS needs to travel home.

Validate on mobile data rather than home Wi-Fi:

1. Confirm the phone is connected to Tailscale.
2. Resolve a known public domain and a domain on the configured blocklist.
3. Confirm the request reaches Pi-hole and the blocked answer matches policy.
4. Confirm ordinary browsing still works.
5. Disconnect Tailscale and confirm the phone returns to its normal network
   resolver.

Apps using their own DNS-over-HTTPS, Android Private DNS, browser Secure DNS,
or iCloud Private Relay may bypass DNS-level filtering. DNS filtering also
cannot reliably remove ads delivered from the same domains as desired content.

If the Pi 2 or home Internet is unavailable, clients configured to use it lose
tailnet DNS. Do not add a public resolver as a secondary nameserver because
clients can use it while Pi-hole is healthy. Add a second filtered resolver
before claiming remote DNS availability.

References:

- [Tailscale Pi-hole remote DNS guide](https://tailscale.com/docs/solutions/block-ads-all-devices-anywhere-using-raspberry-pi)
- [Pi-hole v6 listening modes](https://docs.pi-hole.net/ftldns/configfile/#listeningmode)

## Use the Pi 2 as the WoL sender

Pi 2 sends the LAN broadcast itself, so remote WoL needs neither a Pi 1 hop nor
a subnet router:

```text
remote phone or laptop
  └─ Tailscale → pi2 fixed SSH command → LAN WoL broadcast
```

Configure the production `pi2` host with the wired target MAC addresses and
LAN broadcast:

```yaml
pihole_nodes:
  hosts:
    pi2:
      wol_targets:
        - name: thinkpad
          mac_address: THINKPAD_WIRED_MAC
          broadcast_address: LAN_BROADCAST_ADDRESS
        - name: thinkcentre
          mac_address: THINKCENTRE_WIRED_MAC
          broadcast_address: LAN_BROADCAST_ADDRESS
```

The role installs `wakeonlan` and fixed commands that send three packets one
second apart by default. Invoke them from an authorized OpenSSH client:

```sh
ssh homelab@pi2 /usr/local/bin/wake-thinkcentre
ssh homelab@pi2 /usr/local/bin/wake-thinkpad
```

Restrict tailnet SSH policy to the intended operator identities. The commands
do not require root, and the Pi 2 does not expose an HTTP or message-broker
wrapper for WoL.

Subnet routing is optional and unnecessary for WoL. Enable it only when remote
clients need direct access to additional LAN services. If selected, advertise
the recorded production LAN CIDR, approve it in the Tailscale console, keep
the default subnet-route SNAT, and add narrowly scoped tailnet policy. Do not
configure an exit node or an ISP-gateway port forward for this use case.

WoL cannot recover a target whose AC power is disconnected. Enable magic-packet
wake in target firmware and Linux network configuration, verify Ethernet link
remains present after shutdown, and test each fixed command from the LAN before
depending on remote access.

## Monitor from the Pi 1 sentinel

Keep the availability monitor off the resolver. `pi1sentinel` directly queries
the Pi 2 address over UDP and TCP DNS, asks for a stable public A record, and
checks the web interface as a secondary HTTP signal. `pi1probe` may ping Pi 2
as a reachability hint, but a successful ping does not prove Pi-hole can answer
a query. The sentinel publishes outcomes to Healthchecks and stores no history
locally.

See [Pi 1 edge services](pi1-edge-services.md) for inventory, deployment,
storage assignment, and controlled failure tests.

Pulse can monitor the bare-metal Pi through its ARMv7 unified Linux agent if
host resource history is useful. Install the agent only from the command
generated by the chosen Pulse server and leave command execution disabled
unless reviewed remote actions are explicitly required.

Portainer on another node can manage a standalone Docker Pi-hole through its
ARMv7 Agent or Edge Agent. Prefer the Edge Agent when avoiding an inbound port
on the Pi is important; the standard Agent requires the Portainer server to
reach the Pi on port 9001. If Pi-hole runs in K3s, add the Kubernetes cluster to
Portainer once and inspect the pod there. K3s uses containerd, so do not install
Docker on the Pi solely to make it a standalone Portainer environment.
Portainer supplies container and workload state, logs, and lifecycle controls;
it does not replace the end-to-end DNS monitor.

Test alerts before relying on them: stop `pihole-FTL` briefly during a
maintenance window, confirm that the remote DNS monitor alarms, restart the
service, and confirm recovery. Monitoring the web UI alone is insufficient.

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
