# DNS operations

The Pi-hole pair is independent of K3s. Keep router/DHCP DNS unchanged until
both resolvers have passed direct UDP and TCP queries. Record the current router
DNS values before any cutover.

## Deploy and validate

Deploy one resolver at a time so a broken change cannot remove both DNS paths:

```sh
make check PLAYBOOK=ansible/playbooks/dns.yml LIMIT=pihole1
make dns LIMIT=pihole1
dig @192.0.2.21 example.com A
dig +tcp @192.0.2.21 example.com A

make check PLAYBOOK=ansible/playbooks/dns.yml LIMIT=pihole2
make dns LIMIT=pihole2
dig @192.0.2.22 example.com A
dig +tcp @192.0.2.22 example.com A
```

Replace documentation addresses and `example.com` with production addresses,
a known public name, and a configured local name. Expected results are a
successful response over both transports and the intended local answer. Confirm
the Pi-hole service and port before router cutover:

```sh
ssh pihole1 'sudo systemctl --no-pager --full status pihole-FTL'
ssh pihole1 'sudo ss -lntup | grep ":53"'
```

Configure the router to advertise both resolver addresses only after both pass.
Renew one test client's DHCP lease and verify that it received both addresses.
Stop `pihole-FTL` on one resolver, query through the other, and immediately
restart the stopped service to prove failover.

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

## Rebuild a resolver

Reimage only one node at a time. Restore its original static DHCP reservation,
verify its SSH fingerprint from the console, update `known_hosts`, and apply the
base playbook before the DNS playbook. Validate it directly while clients still
use the surviving peer. Add the rebuilt resolver back to DHCP only after the
same UDP, TCP, local-name, and public-name checks pass.
