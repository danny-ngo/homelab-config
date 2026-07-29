# 0002: Raspberry Pi DNS and constrained edge nodes

- Status: accepted, with Pi 2 deployment form reopened
- Date: 2026-07-28
- Last reviewed: 2026-07-29

## Decision

Both Raspberry Pi 1 Model A+ boards are confirmed to have 256 MB RAM. Do not
run Pi-hole on either one: they are below Pi-hole's supported 512 MB minimum.
A smaller operating system does not change that product requirement, so neither
DietPi nor Alpine makes these boards supported Pi-hole hosts. Keep both outside
managed inventory because the repository's uv-managed Python bootstrap also
does not support ARMv6.

Retain the bare-metal Pi-hole role for future hosts with at least 512 MB RAM.
For Raspberry Pi replacement hardware, prefer current Raspberry Pi OS Lite
32-bit unless the operator deliberately chooses DietPi's additional management
layer. When two supported hosts exist, keep DHCP on the router and advertise
both resolver addresses through DHCP option 6. Treat them as independent
resolvers managed from the same Ansible source of truth, not as a stateful
Pi-hole cluster.

Reserve the 1 GB Raspberry Pi 2 Model B for Pi-hole. It is the first and
currently only selected resolver; do not schedule unrelated workloads on it.
The existing Ansible implementation deploys Pi-hole on bare-metal Raspberry Pi
OS Lite 32-bit and therefore keeps the Pi 2 out of the K3s worker group. A
dedicated K3s-agent topology running only the Pi-hole pod is feasible and is no
longer rejected on memory grounds, but it needs a separate workload definition
for networking, persistence, resource limits, and node placement before the
inventory can safely select it. Keep the router's current DNS configuration
until the chosen form passes direct validation; select a second supported
resolver later before claiming DNS redundancy.

Arch Linux does not install Docker as part of its base system. The execution
node role therefore owns installation and startup of `docker`, `docker-buildx`,
and `docker-compose`.

Use mixed deployment forms on the x86 hosts rather than adding a VM layer
without a concrete isolation requirement. T3 Code and its development
toolchains run directly on the always-on ThinkCentre. Databases run in Docker
containers on the ThinkPad with explicit persistent paths and backups.

## Pi-hole evidence and alternatives

Raspberry Pi 1 Model A+ boards use a single-core BCM2835 (ARMv6), have one USB
port, no built-in Ethernet, and exist in both 256 MB and 512 MB variants. Both
installed boards were physically confirmed as the 256 MB variant. Pi-hole
publishes an ARMv6 FTL binary, but its current minimum is 512 MB RAM and 2 GB
free storage. CPU compatibility therefore does not imply sufficient memory:

```sh
cat /proc/device-tree/model; printf '\n'
awk '/Revision|Model/ {print}' /proc/cpuinfo
vcgencmd get_mem arm
vcgencmd get_mem gpu
free -m
uname -m
```

The usable total reported by `free` is lower because it excludes reserved
memory. Do not lower
`pihole_minimum_memory_mb` or use swap to force a board through the playbook:
swap does not satisfy Pi-hole's RAM requirement and would make DNS latency and
microSD wear less predictable.

### Raspberry Pi OS Lite versus DietPi

Both are Debian-family systems using APT and systemd. DietPi's advantage is a
smaller, appliance-oriented starting point and a curated management layer, not
a different Pi-hole memory requirement.

