---
layout: default
title: T3 Code remote service
---

# T3 Code remote service

The ThinkCentre runs T3 Code as the execution user through T3 Code's managed
Linux background service. The service starts at boot through a lingering
systemd user manager and keeps the server runtime separate from the stable
launcher. Tailscale Serve publishes that loopback-only server privately to the
tailnet over HTTPS.

T3 Code clients and servers work best at exactly the same version. This
repository pins that version in
`ansible/roles/execution_node/defaults/main.yml`; do not update only the desktop
app or only the server and leave the warning dismissed.

## Initial deployment and pairing

Apply and validate the execution-node profile from the MacBook:

```sh
./bootstrap.sh --profile execution-node --limit thinkcentre --check
./bootstrap.sh --profile execution-node --limit thinkcentre
make validate LIMIT=thinkcentre
```

The role installs the exact T3 CLI, removes the legacy root-owned
`t3-code.service`, enables lingering for the execution user, and reconciles the
upstream `t3code.service` user unit with the pinned runtime. The service listens
on loopback; do not bind it directly to the LAN or public internet.

On the ThinkCentre, confirm the managed service and create a short-lived
pairing credential:

```sh
mise exec node@24 -- t3 service status \
  --base-dir "$HOME/.local/share/t3code"

mise exec node@24 -- t3 pair \
  --base-dir "$HOME/.local/share/t3code" \
  --tailscale \
  --tailscale-serve-port 443 \
  --ttl 10m
```

The second command discovers the running server, configures Tailscale Serve for
its actual loopback port, and prints a pairing URL and QR code using the
reachable Tailscale HTTPS endpoint. Open it promptly; the token is a credential
and expires after the requested TTL.

On first use, Tailscale may print a consent URL. Enable **HTTPS Certificates**
for the tailnet, then rerun the pairing command. **Tailscale Funnel is not
needed**: Funnel would make the service public, while Serve keeps it available
only through tailnet access controls.

## Keep the client and server in sync

Before an update, let active agents and terminal commands finish. Updating
restarts the server briefly, although saved threads, settings, and project
files remain in place.

1. Read the exact client version from the T3 Code warning or from
   **Settings → Connections**.
2. Change `t3_code_version` in the execution-node defaults to that exact
   version, including any nightly suffix.
3. Run the execution-node check, apply, and validation commands above.
4. Keep the client open while the managed service installs, tests, restarts,
   and reconnects.
5. If Tailscale Serve was reset, rerun `t3 pair --tailscale` and use the fresh
   link.

The playbook invokes the equivalent of:

```sh
npx --yes t3@<exact-client-version> service update \
  --base-dir "$HOME/.local/share/t3code"
```

Use the exact version, not `latest`, unless the client is itself on the latest
release. After the managed launcher is installed, it keeps exact runtimes
separately, snapshots the database before a candidate update, and can roll back
a failed candidate. The first migration from this repository's former custom
system service establishes that rollback-capable launcher; later updates use
its protected handoff.

## Diagnose connection failures

Check each layer in order on the ThinkCentre:

```sh
mise exec node@24 -- t3 service status \
  --base-dir "$HOME/.local/share/t3code"
systemctl --user status t3code.service
curl -fsS http://127.0.0.1:3773/.well-known/t3/environment
tailscale serve status
```

From a connected tailnet client, set the MagicDNS name reported by
`tailscale serve status`, then test HTTPS:

```sh
T3_MAGICDNS_NAME=replace-with-the-reported-name
curl -fsS "https://${T3_MAGICDNS_NAME}/.well-known/t3/environment"
```

Interpret failures as follows:

- Local HTTP fails: inspect `systemctl --user status t3code.service` and the
  log path printed by `t3 service status`.
- Local HTTP works but HTTPS fails: rerun `t3 pair --tailscale`; verify
  Tailscale is connected, HTTPS certificates are enabled, and Serve points to
  the active loopback port.
- The environment descriptor works but the app repeatedly reconnects: compare
  its `serverVersion` with the desktop app version. Apply the exact matching
  pin, remove any stale saved connection, and pair again with a fresh token.
- A pairing link contains loopback HTTP or has expired: discard it and use
  `t3 pair --tailscale` instead of reusing service-startup output.

Do not paste pairing URLs or tokens into issues, chat, screenshots, or logs.
Use `t3 auth` to inspect and revoke credentials or sessions that are no longer
trusted.

## References

- [Keeping T3 Code in Sync](https://github.com/pingdotgg/t3code/blob/main/docs/user/updating.md)
- [Running T3 Code in the Background](https://github.com/pingdotgg/t3code/blob/main/docs/user/background-service.md)
- [T3 Code Remote Access](https://github.com/pingdotgg/t3code/blob/main/docs/user/remote-access.md)
- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
