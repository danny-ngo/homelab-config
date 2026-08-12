# K3s Cluster Component Specification

Status: planning baseline
Last reviewed: 2026-07-28
Parent plan: `.context/specs/homelab-bootstrap-spec.md`
Delivery phase: Phase 4 — K3s cluster

## 1. Purpose

Define the implementation contract for the homelab's small, mixed-architecture K3s cluster.

This is a component specification, not a second homelab plan. The parent plan owns fleet roles, delivery order, Tailscale, DNS, dotfiles, stateful services, backups, and recovery. This document owns only K3s host preparation, installation, membership, architecture controls, validation, and cluster-specific operations.

The baseline cluster is:

- one `amd64` K3s server on the Debian ThinkPad;
- two `arm64` K3s agents on Raspberry Pi 3 B v1.2 nodes;
- no Raspberry Pi 2, Raspberry Pi 1, or ThinkCentre participation.

## 2. Outcomes

The automation must:

- install a pinned K3s version on the intended nodes;
- derive server and supported-worker behavior from inventory groups;
- use the ThinkPad's stable LAN address as the cluster API endpoint;
- discover and propagate the server-generated join token without exposing it;
- handle `amd64` and `arm64` hosts explicitly;
- remain safe and idempotent on repeated runs;
- validate services, membership, architecture labels, reboot persistence, and a real workload;
- preserve enough server state and documentation to recover the cluster.

## 3. Scope and Boundaries

### In scope

- K3s inventory groups and variables.
- Host preflight and K3s prerequisites.
- A single K3s server on the ThinkPad.
- Two supported Pi 3 agents.
- Server token discovery and secure agent join.
- Kubeconfig handling for administration.
- Node labels, taints, and architecture-aware validation.
- Baseline network, service, reboot, workload, and idempotency checks.
- K3s server-state backup inputs and a recovery runbook contract.

### Out of scope

- Installing application workloads beyond a disposable validation workload.
- Full GitOps configuration.
- High-availability servers or an etcd quorum.
- Adding the ThinkCentre to K3s.
- Adding either Raspberry Pi 1 to K3s.
- Running Pi-hole in K3s.
- Public ingress, public API exposure, automated TLS, or an external load balancer.
- Selecting the long-term ingress, storage, observability, or GitOps products.
- Moving the ThinkPad's Docker infrastructure services into K3s.
- Reconfiguring the router or tailnet.

## 4. Fixed Fleet Membership

| Inventory group | Host | Architecture | Baseline status | K3s role |
|---|---|---|---|---|
| `k3s_servers` | `thinkpad` | `amd64` | Required | Server |
| `k3s_workers_supported` | `rpi3a` | `arm64` | Required | Agent |
| `k3s_workers_supported` | `rpi3b` | `arm64` | Required | Agent |
| Excluded | `pi2` | `armhf` / ARMv7 | Never a cluster node | Dedicated bare-metal Pi-hole |
| Excluded | `thinkcentre` | `amd64` | Never a cluster node | Remote development only |
| Excluded | two Pi 1 boards | `armv6` | Never cluster nodes | Reachability probe and Pi 2 service sentinel only |

Hostnames are illustrative inventory identifiers. Role assignment must never depend on matching these strings.

## 5. Platform and Architecture Contract

### ThinkPad server

- Expected CPU: Intel Core i5-8250U, `x86_64` / `amd64`.
- Expected OS: supported Debian release using systemd.
- Uses persistent local storage for K3s server state.
- Also hosts Docker databases, monitoring, and automation services in later
  phases, so K3s must have explicit resource headroom and must not consume the
  host without limits.
- Starts with K3s's default single-server datastore unless a separate architecture decision explicitly selects another supported datastore.

### Raspberry Pi 3 workers

- Expected hardware: Raspberry Pi 3 B v1.2.
- Required OS path: actively maintained 64-bit Raspberry Pi OS or Debian-compatible image.
- Expected detected architecture: `aarch64` / `arm64`.
- Must have unique hostnames, enabled memory cgroups, stable power, and healthy storage.
- Must not receive write-heavy workloads by default when running from SD cards.

### Raspberry Pi 2 exclusion

The Pi 2 is permanently assigned to bare-metal Pi-hole. It must not appear in a
K3s worker group, receive K3s prerequisites, or have a K3s agent installed.

