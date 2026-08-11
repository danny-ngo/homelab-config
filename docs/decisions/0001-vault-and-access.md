---
layout: default
title: Vault and access
---

# Vault and access

Secrets remain in Ansible Vault; host-key checking stays strict. Prefer
enrolling Linux nodes with Tailscale on the device itself before the first
Ansible run. When a node is already authenticated, Ansible reapplies the
complete non-secret client preferences without requiring or reusing an auth
key. A vaulted auth key is the unattended fallback when the client reports that
it needs login or has no usable state. Tailscale DNS acceptance and Tailscale
SSH are disabled, retaining OpenSSH/LAN recovery.
