# Raspberry Pi 1 Wake-on-LAN and reachability probe

The two 256 MB Raspberry Pi 1 Model A+ boards have narrow, optional roles:

- `pi1wol` sends fixed Wake-on-LAN magic packets to the ThinkPad and
  ThinkCentre.
- `pi1probe` pings both targets and publishes successful heartbeats to
  Healthchecks.io, which owns missed-heartbeat detection and mobile delivery.

The example inventory assigns one role to each board. One board may belong to
both inventory groups if fewer devices are preferred; the workloads are tiny.
Separate boards provide a cleaner failure boundary but require another SD card,
power supply, and USB network adapter.

Neither role runs a server reachable from the Internet. Wake commands are
invoked over an existing SSH connection, and the probe makes outbound HTTPS
requests only. MQTT, Docker, K3s, uv, and uv-managed Python are deliberately
absent.

## Architecture and limits

```text
MacBook or phone over LAN/VPN
  └─ SSH → pi1wol → UDP magic packet → target wired NIC

pi1probe
  ├─ ICMP echo → ThinkPad
  ├─ ICMP echo → ThinkCentre
  └─ HTTPS success heartbeats → Healthchecks.io
                                  └─ mobile integration
```

A missed ping means **unreachable**, not necessarily powered off. A disconnected
cable, firewall rule, frozen OS, failed switch, or power loss can have the same
result. The probe does not automatically wake a failed machine: alerting and
recovery remain separate so a planned shutdown cannot create a wake loop.

The Pi 1 A+ has one USB port and no built-in Ethernet. Prefer a supported USB
Ethernet adapter connected to the LAN switch. USB Wi-Fi can work, but broadcast
handling and recovery are less predictable. The Pi never plugs directly into a
target computer.

## Prepare Raspberry Pi OS

Use Raspberry Pi Imager to install Raspberry Pi OS Lite 32-bit. Configure the
final hostname, the `homelab` administrator, an SSH public key, and the
`America/Toronto` timezone before first boot. Reserve each network adapter's
address in DHCP.

The standard Linux installer and `bootstrap.sh --prepare-only` must not run on
ARMv6 because uv-managed Python 3.14 is unavailable. Install only the
distribution Python required by Ansible:

```sh
ssh homelab@PI1_LAN_IP
sudo apt-get update
sudo apt-get install --yes python3
uname -m
/usr/bin/python3 --version
```

`uname -m` must report `armv6l`. Verify the SSH host fingerprint through the
local console, then add the verified key to the MacBook controller's
`known_hosts`.

The production inventory must keep both Pi 1 groups outside `linux_nodes`.
`pi1_edge_nodes` selects `/usr/bin/python3` as the documented ARMv6 exception;
it does not inherit the common, storage, firewall, dotfiles, Tailscale, or
language-toolchain roles.

## Configure the Wake-on-LAN targets

Wake-on-LAN must work from an ordinary LAN machine before provisioning the Pi.
For each target:

1. Connect its Wake-on-LAN-capable NIC by Ethernet.
2. Enable Wake-on-LAN in firmware.
3. Disable firmware settings such as ErP or deep sleep if they remove NIC
   standby power.
4. On Linux, run `sudo ethtool INTERFACE` and confirm that magic-packet wake
   mode `g` is supported and enabled. Persist `ethtool -s INTERFACE wol g`
   through the target's network manager when necessary.
5. Shut down the target and verify that the Ethernet link remains active.
6. Test from another machine on the same LAN.

WoL cannot recover a target whose AC power is disconnected. Configure the
ThinkCentre's firmware power-loss policy separately if it must start after an
outage. ThinkPad behaviour can depend on AC power, battery state, dock, and
network adapter.

Replace the example MAC addresses, Pi address, and broadcast addresses in
`ansible/inventories/production/hosts.yml`:

```yaml
pi1_wol_nodes:
  hosts:
    pi1wol:
      ansible_host: PI1_WOL_LAN_IP
      expected_os_family: Debian
      expected_architecture: armv6l
      pi1_wol_targets:
        - name: thinkpad
          mac_address: THINKPAD_WIRED_MAC
          broadcast_address: LAN_BROADCAST_ADDRESS
        - name: thinkcentre
          mac_address: THINKCENTRE_WIRED_MAC
          broadcast_address: LAN_BROADCAST_ADDRESS
```

The role installs `wakeonlan` and fixed commands named after each target. It
sends three packets one second apart by default. The package uses UDP and does
not require root privileges.