### Raspberry Pi 1 exclusion

Both 256 MB Pi 1 nodes are permanently excluded from this cluster
specification. Do not add an ARMv6 K3s path or a generic `arm*` acceptance rule.

### Architecture assertions

Before installing or changing K3s, automation must:

- collect Ansible facts;
- map the detected architecture to the expected inventory class;
- assert `amd64` for the server and `arm64` for supported workers;
- fail clearly on a mismatch or unsupported architecture;
- verify that the pinned K3s release artifact exists for the target architecture;
- preserve standard Kubernetes `kubernetes.io/os` and `kubernetes.io/arch` labels;
- apply any custom capability labels through variables, not hostname conditionals.

## 6. Network and Access Model

- The ThinkPad and Pi 3 nodes communicate over the LAN.
- The K3s API endpoint must resolve to or explicitly use the ThinkPad's stable LAN address.
- Do not use the ThinkPad's Tailscale address as the agent join endpoint in v1 because the Raspberry Pi workers are intentionally outside Tailscale.
- The MacBook may administer the API remotely through the ThinkPad's Tailscale path only if routing, certificate names, and access controls are intentionally configured; this is not required for initial cluster convergence.
- The Ansible operator machine reaches the ThinkPad and Raspberry Pis through LAN SSH; the ThinkPad may be that machine but is not required to be.
- No K3s port is exposed directly to the public internet.
- Inventory variables must detect conflicts between the chosen pod/service CIDRs and the LAN, tailnet, or other routed networks.
- The firewall port matrix must be derived from the pinned K3s networking backend and official documentation rather than copied indefinitely into this specification.
- At minimum, the K3s API path on TCP 6443 must be reachable from intended agents and authorized administrators.

## 7. Repository Layout

The implementation should use the broader repository structure defined in the parent plan and add only real files needed for this component:

```text
ansible/
  inventories/
    production/
      hosts.yml
      group_vars/
        k3s_cluster.yml
        k3s_servers.yml
        k3s_workers_supported.yml
      host_vars/
  playbooks/
    k3s.yml
  roles/
    k3s_prereqs/
      defaults/
      tasks/
      handlers/
    k3s_server/
      defaults/
      tasks/
      templates/
      handlers/
    k3s_agent/
      defaults/
      tasks/
      templates/
      handlers/
tests/
docs/
  runbooks/
    k3s-recovery.md
```

Do not create empty role trees in advance. Each added role must include defaults, input assertions, handlers where needed, and relevant validation.

## 8. Inventory Model

### Required groups

- `k3s_servers`
- `k3s_workers_supported`
- `k3s_cluster`, an optional parent containing servers and supported workers only

### Example shape

```yaml
all:
  children:
    k3s_cluster:
      children:
        k3s_servers:
          hosts:
            thinkpad: {}
        k3s_workers_supported:
          hosts:
            rpi3a: {}
            rpi3b: {}
```

### Behavior rules

- Members of `k3s_servers` receive server configuration.
- Members of `k3s_workers_supported` receive agent configuration during the normal K3s playbook.
- A host must never be both a server and a worker.
- Common prerequisite tasks must not execute more than once because a host is reachable through overlapping parent groups.

## 9. Functional Requirements

### 9.1 Preflight and host preparation

The `k3s_prereqs` role must idempotently:

- gather and assert OS, architecture, CPU, RAM, storage, and init-system facts;
- verify unique Kubernetes node names;
- install pinned or distribution-managed prerequisite packages;
- ensure a downloader such as `curl` is available;
- enable required cgroups on Raspberry Pi operating systems and handle the correct boot configuration path for that OS release;
- handle swap according to the selected K3s/Kubernetes approach;
- configure required sysctls and kernel modules;
- validate time synchronization and DNS resolution;
- validate LAN reachability and CIDR non-overlap;
- check free space and flag unhealthy or unsuitable SD-card/storage conditions;
- reboot only through an explicit handler when boot configuration changes;
- wait for the host and rerun assertions after any required reboot.

Changing Raspberry Pi boot arguments is a high-impact step. Back up the original boot configuration and make changes with a template or line-aware module.

### 9.2 Server installation

For `k3s_servers`:

