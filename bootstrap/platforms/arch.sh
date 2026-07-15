#!/usr/bin/env bash

if [[ "$BOOTSTRAP_DRY_RUN" != true && ! -x "$(command -v uv 2>/dev/null || true)" ]]; then
  bootstrap_require_command sudo
  bootstrap_require_command pacman
  bootstrap_run sudo pacman --sync --needed --noconfirm uv git openssh
fi
bootstrap_prepare_ansible
