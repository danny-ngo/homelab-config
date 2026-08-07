---
layout: default
title: K3s recovery
---

# K3s recovery

The ThinkPad is the single K3s server. Its data directory and node token are
critical state; workers are rebuildable. Restore the server before any worker.

## Helm administration

Helm works with K3s without special cluster configuration. K3s includes a Helm
Controller for declarative `HelmChart` resources, but the upstream Helm CLI is
a client and does not need to be installed on the ThinkPad merely because that
host runs the K3s server.

Keep the normal administration boundary consistent with the rest of this
repository:

- run the Helm CLI from the MacBook controller, or from explicit automation,
  using a kubeconfig that can reach the K3s API;
- keep charts, values, and release configuration in this repository;
- treat a Helm CLI installation on the ThinkPad as optional break-glass
  tooling, not as a routine deployment dependency; and
- retain the current no-GitOps baseline unless continuous in-cluster
  reconciliation is adopted as a separate architecture decision.

The server's administrator kubeconfig is
`/etc/rancher/k3s/k3s.yaml`. Any copy used from the MacBook must replace its
`server` address with the reachable ThinkPad API address. It grants unrestricted
cluster administration, must never be committed, and may need to be refreshed
after K3s rotates the embedded client certificates. Prefer a purpose-scoped
kubeconfig over copying the administrator credential once the required Helm
release permissions are known.

References:

- [K3s Helm support and Helm Controller](https://docs.k3s.io/add-ons/helm)
- [K3s cluster access and external kubeconfig handling](https://docs.k3s.io/cluster-access)

## Recovery inputs

Keep these in the protected backup system, never in Git or ordinary logs:

- `/var/lib/rancher/k3s` from the server, including the SQLite datastore;
- `/var/lib/rancher/k3s/server/node-token`;
- `/etc/rancher/k3s/config.yaml` and the deployed K3s version;
- any administrator kubeconfig, treated as a cluster credential.

Before maintenance, record cluster state and verify the backup completed:

```sh
ssh thinkpad 'sudo k3s kubectl get nodes -o wide'
ssh thinkpad 'sudo k3s kubectl get pods -A'
ssh thinkpad 'sudo systemctl --no-pager status k3s'
```

## Server recovery

1. Stop `k3s` and copy the failed data directory aside instead of overwriting it.
2. Rebuild the ThinkPad with the same LAN address, hostname, architecture, and
   K3s version recorded with the backup.
3. Apply the host baseline. Stop K3s before restoring the protected server data
   directory and configuration with their original root ownership and modes.
4. Start K3s and inspect `journalctl -u k3s`. Require the API to respond before
   touching workers:

   ```sh
   ssh thinkpad 'sudo systemctl start k3s'
   ssh thinkpad 'sudo k3s kubectl get --raw=/readyz'
   ssh thinkpad 'sudo k3s kubectl get nodes -o wide'
   ```

5. Run `make validate LIMIT=thinkpad`. Do not copy the node token to a shell
   command or inventory; the K3s playbook reads it transiently under `no_log`.

If the old datastore cannot be restored, create a fresh server only after
preserving the failed state for later analysis. A fresh server is a new cluster;
remove stale worker state before rejoining.

## Worker removal and rejoin

Drain a responsive worker before planned replacement:

```sh
ssh thinkpad 'sudo k3s kubectl drain pi3a --ignore-daemonsets --delete-emptydir-data'
ssh thinkpad 'sudo k3s kubectl delete node pi3a'
```

On the worker, stop `k3s-agent` and preserve logs if the failure is unexplained.
For a clean rejoin, remove stale agent state only after the server-side Node has
been deleted. Then apply the normal playbook to exactly that worker:

```sh
make check PLAYBOOK=ansible/playbooks/k3s.yml LIMIT=pi3a
make k3s LIMIT=pi3a
ssh thinkpad 'sudo k3s kubectl wait node/pi3a --for=condition=Ready --timeout=5m'
```

## Upgrade and rollback

Back up the server first. Upgrade the server before agents and never change the
server and every worker in one unobserved step. Confirm the checksum mapping for
the new pinned release in both K3s role defaults, apply to the server, validate
the API and workloads, then update one agent at a time.

For rollback, stop K3s, restore the datastore backup made before the upgrade,
restore the previous verified binary/configuration, and start the server. Roll
agents back only after the server is healthy. Validate node readiness and actual
workloads, not just systemd process state.

Do not share kubeconfig, node-token contents, or command output containing
credentials in tickets or chat.

## Raspberry Pi 2 admission gate

The current example baseline assigns the Pi 2 to bare-metal Pi-hole, so it does
not yet have a K3s agent or appear in the worker inventory group. This is an
implementation gate, not a hardware exclusion: its 1 GB RAM meets the K3s agent
baseline, which excludes workload consumption.

Before admitting it, add a reviewed Pi-hole Kubernetes workload with persistent
configuration, explicit DNS port exposure, measured requests and limits, and
node affinity for a dedicated DNS label. Taint the Pi 2 so unrelated workloads
cannot land there, then extend recovery checks to prove that the Pi-hole pod
returns to the Pi 2 and answers direct UDP and TCP DNS queries after a reboot.
Do not add the worker first and leave the critical workload or scheduling policy
implicit.
