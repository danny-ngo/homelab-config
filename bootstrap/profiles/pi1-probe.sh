#!/usr/bin/env bash

# Pi 1 nodes use distribution Python and deliberately skip the standard
# uv-managed Linux baseline.
bootstrap_run_playbook ansible/playbooks/pi1-probe.yml pi1_probe_nodes