- install the pinned K3s release in server mode using the official installer or a verified binary path;
- render a stable K3s configuration file from variables;
- bind/advertise the intended LAN endpoint;
- enable and start the systemd service;
- verify the service and API become healthy;
- keep kubeconfig and server state at least-privileged permissions;
- read the node join token from `/var/lib/rancher/k3s/server/node-token` after the server is ready;
- expose the token to agent plays only in memory with `no_log` protection;
- never regenerate or replace a healthy cluster token on a routine rerun;
- record the server data directory, datastore choice, token backup requirement, and recovery inputs.

### 9.3 Supported agent installation

For `k3s_workers_supported`:

- consume the ThinkPad's LAN API URL and runtime-discovered token;
- install the exact K3s version used by the server;
- render stable agent configuration including node name, labels, and optional taints;
- enable and start the systemd agent service;
- verify the local service and server-side node registration;
- avoid restarts unless configuration or binary content changed.

### 9.4 Token and kubeconfig handling

Preferred token flow:

1. Converge the server.
2. Read `/var/lib/rancher/k3s/server/node-token` using privilege.
3. Store it only as a transient Ansible fact or delegated variable protected with `no_log`.
4. Use it during the agent plays without writing it into inventory, logs, cached facts, or generated documentation.

An encrypted pre-seeded token is an acceptable fallback only when the operational reason is documented.

If kubeconfig is copied to the MacBook or another operator machine:

- treat it as a sensitive administrator credential;
- set owner-only permissions;
- rewrite the endpoint intentionally rather than with brittle string replacement;
- ensure the selected address is represented in the server certificate configuration;
- document revocation and rotation expectations.

### 9.5 Validation

The normal K3s playbook must verify:

- `k3s` is enabled and active on the ThinkPad;
- `k3s-agent` is enabled and active on both Pi 3 nodes;
- the API responds from the ThinkPad;
- exactly the expected baseline nodes appear;
- the baseline nodes reach `Ready` within a bounded timeout;
- reported OS and architecture labels match inventory expectations;
- no Pi 1 or ThinkCentre appears as a node;
- a disposable validation workload using a trusted, pinned multi-architecture image can be scheduled and completed on compatible workers;
- validation resources are removed afterward;
- nodes return to `Ready` after a controlled reboot test.

Validation must surface actionable output showing which node, service, architecture, or scheduling condition failed.

### 9.6 Idempotency

A second run must:

- report no unexplained changes;
- not reinstall an unchanged K3s binary;
- not rotate the join token;
- not rewrite unchanged configuration;
- not restart healthy services without a notified change;
- not rejoin or duplicate existing nodes;
- not touch the dedicated Pi-hole Pi 2.

## 10. Required Variables

At minimum, define and document:

- `k3s_version`: required pinned version for all nodes;
- `k3s_server_url`: ThinkPad LAN API URL;
- `k3s_token_source`: defaults to runtime discovery on the server;
- `k3s_disable_components`: explicit list, empty unless an architecture decision says otherwise;
- `k3s_extra_server_args`: validated extra server options;
- `k3s_extra_agent_args`: validated extra agent options;
- `k3s_kubeconfig_mode`: least-privileged mode;
- `k3s_cluster_cidr` and `k3s_service_cidr`: checked for network overlap;
- `k3s_node_labels`: per-host or group-defined labels;
- `k3s_node_taints`: for constrained supported nodes when needed;
- `k3s_expected_arch`: assertion value per group/host;
- `k3s_validation_image`: trusted, pinned, verified multi-architecture image;
- `k3s_server_data_dir`: documented persistent state path;
- `k3s_fetch_kubeconfig`: defaults to `false` until destination and permissions are configured.

Do not define a plaintext `k3s_token` in normal inventory examples.

## 11. Security and Operational Requirements

- Never commit join tokens, kubeconfigs, service-account tokens, SSH private keys, or registry credentials.
- Apply `no_log` to tasks that can expose the K3s token or sensitive kubeconfig content.
- Disable persistent fact caching for secret-bearing transient variables or prove the secret is excluded.
- Prefer Ansible modules and verified downloads over broad shell pipelines.
- Pin K3s and verify release checksums when downloading binaries directly.
- Restrict K3s API access to intended LAN/tailnet administrators and agents.
- Treat SSH and sudo access to the ThinkPad as cluster-administrator access.
- Prefer trusted multi-architecture images, pinned tags, and digests where practical.
- Do not use unofficial images solely to make a weak architecture work.
- Monitor ThinkPad capacity so K3s, databases, monitoring, and automation
  services cannot silently starve one another.
