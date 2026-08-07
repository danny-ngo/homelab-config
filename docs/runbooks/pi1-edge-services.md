---
layout: default
title: Raspberry Pi 1 reachability probe and service sentinel
---

# Raspberry Pi 1 reachability probe and service sentinel

The two 256 MB Raspberry Pi 1 Model A+ boards remain small, stateless LAN
leaves with distinct responsibilities:

- `pi1probe`, using the available 8 GB card, checks whether selected hosts are
  reachable with ICMP and publishes successful target and self heartbeats.
- `pi1sentinel`, using the available 32 GB card, checks whether Pi 2 actually
  answers DNS over UDP and TCP and serves its Pi-hole HTTP endpoint. It
  publishes successful service and self heartbeats.

Healthchecks.io owns missed-heartbeat detection, incident history, recovery,
maintenance pauses, and notifications. Neither Pi stores monitoring history,
runs a dashboard, or triggers Wake-on-LAN automatically. Pi 2 now owns the
fixed WoL commands; see [DNS operations](dns.md).

## Responsibility and failure boundaries

```text
pi1probe (8 GB)
  ├─ ICMP echo → ThinkPad
  ├─ ICMP echo → ThinkCentre
  └─ HTTPS success heartbeats → Healthchecks.io

pi1sentinel (32 GB)
  ├─ UDP DNS query → Pi 2 Pi-hole
  ├─ TCP DNS query → Pi 2 Pi-hole
  ├─ HTTP request → Pi 2 Pi-hole
  └─ HTTPS success heartbeats → Healthchecks.io
```

The probe answers “can this host or LAN path be reached?” A missed ping does
not distinguish a planned shutdown from a disconnected cable, firewall rule,
frozen OS, or power failure. Pause a target's check before planned downtime.

The sentinel answers “does the Pi 2 service work?” A successful Pi 2 ping is
not enough: both DNS transports must return a non-empty A-record answer, and
the configured HTTP URL must return a successful response. The sentinel does
not validate filtered DNS from a remote Tailscale client because its checks
originate on the LAN. Keep the mobile-data acceptance test in the DNS runbook.

Give each board its own power supply and switch port when practical. Both
self-heartbeats are required to distinguish a target failure from loss of the
monitoring leaf, LAN, Internet connection, or Healthchecks itself.

## Storage assignment and write policy

Raspberry Pi OS Lite 32-bit and the small runtime package sets fit on either
card. Use the cards as follows:

| Node | Card | Local payload |
| --- | --- | --- |
| `pi1probe` | 8 GB | Raspberry Pi OS Lite, `iputils-ping`, `curl`, configuration, and bounded system logs |
| `pi1sentinel` | 32 GB | Raspberry Pi OS Lite, `dnsutils`, `curl`, configuration, and bounded system logs |

The probe receives the smaller card because it has the narrower package set
and no planned expansion. The sentinel receives the larger card to leave room
for future GPIO sensor tooling and diagnostics, not because its current role
needs 32 GB. Do not add local time-series databases, packet-capture archives,
or unbounded application logs. Configuration is reproducible from Ansible and
history remains in Healthchecks, so neither SD card needs a file-level backup.

## Prepare Raspberry Pi OS

Use Raspberry Pi Imager to install Raspberry Pi OS Lite 32-bit. Configure the
final hostname, the `homelab` administrator, an SSH public key, and the
`America/Toronto` timezone before first boot. Reserve each USB Ethernet
adapter's address in DHCP.

The Pi 1 A+ has one USB port and no built-in Ethernet. Prefer a supported USB
Ethernet adapter connected to the LAN switch. A project that later needs both
networking and a USB peripheral requires a powered hub.

The standard Linux installer and `bootstrap.sh --prepare-only` must not run on
ARMv6 because uv-managed Python 3.14 is unavailable. Install only distribution
Python for Ansible:

```sh
ssh homelab@PI1_LAN_IP
sudo apt-get update
sudo apt-get install --yes python3
uname -m
/usr/bin/python3 --version
```

`uname -m` must report `armv6l`. Verify each SSH host fingerprint through the
local console, then add it to the MacBook controller's `known_hosts`.

The production inventory must keep both groups outside `linux_nodes`.
`pi1_edge_nodes` selects `/usr/bin/python3` as the documented ARMv6 exception;
it does not inherit the common, storage, firewall, dotfiles, Tailscale, or
language-toolchain roles.

## Configure Healthchecks

Create these checks with a one-minute period and at least a two-minute grace:

- `pi1probe-alive`
- `thinkpad-reachable`
- `thinkcentre-reachable`
- `pi1sentinel-alive`
- `pi2-dns-udp`
- `pi2-dns-tcp`
- `pi2-http`

Attach the selected notification integration. Treat every ping URL as a bearer
secret: anyone who knows one can forge a successful heartbeat. Store the URLs
only in the encrypted production Vault:

