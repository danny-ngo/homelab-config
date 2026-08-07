#!/usr/bin/env bash

if [[ "$BOOTSTRAP_DRY_RUN" == true ]] ||
  ! command -v uv >/dev/null 2>&1 ||
  ! command -v git >/dev/null 2>&1 ||
  ! command -v ssh >/dev/null 2>&1 ||
  ! command -v python3 >/dev/null 2>&1; then
  if [[ "$BOOTSTRAP_DRY_RUN" != true ]]; then
    bootstrap_require_command sudo
    bootstrap_require_command pacman
  fi
  bootstrap_run sudo pacman --sync --needed --noconfirm uv git openssh python
fi
bootstrap_prepare_managed_node
