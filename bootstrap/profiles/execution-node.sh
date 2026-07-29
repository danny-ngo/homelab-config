#!/usr/bin/env bash

# Apply the baseline followed by every stable purpose-specific play in which
# the selected execution node participates.
bootstrap_run_playbook ansible/playbooks/site.yml execution_nodes
