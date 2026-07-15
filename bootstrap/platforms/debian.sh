#!/usr/bin/env bash

# Debian-family hosts need uv, Git, and OpenSSH before Ansible can prepare the
# project environment. uv is deliberately required rather than installed via a
# remote pipe; install it using the distribution/site-approved method first.
bootstrap_prepare_ansible
