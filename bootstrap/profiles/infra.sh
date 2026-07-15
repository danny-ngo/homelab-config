#!/usr/bin/env bash

# Apply every stable play in which the infrastructure host participates. The
# inventory limit prevents this profile from converging the rest of the fleet.
bootstrap_run_playbook ansible/playbooks/site.yml infra_hosts