| Concern | Raspberry Pi OS Lite 32-bit | DietPi ARMv6 |
| --- | --- | --- |
| Hardware support | Official Raspberry Pi OS, kernel, firmware, and tooling; Lite is intended for headless and older Pis | DietPi explicitly provides a Pi 1/Zero ARMv6 image, based on Debian with DietPi scripts and defaults |
| Initial footprint | Lean headless vendor image, but includes more Raspberry Pi defaults and integration | More aggressively minimal; optional components and services are installed through DietPi tools |
| Operational model | Standard APT, systemd, `raspi-config`, and Raspberry Pi documentation; best fit for the existing Ansible roles | APT and systemd remain underneath, but `dietpi-*` tools form a second configuration and lifecycle layer |
| Automation ownership | Ansible can directly own packages, services, network settings, and Pi-hole | Must decide whether DietPi recipes or Ansible own each setting; using both for the same application risks configuration drift |
| Logging and SD writes | Conventional journald/package logging unless explicitly tuned | DietPi-RAMlog can keep `/var/log` in RAM, reduce SD writes, and discard logs hourly; persistent RAMlog and full-disk logging are alternatives |
| Troubleshooting | Broader Raspberry Pi community guidance generally applies directly | DietPi defaults can explain missing historical logs, nonstandard application ports, or settings that differ from upstream |
| Updates | `apt full-upgrade` within a release; Raspberry Pi recommends reimaging for a major OS upgrade | `dietpi-update` updates the DietPi layer and reports APT updates; Debian base upgrades and application updates remain separate concerns |
| Best fit | Predictable, conventional, Ansible-owned server | Very small appliance where the operator intentionally adopts DietPi's tools and conventions |

DietPi-specific management behavior that matters here:

- `dietpi-software` installs curated application recipes and may configure the
  application, related packages, ports, credentials, and integrations. It is
  more than a package selector.
- `dietpi-config` manages OS and board settings including network configuration
  and static DNS. These settings can overlap with Ansible or manual files.
- `dietpi-services` wraps systemd service control and can set service modes and
  priority levels. Standard `systemctl` still exists.
- `dietpi-update` updates DietPi scripts separately from normal Debian packages.
  Pi-hole itself still has its own `pihole -up` update path.
- `dietpi-backup` stops services during backup. Moved DietPi userdata can be
  excluded unless explicitly included, so backup scope and downtime must be
  reviewed.
- DietPi-RAMlog can reduce microSD writes, but the default volatile mode clears
  logs hourly. That is efficient during normal operation and less useful during
  post-reboot or delayed incident investigation.
- DietPi's Pi-hole recipe uses the official installer but changes the web UI to
  port `8089`, uses the DietPi global software password, disables the text query
  log, and retains two days of query database history. The latter two are
  sensible resource settings already mirrored by this Ansible role.
- DietPi mounts `/tmp` as tmpfs. Large gravity lists can exhaust it; on a
  256 MB machine this makes aggressive lists especially unsuitable.

If DietPi is chosen for a future supported resolver, choose one owner for
Pi-hole installation. Either use `dietpi-software` and teach Ansible to validate
and manage the resulting DietPi conventions, or use the existing Ansible
bare-metal role and do not install Pi-hole through DietPi. The current
recommendation is Raspberry Pi OS Lite plus Ansible because it has one
configuration owner and less platform-specific behavior.

Alpine remains the smallest base option, but introduces OpenRC and musl while
the rest of this fleet and the existing roles use Debian-family conventions.
The official Pi-hole container also has an ARMv6 image, but Docker cannot make
256 MB supported and adds another runtime layer. Neither alternative changes
the exclusion decision.

For future supported hosts, the role uses Pi-hole's official unattended
bare-metal installer from a pinned Core tag. The pin makes the reviewed
installer input reproducible; it does not pin the complete installed stack.
Pi-hole's installer resolves its Core, Web, and FTL components through upstream
release channels, and this role deliberately does not run `pihole -up`
automatically. Review release notes, back up `/etc/pihole`, and perform upgrades
as a separate maintenance action.

Resource-oriented settings disable the duplicate text query log, retain two
days of database history, use a 5,000-entry cache, cap web/API concurrency, and
disable Pi-hole's optional NTP client/server. The web interface remains
available. Ansible renders the authoritative local records, upstreams,
interface, and password hash.

Sources:

- [Pi-hole prerequisites](https://docs.pi-hole.net/main/prerequisites/)
- [Pi-hole installation methods](https://docs.pi-hole.net/main/basic-install/)
- [Pi-hole v6 configuration reference](https://docs.pi-hole.net/ftldns/configfile/)
- [Official Pi-hole Docker configuration](https://docs.pi-hole.net/docker/)
- [Raspberry Pi model table](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
- [Raspberry Pi processor documentation](https://www.raspberrypi.com/documentation/computers/processors.html)
- [Raspberry Pi OS downloads and compatibility](https://www.raspberrypi.com/software/operating-systems/)
- [Raspberry Pi OS documentation](https://www.raspberrypi.com/documentation/computers/os.html)
- [DietPi Raspberry Pi support](https://dietpi.com/docs/hardware/)
- [DietPi tools and first-run model](https://dietpi.com/docs/getting_started/)
- [DietPi system maintenance](https://dietpi.com/docs/dietpi_tools/system_maintenance/)
- [DietPi service management](https://dietpi.com/docs/dietpi_tools/system_configuration/)
- [DietPi logging choices](https://dietpi.com/docs/software/log_system/)
- [DietPi Pi-hole behavior](https://dietpi.com/docs/software/dns_servers/)
- [Alpine Linux downloads](https://www.alpinelinux.org/downloads/)

## DNS availability model

After two supported resolver hosts are selected and validated, the router
should advertise only the two Pi-hole addresses. Until then, leave its existing
DNS settings unchanged. DHCP option 6 can carry an ordered list of DNS servers,
but client resolvers decide how they use that list. Some prefer the first, some
distribute queries, and some take time to retry after a failure. This is
redundant service discovery with client-controlled failover and incidental load
sharing; it is not deterministic active/passive HA.

A floating address using keepalived was rejected. DNS has no session state to
preserve, both resolvers are already acceptable endpoints, and a VIP adds
health-check and failover machinery to resource-constrained nodes. It would
also hide whether clients can actually use the second address.

Pi-hole runtime databases and query history are not synchronized. Shared
configuration is rendered from this repository and secrets from Vault. Make
allowlist, denylist, blocklist, and local-record changes in inventory-backed
configuration rather than independently in each web UI. Continue deploying
with `serial: 1`. Do not advertise a public resolver as a third DHCP DNS entry,
because clients could bypass Pi-hole filtering while both nodes are healthy.

Keep DHCP on the router. Running split or failover DHCP on the resolver hosts
would add state coordination and couple network address assignment to the DNS
deployment. If the router cannot advertise two DNS addresses, replace or
reconfigure that DHCP service before adding VIP complexity to Pi-hole.

Use separate power supplies and, where practical, separate power outlets. A
shared router/switch remains a common dependency. Prefer wired Ethernet for
stable latency and predictable recovery.

The DHCP DNS server option is defined by
[RFC 2132 section 3.8](https://datatracker.ietf.org/doc/html/rfc2132#section-3.8).

## Raspberry Pi 1 disposition

The Pi 1 boards can still be useful when their role is optional, tolerant of
slow ARMv6 hardware, and does not depend on this repository's Python bootstrap.
Rank the practical options as follows:

1. A GPIO sensor or actuator node running a very small OS and a C, Go, or shell
   daemon. Publish low-rate temperature, contact, or power telemetry through a
   USB Wi-Fi adapter; do not make alerting or automation safety depend on it.
2. A local e-ink/LCD status display, clock, or simple information radiator.
   Cache the last display state so a network or SD-card failure has no wider
   effect.
3. A lab-only ARMv6 compatibility target for cross-compiled binaries, Linux
   fundamentals, GPIO experiments, or retro-computing projects.
4. A secondary GPS-backed NTP experiment using GPIO/UART for the receiver and
   USB for networking. Treat it as an additional time source, never the only
   one.
5. A powered-off spare or donor board if none of those projects is genuinely
   useful; this avoids ongoing SD-card, adapter, and maintenance costs.

Avoid Pi-hole, DHCP, routing, storage, databases, monitoring control planes, and
other core services. A Pi 1 A+ has no built-in Ethernet and only one USB port,
so projects needing both USB networking and another USB peripheral also need a
powered hub. Any managed deployment would require a documented ARMv6 exception
using the distribution Python rather than the standard uv-managed Python 3.14
bootstrap.

## Raspberry Pi 2 role selection

The memory gate is resolved: both Pi 1 boards have 256 MB, so the 1 GB Pi 2 is
the single dedicated Pi-hole node. Its service role is settled; its deployment
form is reopened. A K3s worker that runs only Pi-hole is materially different
from a server or general-purpose worker and meets K3s's published one-core,
512 MB agent baseline.

That baseline explicitly excludes workload consumption. Pi-hole also publishes
a 512 MB minimum, but these values are compatibility floors rather than
additive reservations. A 1 GB node can work, but it must be measured under
gravity updates, query bursts, container image extraction, K3s upgrades, and
restarts. Keep monitoring control planes off the Pi 2 and do not infer spare
capacity from the fact that it passes each minimum independently.

### Deployment form and monitoring interoperability

The extra RAM above Pi-hole's minimum is operating margin, cache, and recovery
headroom; it is not by itself a reason to add an orchestration layer. The
worker-only topology makes K3s reasonable when the lab already values
Kubernetes-native deployment, resource controls, and centralized workload
management. Label and taint the node for DNS, add matching placement rules,
define requests and limits from measured usage, and make persistence and port
53 exposure explicit. A drain, CNI failure, control-plane dependency, or node
reboot still becomes a DNS event, so this does not replace a second resolver.

Standalone Docker remains the simplest containerized option on ARMv7. It
provides an image-based upgrade/rollback unit and direct container visibility
to Portainer, while avoiding the Kubernetes control-plane and CNI dependency.
Bare metal remains the smallest operational surface and the only deployment
form currently implemented in this repository. Choose K3s for cluster-native
operations, Docker for a single remotely managed container host, or bare metal
for maximum DNS independence; RAM alone does not select among them.

Monitoring does not require Pi-hole to share the monitor's deployment form:

| Monitor | Bare-metal Pi-hole | Docker Pi-hole | K3s Pi-hole |
| --- | --- | --- | --- |
| Uptime Kuma | Preferred compatibility: query the Pi 2 directly with a DNS monitor; optionally add HTTP(S) and ping checks | Same service checks, plus a Docker-container monitor if the Docker API is deliberately exposed | Same service checks; cluster visibility is separate |
| Pulse | The unified Linux agent is published for ARMv7 and can report the Pi as a standalone machine | Adds Docker/container inventory when the agent has Docker socket access | Supports Kubernetes monitoring through its cluster agents |
| Portainer | No Pi-hole workload visibility; Portainer is a container/cluster manager, not a DNS availability check | Full container lifecycle visibility through an ARMv7 Agent or Edge Agent | Add the cluster once through the Kubernetes agent; Portainer then sees the Pi-hole workload and its Pi 2 placement |

Use Uptime Kuma on another always-on node for the actual availability signal:
perform a DNS query through the Pi 2 rather than checking only ICMP or TCP port
53. A web-interface check is useful but secondary because the dashboard can be
healthy while resolution is broken. Pulse is a compatible optional host
telemetry layer because its current releases include an ARMv7 agent. Portainer
adds value only if Pi-hole is containerized and still does not replace an
end-to-end DNS query.

For standalone Docker, prefer Portainer's Edge Agent when the Portainer server
can expose its tunnel endpoint; it does not require an inbound agent port on the
Pi 2. The standard Agent is also available for ARMv7 but requires the server to
reach port 9001 on the Pi. For K3s, do not install Docker merely for Portainer:
K3s uses containerd. Add the Kubernetes environment once, not each node. The
Portainer cluster agent can run on an x86_64 or ARM64 cluster node and manage
the Pi 2 workload through the Kubernetes API.

Portainer CE 2.39 publishes compatibility for Kubernetes 1.32 through 1.34.
The repository therefore pins K3s `v1.34.9+k3s1` rather than 1.35 while this
integration is required. Portainer publishes ARMv7 images, although its primary
tested architecture matrix lists ARM64 and x86_64; validate the selected agent
tag on the Pi before relying on standalone Docker management.

Do not expose an unauthenticated Docker TCP socket merely to gain remote
monitoring. Uptime Kuma documents that Docker socket/API access grants control
of the daemon; Portainer and Pulse provide agents for their container-aware
paths. Keep the monitoring service on a different node so a Pi 2 failure cannot
take down both DNS and its observer.

Sources:

- [K3s requirements](https://docs.k3s.io/installation/requirements)
- [Official Pi-hole Docker deployment](https://docs.pi-hole.net/docker/)
- [Uptime Kuma Docker monitoring](https://github.com/louislam/uptime-kuma/wiki/How-to-Monitor-Docker-Containers)
- [Pulse monitoring and agent model](https://github.com/rcourtman/Pulse)
- [Pulse installation guide](https://github.com/rcourtman/Pulse/blob/main/docs/INSTALL.md)
- [Portainer Docker environment options](https://docs.portainer.io/admin/environments/add/docker)
- [Portainer Kubernetes agent](https://docs.portainer.io/admin/environments/add/kubernetes/agent)
- [Portainer requirements and compatibility matrix](https://docs.portainer.io/start/requirements-and-prerequisites)
- [Portainer ARM architecture support](https://docs.portainer.io/faqs/installing/which-arm-architectures-does-portainer-support)

## X86 deployment forms and source durability

Do not introduce VMs until a service has a concrete kernel, operating-system,
security, snapshot, or migration requirement that containers or host processes
cannot satisfy. The current split is:

- ThinkCentre: always-on remote development server; T3 Code, language
  toolchains, and agent CLIs run directly on the host.
- ThinkPad: persistent infrastructure host; databases run as Docker containers
  with definitions under `/srv/infra/containers` and data under
  `/srv/infra/data`.

Container images and writable layers are replaceable. Each database still
requires a service-specific image/version decision, named data path, ownership,
resource limits, health check, network exposure, credential source, backup, and
tested restore. Docker-published ports can interact unexpectedly with host
firewall policy, so database ports must be bound and filtered deliberately
rather than exposed by default.

The ThinkCentre is always on but remains rebuildable. GitHub is the durable
source of truth for project source. Active branches are pushed at meaningful
checkpoints, before switching machines, before maintenance, and at session end.
Agents must not automatically commit or push an unreviewed working tree.
Secrets, caches, databases, and generated artifacts remain outside Git and need
separate backup if they are irreplaceable. See the
[ThinkCentre workspace runbook](../runbooks/thinkcentre-workspaces.md).

## Arch Linux and Docker

The Arch `base` package is a minimal system definition and does not depend on
Docker. Docker is a separate package in the `extra` repository, the daemon must
be enabled explicitly, and Buildx is packaged as `docker-buildx` (not the
Debian/Ubuntu-style `docker-buildx-plugin` name).

The repository already makes Docker part of the ThinkCentre execution-node
profile: Ansible installs the three packages, renders bounded log settings,
enables `docker.service`, and adds the execution user to the `docker` group.
Rootful Docker and this root-equivalent group access are accepted for the
trusted execution-node account and the agents running as that account. Rootless
Docker is not required. A newly added group membership requires a fresh login
session.

Verification:

```sh
pacman -Q docker docker-buildx docker-compose
systemctl is-enabled docker
systemctl is-active docker
docker version
docker buildx version
docker compose version
```

Sources:

- [Arch base package](https://archlinux.org/packages/core/any/base/)
- [Arch Docker package](https://archlinux.org/packages/extra/x86_64/docker/)
- [Arch Docker installation guidance](https://wiki.archlinux.org/title/Docker#Installation)
- [Arch Docker Buildx package](https://archlinux.org/packages/extra/x86_64/docker-buildx/)
- [Docker Engine firewall considerations](https://docs.docker.com/engine/install/debian/#firewall-limitations)

## Remaining implementation inputs

The operator inputs that remain after this decision—Pi 2 deployment form,
second-resolver selection, router behavior, upstream/local DNS policy, and
final Pi 1 disposition—are tracked only in
[Open homelab decisions](open-decisions.md). That file is the canonical
backlog; this accepted record retains the rationale and settled role selection.

## Consequences

- The Pi 2 is the selected first Pi-hole host; deployment still requires
  production addresses, interface confirmation, upstream policy, and a vaulted
  web password hash.
- With two future hosts, DNS can remain available during one Pi-hole update or
  node failure, subject to client retry behavior and shared dependencies.
- Both 256 MB Pi 1 boards are excluded from production DNS and managed
  inventory, but remain candidates for optional lightweight projects.
- Raspberry Pi OS and bare metal use more disk than Alpine alone but reduce
  operational variance and runtime layers.
- The Pi 2 remains outside the example K3s worker group until a K3s Pi-hole
  workload and its resource, persistence, networking, and placement policy are
  implemented.
- Docker availability on Arch is reproducible through Ansible rather than an
  assumption about the installation image.