```yaml
vault_pi1_probe_healthchecks_urls:
  pi1probe:
    probe: https://hc-ping.com/PROBE_UUID
    thinkpad: https://hc-ping.com/THINKPAD_UUID
    thinkcentre: https://hc-ping.com/THINKCENTRE_UUID

vault_pi1_sentinel_healthchecks_urls:
  pi1sentinel:
    dns_udp: https://hc-ping.com/DNS_UDP_UUID
    dns_tcp: https://hc-ping.com/DNS_TCP_UUID
    http: https://hc-ping.com/HTTP_UUID
    sentinel: https://hc-ping.com/SENTINEL_UUID
```

Edit the Vault without committing plaintext URLs:

```sh
ansible-vault edit ansible/inventories/production/group_vars/all/vault.yml
```

## Configure the reachability probe

Use stable LAN addresses. Monitor intentionally powered-off targets only when
their Healthchecks checks will be paused during planned shutdowns:

```yaml
pi1_probe_nodes:
  hosts:
    pi1probe:
      ansible_host: PI1_PROBE_LAN_IP
      expected_os_family: Debian
      expected_architecture: armv6l
      pi1_probe_boot_media_gb: 8
      pi1_probe_targets:
        - name: thinkpad
          address: THINKPAD_LAN_IP
          healthchecks_url: >-
            {{ vault_pi1_probe_healthchecks_urls[inventory_hostname]['thinkpad'] }}
        - name: thinkcentre
          address: THINKCENTRE_LAN_IP
          healthchecks_url: >-
            {{ vault_pi1_probe_healthchecks_urls[inventory_hostname]['thinkcentre'] }}
      pi1_probe_heartbeat_url: >-
        {{ vault_pi1_probe_healthchecks_urls[inventory_hostname]['probe'] }}
```

Apply and validate:

```sh
./bootstrap.sh --profile pi1-probe --limit pi1probe --check
./bootstrap.sh --profile pi1-probe --limit pi1probe
make validate LIMIT=pi1probe
```

## Configure the service sentinel

Point the DNS checks directly at Pi 2 instead of using the sentinel's default
resolver. Select a stable public query name expected to return an A record. The
HTTP URL may use HTTP on the trusted LAN; Healthchecks publishing always uses
HTTPS.

The sentinel's own name resolution must not depend exclusively on Pi 2.
Configure an independent resolver only for this monitoring leaf so a Pi 2 DNS
failure does not prevent it from publishing its self-heartbeat.

```yaml
pi1_sentinel_nodes:
  hosts:
    pi1sentinel:
      ansible_host: PI1_SENTINEL_LAN_IP
      expected_os_family: Debian
      expected_architecture: armv6l
      pi1_sentinel_boot_media_gb: 32
      pi1_sentinel_dns_server: PI2_LAN_IP
      pi1_sentinel_dns_query_name: example.com
      pi1_sentinel_http_url: http://PI2_LAN_IP/admin/
      pi1_sentinel_healthchecks_urls: >-
        {{ vault_pi1_sentinel_healthchecks_urls[inventory_hostname] }}
```

Apply and validate:

```sh
./bootstrap.sh --profile pi1-sentinel --limit pi1sentinel --check
./bootstrap.sh --profile pi1-sentinel --limit pi1sentinel
make validate LIMIT=pi1sentinel
```

The service runs as the unprivileged `pi1-sentinel` account. Protected
heartbeat URLs live under `/etc/pi1-sentinel`; the program and systemd unit
contain no secrets.

## Operate and test

Inspect services without displaying protected heartbeat files:

```sh
ssh pi1probe \
  'systemctl --no-pager --full status pi1-ping-probe'
ssh pi1sentinel \
  'systemctl --no-pager --full status pi1-service-sentinel'
ssh pi1sentinel \
  'journalctl --unit pi1-service-sentinel --since "30 minutes ago"'
```

Test the reachability path by pausing planned-maintenance alerts, shutting down
one target, waiting through the Healthchecks grace period, and confirming only
that target becomes unavailable. Restore the target with the fixed command now
installed on Pi 2:

```sh
ssh pi2 /usr/local/bin/wake-thinkcentre
```

Test the sentinel during a maintenance window:

1. Confirm all four sentinel checks are up.
2. Stop `pihole-FTL` on Pi 2.
3. Confirm the UDP, TCP, and HTTP checks become late while
   `pi1sentinel-alive` remains up.
4. Restart `pihole-FTL`.
5. Confirm all three service checks recover.
6. Stop the sentinel service briefly and confirm its self-check becomes late.
7. Restart it before the test window grows unexpectedly:

   ```sh
   ssh pi1sentinel \
     'sudo systemctl restart pi1-service-sentinel'
   ```

## Recovery

Both roles are stateless. After an SD-card failure:

1. Reimage Raspberry Pi OS Lite 32-bit onto the assigned card.
2. Restore the hostname, administrator key, and DHCP reservation.
3. Install distribution `python3`.
4. Verify the new SSH host key locally and update `known_hosts`.
5. Reapply the appropriate profile from the MacBook.
6. Repeat its controlled end-to-end test.

References:

- [Raspberry Pi OS documentation](https://www.raspberrypi.com/documentation/computers/os.html)
- [Healthchecks.io documentation](https://healthchecks.io/docs/)
- [Healthchecks notification integrations](https://healthchecks.io/docs/configuring_notifications/)
