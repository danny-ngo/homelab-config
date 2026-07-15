# Full Homelab Automation Plan

Status: planning baseline
Last reviewed: 2026-07-15
Primary audience: implementation agents and the homelab operator
Component detail: `.context/specs/k3s-cluster-spec.md` defines the Phase 4 K3s implementation contract beneath this plan.

## 1. Mission

Evolve this repository from a K3s-only bootstrap into the source of truth for provisioning, configuring, validating, and operating the full homelab.

The target outcome is a reproducible fleet in which:

- the MacBook Pro is the primary operator workstation;
- the Debian ThinkPad is the persistent infrastructure host and K3s server;
- the headless CachyOS ThinkCentre Tiny is a remote agentic-development execution node;
- two Raspberry Pi 3 B v1.2 machines are normal K3s workers;
- one Raspberry Pi 2 B v1.1 is admitted as an experimental K3s worker only after a support gate;
- two Raspberry Pi 1 A+ v1.1 machines run Pi-hole directly on the operating system;
- the MacBook, ThinkPad, and ThinkCentre are joined to Tailscale;
- the separate dotfiles repository is applied as an explicit Ansible step rather than copied into this repository;
- every important change is rerunnable, testable, and recoverable without committing secrets.

## 2. Repository State at Planning Time

The repository is a scaffold. `README.md`, `Makefile`, `bootstrap.sh`, Ansible configuration, and Ansible requirements are empty. The inventory, playbook, role, bootstrap, docs, scripts, and tests directories contain no implementation yet.

The detailed cluster requirements live in `.context/k3s-cluster-spec.md`. That component specification establishes:

- group-driven K3s server/agent behavior;
- mixed `amd64`, `arm64`, `armv7`, and `armv6` constraints;
- secure discovery of the K3s join token;
- idempotency and cluster validation requirements;
- Pi 3 workers as the normal target, Pi 2 as conditional, and Pi 1 devices outside K3s.

Do not discard that detail. Implement the broader plan here and refer to the K3s document when working on cluster roles.

## 3. Architectural Principles

1. **Separate machine configuration from application deployment.** Ansible owns hosts, packages, users, networking, Tailscale, host services, K3s installation, and validation. Kubernetes manifests or Helm own in-cluster applications.
2. **Keep the bootstrap path acyclic.** One public bootstrap entry point prepares any supported operator machine and dispatches platform/profile modules. No managed host, including the ThinkPad, is required to remain the Ansible controller.
3. **Use group membership, not hostnames, to assign behavior.** A host may belong to several capability groups; for example, the ThinkPad is both an infrastructure host and a K3s server.
4. **Prefer LAN addresses for the local cluster.** K3s server/agent traffic and Pi-hole service traffic should use stable LAN addresses initially because the Raspberry Pis are intentionally outside Tailscale. Tailscale is the remote administration path for the three primary computers.
5. **Treat persistent state explicitly.** Databases, orchestration metadata, Pi-hole configuration, K3s state, and credentials each need named storage and recovery procedures before they are considered operational.
6. **Do not make weak hardware a hidden dependency.** Failure of the Pi 2 or either Pi 1 must degrade only the workload or DNS instance assigned to it, not the automation path or cluster server.
7. **Pin versions and test upgrades.** Pin K3s and important roles/collections. Upgrade deliberately through a documented maintenance playbook.
8. **No plaintext secrets in Git.** Repository examples contain variable names and fake values only. Runtime credentials come from an encrypted or external secret source.

## 4. Target Fleet and Responsibilities

