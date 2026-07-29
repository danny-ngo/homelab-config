#!/usr/bin/env bash

# Apply the baseline before the dedicated DNS role. The inventory limit keeps
# unrelated site plays from touching other hosts.
bootstrap_run_playbook ansible/playbooks/site.yml pihole_nodes
