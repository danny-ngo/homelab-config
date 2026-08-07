---
layout: default
title: Vault and access
---

# Vault and access

Secrets remain in Ansible Vault; host-key checking stays strict. Linux uses
vaulted auth keys for first-time tagged Tailscale enrollment, then reapplies
the complete non-secret client preferences without reusing the key while the
node remains authenticated. Tailscale DNS acceptance and Tailscale SSH are
disabled, retaining OpenSSH/LAN recovery.