- Back up the K3s server token, configuration, and datastore through the parent plan's backup system.

## 12. Raspberry Pi 2 Exclusion Contract

The Pi 2 is the dedicated Pi-hole node. Inventory, tests, and recovery
documentation must keep it outside `k3s_cluster` and all worker groups. Any
future reversal requires a new architecture decision and a replacement DNS
host before cluster work begins.

## 13. Execution Model

### Baseline cluster

The normal `ansible/playbooks/k3s.yml` flow should:

1. Run preflight and prerequisites on `k3s_servers` and `k3s_workers_supported`.
2. Converge the ThinkPad server.
3. Read the runtime join token securely.
4. Converge the two supported Pi 3 agents.
5. Validate membership, labels, services, and the disposable workload.
6. Verify the Pi 2 remains absent from cluster membership.

### Configuration style

- Prefer `/etc/rancher/k3s/config.yaml` or equivalent stable configuration over opaque installer flags.
- Use handlers so services restart only after relevant changes.
- Explain every `command` or `shell` task and give it accurate `changed_when` and `failed_when` behavior.
- Separate validation from mutation where practical so `validate.yml` can call read-only checks.

## 14. Acceptance Criteria

### Baseline acceptance

The Phase 4 baseline is complete when:

1. The ThinkPad runs the pinned K3s server version and exposes the API on the intended LAN endpoint.
2. Both Pi 3 nodes run the matching K3s agent version and join successfully.
3. `kubectl get nodes` reports the ThinkPad and both Pi 3 nodes as `Ready` with correct OS/architecture labels.
4. Neither Pi 1 nor the ThinkCentre appears in cluster membership.
5. The Pi 2 remains absent from every K3s worker group and cluster membership.
6. A trusted pinned multi-architecture validation workload completes only on compatible nodes.
7. Baseline nodes recover to `Ready` after controlled reboot.
8. A second normal playbook run has no unexplained changes or restarts.
9. The token is discovered securely and does not appear in inventory, logs, cached facts, or committed files.
10. Kubeconfig, if fetched, has correct endpoint and least-privileged permissions.
11. Server state paths and backup inputs are registered with the parent backup plan.
12. Usage and recovery documentation explain inventory, execution, validation, upgrades, and removal.

## 15. Deliverables

Implementation agents should produce:

- production inventory groups and non-secret example variables;
- pinned K3s collection/role dependencies, if any;
- `k3s_prereqs`, `k3s_server`, and `k3s_agent` roles;
- the normal K3s playbook;
- runtime token propagation with secret-safe logging behavior;
- server, agent, architecture, reboot, workload, and idempotency validation;
- README commands for normal provisioning and validation;
- `docs/runbooks/k3s-recovery.md` covering server state, token, kubeconfig, node removal, and rebuild order;
- tests or CI checks for YAML, Ansible syntax/lint, inventory shape, and role input assertions.

## 16. Deferred Enhancements

Design so these can be added later without implementing them in Phase 4:

- a second or third K3s server and an HA datastore;
- GitOps bootstrap and application namespaces;
- deliberate ingress and certificate management;
- a durable cluster storage strategy;
- network policies and deeper runtime hardening;
- registry mirrors or air-gapped installation;
- automated upgrade orchestration with rollback checks;
- richer node capability labels and workload policies.

## 17. Instructions for Implementation Agents

1. Read `.context/homelab-bootstrap-spec.md` before this component specification.
2. Do not broaden cluster membership beyond the fixed fleet table.
3. Do not add the dedicated Pi-hole Pi 2 to any worker group.
4. Do not add the Pi 1 or ThinkCentre nodes to any K3s group.
5. Keep the cluster endpoint on the LAN unless the parent architecture plan is deliberately revised.
6. Preserve group-driven behavior; hostname checks are documentation smells and task-logic failures.
7. Recheck official K3s architecture and release support whenever the pinned version changes.
8. Do not silently select deferred ingress, storage, GitOps, or datastore products.
9. Validate idempotency, reboot persistence, and a real workload before declaring completion.
10. Update this spec, the parent plan, README, and recovery runbook when a cluster decision changes.