| Inventory name | Hardware / OS | Primary responsibilities | Connectivity | State class |
|---|---|---|---|---|
| `macbook` | MacBook Pro / macOS | Main workstation, initial bootstrap origin, repository editing, operator CLI, local dotfiles | LAN + Tailscale | User data; backed up outside this repo |
| `thinkpad` | ThinkPad / Debian | K3s server, databases, pipeline orchestration, backup coordination, optional admin entry point | LAN + Tailscale | Critical infrastructure state |
| `thinkcentre` | ThinkCentre Tiny / headless CachyOS | Remote T3 Code and Codex CLI execution, builds/tests, isolated workspaces and caches | LAN + Tailscale | Rebuildable workspaces plus selected caches |
| `rpi3a` | Raspberry Pi 3 B v1.2 / 64-bit Pi OS or Debian | Normal K3s worker for small services | LAN | Rebuildable node state |
| `rpi3b` | Raspberry Pi 3 B v1.2 / 64-bit Pi OS or Debian | Normal K3s worker for small services | LAN | Rebuildable node state |
| `rpi2` | Raspberry Pi 2 B v1.1 / supported 32-bit Pi OS | Experimental K3s worker after admission checks | LAN | Rebuildable; never required for quorum |
| `pihole1` | Raspberry Pi 1 A+ v1.1 / supported 32-bit Pi OS | Bare-metal primary/peer Pi-hole DNS resolver | LAN with static lease | Replicated DNS configuration |
| `pihole2` | Raspberry Pi 1 A+ v1.1 / supported 32-bit Pi OS | Bare-metal secondary/peer Pi-hole DNS resolver | LAN with static lease | Replicated DNS configuration |

Hardware and OS versions must be confirmed in inventory facts before implementation. Friendly names above are placeholders and may be changed without changing role logic.

## 5. Support Decisions for the Raspberry Pis

### Raspberry Pi 3 B v1.2

Default K3s workers. Provision a 64-bit operating system so they use the `arm64` K3s path and the broadest practical container-image support. Require unique hostnames, enabled cgroups, stable power, adequate storage, and architecture-aware workload scheduling.

### Raspberry Pi 2 B v1.1

Conditional worker, not part of the initial cluster acceptance set.

As of this review, official K3s requirements list `armhf` as a supported architecture and publish ARM artifacts. That makes the Pi 2 an eligible candidate, not an automatic success. It must pass all of these gates:

1. `ansible_architecture` reports a compatible ARMv7/32-bit architecture.
2. The selected, actively maintained OS boots with required memory cgroups and systemd.
3. Available RAM and disk meet the K3s agent minimum before workload overhead.
4. The pinned K3s release includes a working `armhf` binary and required images.
5. The node joins, survives reboot, reports `Ready`, and completes a 72-hour lightweight workload soak.
6. Every workload allowed onto it has a compatible 32-bit ARM image and explicit scheduling rules.

If any gate fails, keep `rpi2` in an `experimental_nodes` group and exclude it from `k3s_workers_enabled`. Its failure must not block the supported cluster rollout.

### Raspberry Pi 1 A+ v1.1

Never include these nodes in K3s. Reserve them for bare-metal Pi-hole. Current Pi-hole prerequisites list `armv6` binaries and Raspberry Pi OS among supported targets, so this placement is supportable provided the chosen OS release is actively maintained. Validate performance, storage health, and update behavior on one Pi before enabling both as network DNS.

Time-sensitive source checks:

