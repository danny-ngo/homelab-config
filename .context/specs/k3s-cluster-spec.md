# K3s Cluster Component Specification

Status: planning baseline
Last reviewed: 2026-07-15
Parent plan: `.context/specs/homelab-bootstrap-spec.md`
Delivery phase: Phase 4 — K3s cluster

## 1. Purpose

Define the implementation contract for the homelab's small, mixed-architecture K3s cluster.

This is a component specification, not a second homelab plan. The parent plan owns fleet roles, delivery order, Tailscale, DNS, dotfiles, stateful services, backups, and recovery. This document owns only K3s host preparation, installation, membership, architecture controls, validation, and cluster-specific operations.

The baseline cluster is:

- one `amd64` K3s server on the Debian ThinkPad;
- two `arm64` K3s agents on Raspberry Pi 3 B v1.2 nodes;
- one optional `armhf` agent on the Raspberry Pi 2 B v1.1 only after explicit admission;
- no Raspberry Pi 1 or ThinkCentre participation.

## 2. Outcomes

The automation must:

- install a pinned K3s version on the intended nodes;
- derive server, supported-worker, and experimental-worker behavior from inventory groups;
- use the ThinkPad's stable LAN address as the cluster API endpoint;
- discover and propagate the server-generated join token without exposing it;
- handle `amd64`, `arm64`, and optional `armhf` hosts explicitly;
- remain safe and idempotent on repeated runs;
- validate services, membership, architecture labels, reboot persistence, and a real workload;
- keep experimental-node failure outside baseline success;
- preserve enough server state and documentation to recover the cluster.

## 3. Scope and Boundaries

### In scope

- K3s inventory groups and variables.
- Host preflight and K3s prerequisites.
- A single K3s server on the ThinkPad.
- Two supported Pi 3 agents.
- A separate, opt-in Pi 2 admission workflow.
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
- Moving the ThinkPad's databases or pipeline orchestrator into K3s.
- Reconfiguring the router or tailnet.

## 4. Fixed Fleet Membership

| Inventory group | Host | Architecture | Baseline status | K3s role |
|---|---|---|---|---|
| `k3s_servers` | `thinkpad` | `amd64` | Required | Server |
| `k3s_workers_supported` | `rpi3a` | `arm64` | Required | Agent |
| `k3s_workers_supported` | `rpi3b` | `arm64` | Required | Agent |
| `k3s_workers_experimental` | `rpi2` | `armhf` / ARMv7 | Opt-in only | Agent after admission |
| Excluded | `thinkcentre` | `amd64` | Never a cluster node | Remote development only |
| Excluded | `pihole1`, `pihole2` | `armv6` | Never cluster nodes | Bare-metal DNS only |

Hostnames are illustrative inventory identifiers. Role assignment must never depend on matching these strings.

## 5. Platform and Architecture Contract

### ThinkPad server

- Expected CPU: Intel Core i5-8250U, `x86_64` / `amd64`.
- Expected OS: supported Debian release using systemd.
- Uses persistent local storage for K3s server state.
- Also hosts databases and pipeline orchestration in later phases, so K3s must have explicit resource headroom and must not consume the host without limits.
- Starts with K3s's default single-server datastore unless a separate architecture decision explicitly selects another supported datastore.

### Raspberry Pi 3 workers

- Expected hardware: Raspberry Pi 3 B v1.2.
- Required OS path: actively maintained 64-bit Raspberry Pi OS or Debian-compatible image.
- Expected detected architecture: `aarch64` / `arm64`.
- Must have unique hostnames, enabled memory cgroups, stable power, and healthy storage.
- Must not receive write-heavy workloads by default when running from SD cards.

### Raspberry Pi 2 experimental worker

