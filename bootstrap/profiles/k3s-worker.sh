#!/usr/bin/env bash

# The server must participate so its runtime join token is available to the
# selected workers. An explicit --limit is combined with the server group.
worker_limit="${BOOTSTRAP_LIMIT:-k3s_workers_supported}"
BOOTSTRAP_LIMIT="k3s_servers:${worker_limit}"
bootstrap_run_playbook ansible/playbooks/k3s.yml k3s_cluster
