---
layout: default
title: K3s worker setup
---

# K3s worker setup

Use this guide to add a supported Linux node as a K3s worker. The MacBook
controller and Ansible install and configure the K3s agent; you prepare the
node's operating system, network identity, and SSH access first. The ThinkPad
must already be installed as the cluster's single K3s server.

The current supported workers are the 64-bit Raspberry Pi 3 nodes in the
`k3s_workers_supported` inventory group. The Pi 2 and Pi 1 boards are not
supported workers in the current configuration.

## 1. Prepare the node

Install a supported 64-bit Debian-family OS and give the node a unique,
persistent hostname. Connect it to the same LAN as the ThinkPad and reserve a
stable LAN address. Ensure systemd is in use and the memory cgroup controller
is enabled. The configured minimum memory for an agent is 512 MB.

Create or select the unprivileged `homelab` administrator account with sudo
access. From the MacBook, verify SSH access and verify the host key through the
node's console or another trusted channel before accepting it into
`~/.ssh/known_hosts`. Do not disable strict host-key checking for normal runs.

On a fresh Linux node, run the documented curl installer locally as that
administrator. It prepares Linux prerequisites and stops; it does not install
Ansible or configure K3s. See [Bootstrap Python, Ansible, and uv
flow](../bootstrap-python-flow.md).

## 2. Add the worker to production inventory

Edit `ansible/inventories/production/hosts.yml`. Add the node under
`k3s_workers_supported` and make sure it is also included in the `linux_nodes`
children (the inventory's `linux_nodes` group normally includes the complete
`k3s_workers_supported` group):

```yaml
k3s_workers_supported:
  hosts:
    pi3a:
      ansible_host: 192.0.2.31
      expected_os_family: Debian
      expected_architecture: aarch64
      k3s_node_address: 192.0.2.31
```

Replace the example name and address with the node's real hostname and LAN
address. `ansible_host` is where SSH connects; `k3s_node_address` is the
address K3s advertises to the cluster. Keep it unique, reachable from the
ThinkPad, and on the LAN. Match `expected_architecture` to the facts Ansible
reports for the installed 64-bit OS (`aarch64` for the supported Pi 3 setup).
Keep the node out of `k3s_servers`; the configured topology has one server.

No K3s join token or K3s-specific vault value is needed in inventory. The
playbook reads the token from the ThinkPad at run time, keeps it in Ansible
memory for that run, and suppresses task output containing it.

## 3. Apply the Linux baseline

From the repository on the MacBook, check and apply the common Linux baseline
to the new worker:

```sh
make check PLAYBOOK=ansible/playbooks/base.yml LIMIT=pi3a
make apply PLAYBOOK=ansible/playbooks/base.yml LIMIT=pi3a
```

Use the inventory hostname in place of `pi3a`. Resolve any package, SSH,
firewall, storage, or privilege errors before continuing.

## 4. Install the K3s agent

Check and apply the K3s playbook with both the ThinkPad and worker in the
limit. Including the server lets Ansible read its current join token during
this run:

```sh
make check PLAYBOOK=ansible/playbooks/k3s.yml LIMIT=thinkpad,pi3a
make k3s LIMIT=thinkpad,pi3a
```

Replace `pi3a` with the inventory hostname. The playbook prepares the K3s
nodes, converges the ThinkPad server, downloads the checksum-verified agent,
writes its configuration, and enables and starts `k3s-agent`. The agent joins
the server at the configured LAN address. No manual token copy or `k3s agent`
command is required.

If the prerequisite check reports that the memory cgroup controller is
disabled, enable it using the distribution's boot configuration, reboot the
worker, and rerun the check. The playbook reports other unsupported hardware,
network overlap, or topology settings before installing the agent.

## 5. Confirm the worker joined

Wait for the node to become Ready, then inspect the cluster and validate the
worker roles:

```sh
ssh thinkpad 'sudo k3s kubectl wait node/pi3a --for=condition=Ready --timeout=5m'
ssh thinkpad 'sudo k3s kubectl get nodes -o wide'
make validate LIMIT=pi3a
```

Check that the node name, architecture, and LAN address are correct. If it
does not become Ready, inspect the agent service and logs on the worker and
the server logs on the ThinkPad:

```sh
ssh pi3a 'sudo systemctl --no-pager status k3s-agent'
ssh pi3a 'sudo journalctl -u k3s-agent -b --no-pager'
ssh thinkpad 'sudo journalctl -u k3s -b --no-pager'
```

Do not paste node-token contents, kubeconfig contents, or secret-bearing logs
into tickets or chat. For replacing or rejoining an existing worker, follow
[K3s administration and recovery](k3s-recovery.md) so stale cluster state is
removed in the right order.