Official K3s requirements currently list `armhf` as supported, making this node a candidate rather than a supported homelab baseline. Recheck the [K3s requirements](https://docs.k3s.io/installation/requirements) and the assets for the pinned [K3s release](https://github.com/k3s-io/k3s/releases) at admission time.

The Pi 2 must not be targeted by `site.yml` or the normal `k3s.yml` run. A separate `k3s-admit-experimental.yml` workflow must require an explicit enable variable and must pass every gate in Section 12.

### Raspberry Pi 1 exclusion

Both Pi 1 nodes are permanently excluded from this cluster specification. The parent plan reserves them for bare-metal Pi-hole. Do not add an ARMv6 K3s path or a generic `arm*` acceptance rule.

### Architecture assertions

Before installing or changing K3s, automation must:

- collect Ansible facts;
- map the detected architecture to the expected inventory class;
- assert `amd64` for the server, `arm64` for supported workers, and ARMv7/`armhf` for the experimental worker;
- fail clearly on a mismatch or unsupported architecture;
- verify that the pinned K3s release artifact exists for the target architecture;
- preserve standard Kubernetes `kubernetes.io/os` and `kubernetes.io/arch` labels;
- apply any custom capability labels through variables, not hostname conditionals.

## 6. Network and Access Model

- The ThinkPad, Pi 3 nodes, and optional Pi 2 communicate over the LAN.
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
        k3s_workers_experimental.yml
      host_vars/
  playbooks/
    k3s.yml
    k3s-admit-experimental.yml
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
- `k3s_workers_experimental`
- `k3s_cluster`, an optional parent containing servers and supported workers only

The experimental group must remain outside the default `k3s_cluster` parent so a normal group limit cannot enroll the Pi 2 accidentally.

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
    k3s_workers_experimental:
      hosts:
        rpi2:
          k3s_experimental_worker_enabled: false
```

### Behavior rules

- Members of `k3s_servers` receive server configuration.
- Members of `k3s_workers_supported` receive agent configuration during the normal K3s playbook.
- Members of `k3s_workers_experimental` receive no K3s changes during normal playbooks.
- Experimental enrollment requires the separate admission playbook, a host-specific enable value, and all admission assertions.
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

### 9.4 Experimental agent admission

For `k3s_workers_experimental`, the admission playbook must:

- assert `k3s_experimental_worker_enabled: true` for the targeted host;
- require a deliberate host limit so it cannot run against a broad fleet pattern;
- run every preflight and release-asset check before installation;
- label and preferably taint the node so ordinary workloads do not land on it;
- validate reboot recovery and the 72-hour soak described in Section 12;
- produce a recorded result of `admitted` or `excluded` with the K3s version, OS version, architecture, and test outcome;
- allow clean removal from the cluster without affecting baseline nodes.

### 9.5 Token and kubeconfig handling

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

### 9.6 Validation

The normal K3s playbook must verify:

- `k3s` is enabled and active on the ThinkPad;
- `k3s-agent` is enabled and active on both Pi 3 nodes;
- the API responds from the ThinkPad;
- exactly the expected baseline nodes appear unless a declared admitted experimental node is also present;
- the baseline nodes reach `Ready` within a bounded timeout;
- reported OS and architecture labels match inventory expectations;
- no Pi 1 or ThinkCentre appears as a node;
- a disposable validation workload using a trusted, pinned multi-architecture image can be scheduled and completed on compatible workers;
- validation resources are removed afterward;
- nodes return to `Ready` after a controlled reboot test.

Validation must surface actionable output showing which node, service, architecture, or scheduling condition failed.

### 9.7 Idempotency

A second run must:

- report no unexplained changes;
- not reinstall an unchanged K3s binary;
- not rotate the join token;
- not rewrite unchanged configuration;
- not restart healthy services without a notified change;
- not rejoin or duplicate existing nodes;
- not touch the experimental worker during the normal playbook.

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
- `k3s_node_taints`: especially for experimental or constrained nodes;
- `k3s_expected_arch`: assertion value per group/host;
- `k3s_experimental_worker_enabled`: defaults to `false`;
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
- Keep experimental nodes tainted and free of secrets or critical workloads until explicitly trusted.
- Prefer trusted multi-architecture images, pinned tags, and digests where practical.
- Do not use unofficial images solely to make a weak architecture work.
- Monitor ThinkPad capacity so K3s, databases, and pipeline orchestration cannot silently starve one another.
- Back up the K3s server token, configuration, and datastore through the parent plan's backup system.

## 12. Raspberry Pi 2 Admission Gate

The Pi 2 may be marked `admitted` only when all of the following are true:

1. Inventory identifies the exact Pi 2 revision and expected ARMv7 architecture.
2. The selected OS is actively maintained and uses systemd.
3. Memory cgroups, required kernel features, time sync, networking, and storage checks pass.
4. CPU, usable RAM, and free disk meet the pinned K3s agent requirements with workload headroom.
5. The pinned K3s release publishes and successfully verifies an `armhf` binary and required images.
6. The node joins with the same K3s version as the server.
7. The node reports the expected architecture and reaches `Ready` after reboot.
8. A trusted 32-bit ARM-compatible smoke workload completes on the node.
9. The node is labeled and tainted so only explicitly compatible workloads can use it.
10. A 72-hour soak completes without repeated NotReady transitions, memory exhaustion, storage errors, or service crashes.
11. Removal and rejoin are demonstrated without affecting the ThinkPad or Pi 3 workers.
12. The result, versions, facts, and allowed workload class are recorded in documentation.

Failure of any gate results in `excluded`, not a partially supported default worker. Exclusion must not fail the baseline cluster playbook or acceptance criteria.

## 13. Execution Model

### Baseline cluster

The normal `ansible/playbooks/k3s.yml` flow should:

1. Run preflight and prerequisites on `k3s_servers` and `k3s_workers_supported`.
2. Converge the ThinkPad server.
3. Read the runtime join token securely.
4. Converge the two supported Pi 3 agents.
5. Validate membership, labels, services, and the disposable workload.
6. Report the Pi 2 as not evaluated, admitted, or excluded without changing it.

### Experimental admission

The separate `ansible/playbooks/k3s-admit-experimental.yml` flow should:

1. Require an explicit `--limit` targeting the experimental host.
2. Assert the enable variable and admission inputs.
3. Run preflight and install only if all immediate gates pass.
4. Apply restrictive labels/taints.
5. Start the reboot and soak validation process.
6. Record the final result before the node is considered usable.

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
5. The Pi 2 is not changed by the normal playbook and has an explicit status of `not evaluated`, `admitted`, or `excluded`.
6. A trusted pinned multi-architecture validation workload completes only on compatible nodes.
7. Baseline nodes recover to `Ready` after controlled reboot.
8. A second normal playbook run has no unexplained changes or restarts.
9. The token is discovered securely and does not appear in inventory, logs, cached facts, or committed files.
10. Kubeconfig, if fetched, has correct endpoint and least-privileged permissions.
11. Server state paths and backup inputs are registered with the parent backup plan.
12. Usage and recovery documentation explain inventory, execution, validation, upgrades, and removal.

### Experimental acceptance

The Pi 2 is accepted only through all Section 12 gates. Its admission is additional capacity, never part of baseline success.

## 15. Deliverables

Implementation agents should produce:

- production inventory groups and non-secret example variables;
- pinned K3s collection/role dependencies, if any;
- `k3s_prereqs`, `k3s_server`, and `k3s_agent` roles;
- normal and experimental admission playbooks;
- runtime token propagation with secret-safe logging behavior;
- server, agent, architecture, reboot, workload, and idempotency validation;
- a Pi 2 admission result record;
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
3. Do not make the Pi 2 part of the normal worker group or baseline acceptance.
4. Do not add the Pi 1 or ThinkCentre nodes to any K3s group.
5. Keep the cluster endpoint on the LAN unless the parent architecture plan is deliberately revised.
6. Preserve group-driven behavior; hostname checks are documentation smells and task-logic failures.
7. Recheck official K3s architecture and release support whenever the pinned version changes.
8. Do not silently select deferred ingress, storage, GitOps, or datastore products.
9. Validate idempotency, reboot persistence, and a real workload before declaring completion.
10. Update this spec, the parent plan, README, and recovery runbook when a cluster decision changes.