- [K3s installation requirements](https://docs.k3s.io/installation/requirements)
- [K3s releases](https://github.com/k3s-io/k3s/releases)
- [Pi-hole prerequisites](https://docs.pi-hole.net/main/prerequisites/)

Recheck these sources whenever the pinned K3s, Pi-hole, or Raspberry Pi OS version changes.

## 6. Network and Access Model

### LAN

- Give every infrastructure host a router reservation or a documented static address.
- Use local DNS names rather than embedding addresses throughout roles.
- Keep K3s API, pod/service CIDRs, DNS port 53, and SSH rules explicit.
- Bind K3s server/agent communication to the LAN for v1.
- Do not expose SSH, K3s, Pi-hole administration, databases, or pipeline interfaces directly to the public internet.

### Tailscale

Join exactly these machines initially:

- `macbook`
- `thinkpad`
- `thinkcentre`

Use Tailscale for remote administration and development access. Keep enrollment credentials out of Git, tag the two unattended Linux machines, define an ACL policy outside or alongside this repository as appropriate, and document key-expiry decisions. CachyOS is Arch-derived; use the distribution-supported Tailscale package path and verify the `tun` device and `tailscaled` service.

Official install references:

- [Tailscale on Linux](https://tailscale.com/docs/install/linux)
- [Tailscale on macOS](https://tailscale.com/docs/install/mac)

### SSH

- Use individual SSH keys; do not share a fleet-wide private key.
- Disable password authentication after key access and recovery access are proven.
- Restrict privileged access through `sudo` and named admin users.
- Decide whether to enable Tailscale SSH only after its ACL and recovery implications are documented.
- Preserve LAN SSH access to the Raspberry Pis from authorized operator machines so automation does not depend on the tailnet.

### DNS

- Give each Pi-hole a unique static LAN address.
- Configure the router/DHCP service to advertise both Pi-hole addresses only after both resolvers pass validation.
- Use a shared declarative source for blocklists, local DNS records, and common settings; keep identity-specific values in host vars.
- Do not use round-robin deployment as a substitute for testing one resolver at a time.
- Maintain a documented emergency DNS fallback for bootstrap and recovery.

## 7. Workload Placement Policy

| Workload type | Default placement | Rationale |
|---|---|---|
| Ansible control and scheduled maintenance | Any supported operator machine; optionally the ThinkPad | The inventory is not coupled to one permanent controller |
| K3s control plane and default SQLite datastore | ThinkPad host | Simple single-server cluster for v1 |
| Infrastructure databases | ThinkPad host with dedicated persistent paths | Avoid accidental scheduling on SD cards; make backups explicit |
| Pipeline orchestration control service | ThinkPad host initially | Keeps orchestration state on the managed infrastructure node |
| Small stateless services | K3s on Pi 3 workers, optionally ThinkPad | Matches the intended lightweight cluster use |
| Architecture-sensitive or heavier services | ThinkPad or constrained compatible nodes | Prevents invalid ARM scheduling |
| Remote development and agent execution | ThinkCentre host | Isolates development workloads from persistent infrastructure services |
| DNS filtering | Bare-metal Pi 1 pair | Keeps DNS independent from K3s availability |

Before deploying databases or the pipeline orchestrator, record the chosen products, data paths, ports, backup targets, restore commands, resource limits, and whether they run as systemd services or rootless containers. Do not place them in K3s by accident simply because manifests are convenient.

## 8. Ansible Inventory Model

Model capabilities with overlapping groups. The implementation may refine names, but should preserve these semantics:

```yaml
all:
  children:
    workstations:
      hosts: { macbook: {} }
    infra_hosts:
      hosts: { thinkpad: {} }
    execution_nodes:
      hosts: { thinkcentre: {} }
    tailscale_nodes:
      hosts: { macbook: {}, thinkpad: {}, thinkcentre: {} }
    k3s_servers:
      hosts: { thinkpad: {} }
    k3s_workers_supported:
      hosts: { rpi3a: {}, rpi3b: {} }
    k3s_workers_experimental:
      hosts: { rpi2: {} }
    pihole_nodes:
      hosts: { pihole1: {}, pihole2: {} }
    linux_nodes:
      children:
        infra_hosts: {}
        execution_nodes: {}
        k3s_servers: {}
        k3s_workers_supported: {}
        k3s_workers_experimental: {}
        pihole_nodes: {}
```

Avoid using the illustrative inline mapping style if a conventional expanded inventory is easier to maintain. The important rule is that behavior comes from membership. Guard against a host receiving duplicated common-role execution because it appears through multiple child groups.

Required inventory data includes:

- management and service addresses;
- OS family and expected architecture assertions;
- SSH user and privilege method;
- storage device/path declarations;
- K3s node labels, taints, and enablement flag;
- Pi-hole identity and peer settings;
- Tailscale tags without auth keys;
- dotfiles profile and pinned repository revision;
- backup classification and restore owner.

## 9. Dotfiles Repository Contract

Treat the separate dotfiles repository as a versioned dependency.

The homelab repository should own a wrapper role named conceptually `dotfiles` that:

1. installs prerequisites needed by the dotfiles installer;
2. clones or updates the external repository from a configured URL;
3. checks out a pinned tag or commit by default;
4. invokes the external repository's documented, noninteractive entry point;
5. selects a per-host profile such as workstation, infra, or execution node;
6. runs as the target user rather than root unless a step explicitly requires privilege;
7. reports changes accurately and is safe to rerun.

The dotfiles repository owns shell/editor/CLI preferences and user-level development configuration. This repository owns system packages, services, networking, storage, host security, and orchestration. If both repositories need the same tool, the system package belongs here and its user configuration belongs in dotfiles.

Inputs that must be supplied before implementing this role:

- dotfiles repository URL or local bootstrap path;
- supported operating systems and profiles;
- install command and noninteractive flags;
- secret-handling contract;
- a stable tag/commit to pin.

## 10. Planned Ansible Roles and Playbooks

### Roles

- `common`: hostname, time sync, base packages, users, SSH keys, sudo, locale, update policy.
- `storage`: mounts, permissions, disk-health tooling, persistent directory layout.
- `tailscale`: package, service, non-secret preferences, enrollment handoff, validation.
- `dotfiles`: external dotfiles dependency wrapper.
- `infra_host`: persistent infrastructure root and host utilities without assigning Ansible controller ownership.
- `execution_node`: headless development packages, T3 Code/Codex prerequisites, container/build tooling, workspace and cache paths, resource limits.
- `pihole`: bare-metal prerequisite checks, unattended install/configuration, peer-consistent settings, health validation.
- `k3s_prereqs`: cgroups, swap, networking, architecture checks, unique names.
- `k3s_server`: pinned server install, config, service, join-token source, kubeconfig handling.
- `k3s_agent`: secure token consumption, pinned agent install, labels/taints, service.
- `database_host`: persistent data directories and chosen database services after product decisions.
- `pipeline_orchestrator`: chosen orchestration service after product decisions.
- `backup_client` / `backup_controller`: backup jobs, retention, restore validation.
- `observability_agent`: host and service health once the monitoring target is chosen.

### Playbooks

- `infra-host.yml`: configure the ThinkPad's persistent host responsibilities without making it a mandatory Ansible controller.
- `base.yml`: common and storage configuration across applicable hosts.
- `tailscale.yml`: the three designated tailnet nodes only.
- `dotfiles.yml`: explicit user-environment step; never hidden inside `common`.
- `execution-node.yml`: ThinkCentre development runner.
- `dns.yml`: staged Pi-hole deployment and validation.
- `k3s.yml`: prerequisites, server, supported workers, and baseline validation.
- `k3s-admit-experimental.yml`: explicit Pi 2 preflight, admission, and recorded outcome; never called by `site.yml`.
- `data-platform.yml`: databases and pipeline orchestration after decisions are recorded.
- `backup.yml`: backup setup and restore probes.
- `site.yml`: ordered composition of stable playbooks, with disruptive or experimental actions excluded by default.
- `validate.yml`: read-only fleet, DNS, Tailscale, service, storage, and cluster checks.

## 11. Delivery Phases and Gates

### Phase 0 — Discovery and decisions

Deliver:

- hardware/OS/architecture fact sheet;
- IP reservations and naming map;
- disk and power assessment, especially SD-card health;
- dotfiles integration contract;
- secret-management choice;
- database, pipeline orchestrator, backup target, and observability decisions;
- current recovery access for every machine.

Gate: all hosts can be reached by at least one documented recovery method, and no role depends on an unknown storage or secret location.

### Phase 1 — Automation foundation

Deliver:

- `ansible.cfg`, pinned collections, inventory, group vars, host-var examples;
- working `bootstrap.sh`, `Makefile`, linting, syntax checks, and check-mode target;
- base and storage roles;
- secret placeholders and `.gitignore` rules;
- initial README and operator commands.

Gate: `ansible-inventory --graph`, syntax checks, and a base-role second run succeed without unexpected changes.

### Phase 2 — Primary computers

Deliver:

- ThinkPad as the persistent infrastructure host, independently of which machine invokes Ansible;
- Tailscale on MacBook, ThinkPad, and ThinkCentre;
- explicit dotfiles playbook for applicable users;
- hardened headless ThinkCentre with development workspaces and agent tooling;
- remote development smoke test from MacBook to ThinkCentre.

Gate: the MacBook can administer both Linux computers over Tailscale; the ThinkPad can administer all Linux nodes over LAN; the ThinkCentre can clone a test repository and complete its build/test command without privileged interactive setup.

### Phase 3 — Resilient DNS

Deliver:

- one Pi-hole provisioned and validated, then the second;
- declarative shared DNS configuration and per-node identities;
- router/DHCP configuration runbook;
- health checks and emergency resolver rollback.

Gate: either Pi-hole can independently resolve local and public names; disabling one does not interrupt a client configured with both; restoring configuration to a rebuilt node is demonstrated.

### Phase 4 — K3s cluster

Deliver:

- pinned K3s server on ThinkPad;
- two Pi 3 workers with architecture labels/constraints;
- secure token discovery and worker join;
- kubeconfig handling and cluster validation;
- optional Pi 2 admission playbook isolated behind an explicit flag/group limit;
- lightweight sample workload with multi-architecture image verification.

Gate: ThinkPad and both Pi 3 nodes remain `Ready` after reboot; a second run is idempotent; the sample workload lands only on compatible nodes. Pi 2 status is separately recorded as admitted or excluded.

### Phase 5 — Data and pipeline platform

Deliver:

- selected databases and pipeline orchestrator on ThinkPad;
- named volumes/paths, resource limits, health checks, and version pins;
- credentials from the chosen secret system;
- backup and tested restore procedure;
- documented client endpoints over LAN/Tailscale as appropriate.

Gate: each stateful service restores into a clean test location and passes an application-level query, not just a process check.

### Phase 6 — Operations and recovery

Deliver:

- fleet validation playbook;
- host, DNS, disk, backup, Tailscale, and K3s health visibility;
- patch and pinned-version upgrade runbooks;
- alert destinations and ownership;
- restore order: network/DNS, ThinkPad, K3s, databases/pipelines, execution node;
- periodic recovery drill checklist.

Gate: the operator can identify a failed component, locate its backup, and follow a tested recovery path without relying on the failed component itself.

## 12. Validation Strategy

Every role must define preflight, convergence, and service-level checks.

Minimum automation checks:

- YAML lint, Ansible lint, syntax check, and inventory validation;
- check mode where modules and target software permit it;
- idempotency: a second normal run has no unexplained changes;
- OS-family and architecture assertions before package or binary installation;
- service enabled/running checks plus actual protocol checks;
- reboot persistence tests for ThinkPad, ThinkCentre, Pi-hole nodes, and K3s nodes;
- backups verified by restore, not by archive existence alone;
- destructive maintenance behind explicit tags/variables and confirmation documentation.

Service-level acceptance examples:

- Tailscale: expected three nodes appear and can reach only intended services.
- Pi-hole: DNS queries succeed through either resolver and block policy is consistent.
- K3s: expected nodes are `Ready`, architecture labels are correct, and a multi-arch smoke workload completes.
- Database: create, read, backup, restore, and read again.
- Pipeline: submit a test run, observe completion, and retrieve logs/artifacts.
- ThinkCentre: complete a remote agentic-development smoke workflow without touching ThinkPad service capacity.

## 13. Security and Secret Handling

- Never commit Tailscale auth keys, K3s tokens, kubeconfigs, Pi-hole passwords, database credentials, API keys, SSH private keys, or backup repository keys.
- Prefer short-lived or reusable-tagged Tailscale enrollment keys according to the chosen ACL policy; document the tradeoff.
- Read the K3s token from `/var/lib/rancher/k3s/server/node-token` at runtime and use `no_log` around propagation.
- Store fetched kubeconfig with least privilege and rewrite its endpoint intentionally.
- Encrypt any repository-managed secrets with the selected mechanism; Ansible Vault is acceptable for the first implementation if no external manager is chosen.
- Separate daily user accounts from service accounts and scope `sudo` narrowly.
- Pin third-party repositories and verify downloads/checksums where supported.
- Keep infrastructure administration interfaces on LAN/Tailscale and configure host firewalls from an explicit port matrix.
- Back up secrets in a recovery-safe form separate from the machines that consume them.

## 14. Target Repository Shape

```text
.
├── .context/
│   ├── homelab-bootstrap-spec.md
│   └── k3s-cluster-spec.md
├── ansible/
│   ├── ansible.cfg
│   ├── requirements.yml
│   ├── inventories/production/
│   │   ├── hosts.yml
│   │   ├── group_vars/
│   │   └── host_vars/              # non-secret values or encrypted files only
│   ├── playbooks/
│   │   ├── infra-host.yml
│   │   ├── base.yml
│   │   ├── tailscale.yml
│   │   ├── dotfiles.yml
│   │   ├── execution-node.yml
│   │   ├── dns.yml
│   │   ├── k3s.yml
│   │   ├── k3s-admit-experimental.yml
│   │   ├── data-platform.yml
│   │   ├── backup.yml
│   │   ├── validate.yml
│   │   └── site.yml
│   └── roles/
├── bootstrap/
│   ├── lib/                         # shared preparation and Ansible helpers
│   ├── platforms/                   # local OS-specific preparation
│   └── profiles/                    # playbook dispatch and safe limits
├── docs/
│   ├── homelab-plan.html
│   └── runbooks/
├── files/                           # non-secret managed files
├── scripts/
├── tests/
├── Makefile
├── README.md
└── bootstrap.sh
```

Do not create empty role trees in bulk. Add each role with its defaults, argument validation, handlers, tests, and documentation when its phase begins.

## 15. Explicit Non-Goals for the First Stable Release

- High-availability K3s control planes or etcd quorum.
- Adding the ThinkCentre or Pi-hole machines to K3s.
- Making the Pi 2 part of baseline cluster success.
- Running Pi-hole in Kubernetes or containers.
- Public ingress to homelab admin services.
- Automatic router reconfiguration unless the router and rollback path are deliberately brought into scope.
- Selecting database, pipeline, backup, GitOps, or observability products without an operator decision.
- Copying or vendoring the dotfiles repository into this repository.

## 16. Decisions Still Required

Resolve these during Phase 0 and record the answers in inventory/group vars or an architecture decision record:

1. Exact hardware names, RAM, disks, current OS versions, and desired rebuild OS images.
2. LAN subnet, reservations, local domain, router/DHCP capabilities, and emergency DNS.
3. Whether the ThinkPad uses the K3s default SQLite datastore or another supported datastore.
4. Which databases and pipeline orchestration platform are required.
5. Host-service runtime for stateful tools: native systemd packages or rootless containers.
6. Backup repository target, retention, encryption, and off-machine/off-site copy.
7. Secret system: Ansible Vault for v1 or an external secret manager.
8. Tailscale ACL/tags, Tailscale SSH choice, key expiry, and Mac client variant.
9. Dotfiles repository URL, installer, profiles, pin, and secret boundaries.
10. ThinkCentre workspace isolation, storage cleanup, and concurrency/resource policy for agents.
11. K3s ingress, storage class, bundled component policy, and GitOps timing.
12. Monitoring stack and notification destination.

## 17. Instructions for Future Agents

1. Read this file first, then `.context/k3s-cluster-spec.md` for the Phase 4 K3s implementation contract.
2. Work one delivery phase at a time and do not silently select products listed as unresolved.
3. Keep changes within this repository unless the operator explicitly authorizes changes to the dotfiles repository, router, tailnet policy, or live hosts.
4. Preserve group-driven behavior and mixed-architecture preflight checks.
5. Do not add the Pi 2 to the default K3s worker set. Admission is an explicit test result.
6. Do not add either Pi 1 to K3s. They are bare-metal DNS appliances.
7. Keep the ThinkCentre out of K3s; its primary purpose is remote agentic development.
8. Prefer Ansible modules and templates over shell commands; explain unavoidable commands.
9. Never commit live addresses if the repository is intended to be public, and never commit secrets under any circumstances.
10. Validate idempotency and the relevant service protocol before declaring a phase complete.
11. Update this plan, the HTML view, README usage, and runbooks when architectural decisions change.
12. Treat all support claims as time-sensitive at upgrade boundaries and verify official sources again.

## 18. Full-Plan Definition of Done

The broadened homelab baseline is complete when:

- the MacBook can bootstrap or recover the ThinkPad;
- the ThinkPad can idempotently configure every Linux host over the LAN;
- the MacBook, ThinkPad, and ThinkCentre are reachable through the intended Tailscale policy;
- dotfiles are applied from the external repository through a pinned, explicit Ansible step;
- the ThinkCentre passes a remote agentic-development smoke test;
- both Pi-hole nodes can independently serve DNS and can be rebuilt from code plus encrypted configuration;
- the ThinkPad K3s server and two Pi 3 workers recover after reboot and pass workload validation;
- the Pi 2 has a documented admitted/excluded result without affecting baseline success;
- databases and pipeline orchestration have named state, health checks, backups, and tested restores;
- validation and recovery runbooks do not depend on the component they are meant to recover;
- a second full stable playbook run reports no unexplained changes;
- no sensitive value exists in repository history or generated documentation.