Apply and validate:

```sh
./bootstrap.sh --profile pi1-wol --limit pi1wol --check
./bootstrap.sh --profile pi1-wol --limit pi1wol
make validate LIMIT=pi1wol
```

Wake a target from the MacBook:

```sh
ssh pi1wol /usr/local/bin/wake-thinkpad
ssh pi1wol /usr/local/bin/wake-thinkcentre
```

A phone can invoke the same fixed SSH commands while connected to the home LAN
or an independently operated VPN. Do not publish SSH, an HTTP wrapper, or a
message broker directly to the Internet merely to expose these commands.

## Configure Healthchecks and mobile delivery

Create three separate Healthchecks.io checks:

- `pi1probe-alive`
- `thinkpad-reachable`
- `thinkcentre-reachable`

Use a one-minute period and at least a two-minute grace time. The Ansible role's
default probe interval is 60 seconds. Healthchecks controls the late threshold,
incident state, recovery message, maintenance pause, and notification
integration.

Attach the desired phone path to the checks:

- Pushover for a dedicated push-notification client;
- Telegram if it is already an accepted alert channel; or
- email for the smallest setup.

Copy each check's unique ping URL into the encrypted production Vault. The URLs
are bearer secrets: anyone who knows one can forge a successful heartbeat.

```yaml
vault_pi1_probe_healthchecks_urls:
  pi1probe:
    probe: https://hc-ping.com/PROBE_UUID
    thinkpad: https://hc-ping.com/THINKPAD_UUID
    thinkcentre: https://hc-ping.com/THINKCENTRE_UUID
```

Edit and encrypt through Ansible Vault; never commit plaintext URLs:

```sh
ansible-vault edit ansible/inventories/production/group_vars/all/vault.yml
```

Configure the target addresses in production inventory. Each target entry
looks up its URL from the encrypted mapping:

```yaml
pi1_probe_nodes:
  hosts:
    pi1probe:
      ansible_host: PI1_PROBE_LAN_IP
      expected_os_family: Debian
      expected_architecture: armv6l
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

The role installs only `iputils-ping` and `curl`. A hardened systemd service
runs as the unprivileged `pi1-probe` account. The Healthchecks URLs are stored
in group-readable, non-world-readable files under `/etc/pi1-probe`.

## Operate and test

Inspect the local service without displaying its protected URL files:

```sh
ssh pi1probe 'systemctl --no-pager --full status pi1-ping-probe'
ssh pi1probe 'journalctl --unit pi1-ping-probe --since "30 minutes ago"'
```

Perform a controlled end-to-end test:

1. Confirm all three Healthchecks checks are up.
2. Pause unrelated maintenance and shut down one target.
3. Wait through the configured period and grace time.
4. Confirm that only that target alerts.
5. Invoke its Wake-on-LAN command.
6. Confirm the target becomes reachable and a recovery notification arrives.
7. During a separate test, stop `pi1-ping-probe` briefly. All target
   heartbeats and the probe heartbeat should become late.
8. Restart the service before the test window grows unexpectedly:

   ```sh
   ssh pi1probe 'sudo systemctl restart pi1-ping-probe'
   ```

If only one target check becomes late, investigate that target or its network
path. If both target checks and `pi1probe-alive` become late together,
investigate the probe, its power, the switch/router, Internet access, or
Healthchecks itself.

Pause the relevant Healthchecks check before a planned shutdown. Do not shorten
the grace time until several days of normal network jitter have been observed.

## Recovery

Both roles are stateless. After an SD-card failure:

1. Reimage Raspberry Pi OS Lite 32-bit.
2. Restore the hostname, administrator key, and DHCP reservation.
3. Install distribution `python3`.
4. Verify the new SSH host key locally and update `known_hosts`.
5. Reapply the appropriate profile from the MacBook.
6. Repeat the end-to-end test.

Healthchecks owns incident history and notification configuration. Ansible
owns the Pi packages, commands, protected endpoint files, and systemd service.

References:

- [Raspberry Pi OS documentation](https://www.raspberrypi.com/documentation/computers/os.html)
- [Debian wakeonlan package](https://packages.debian.org/stable/wakeonlan)
- [Linux Wake-on-LAN interface](https://docs.kernel.org/networking/ethtool-netlink.html)
- [Healthchecks.io documentation](https://healthchecks.io/docs/)
- [Healthchecks notification integrations](https://healthchecks.io/docs/configuring_notifications/)
- [Pushover message API](https://pushover.net/api)
