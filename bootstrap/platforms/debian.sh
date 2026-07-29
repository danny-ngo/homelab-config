#!/usr/bin/env bash

# System Python is retained for Ansible module execution. uv itself is
# installed system-wide, while uv-managed Python and its global pin belong to
# the administrator account running this initial bootstrap.
if [[ "$BOOTSTRAP_DRY_RUN" == true ]] ||
  ! command -v curl >/dev/null 2>&1 ||
  ! command -v git >/dev/null 2>&1 ||
  ! command -v ssh >/dev/null 2>&1 ||
  ! command -v python3 >/dev/null 2>&1; then
  bootstrap_run sudo apt-get update
  bootstrap_run sudo apt-get install --yes ca-certificates curl git openssh-client python3
fi

if [[ "$BOOTSTRAP_DRY_RUN" == true || ! -x /usr/local/bin/uv ]]; then
  if [[ "$BOOTSTRAP_DRY_RUN" != true ]]; then
    bootstrap_require_command curl
    bootstrap_require_command sudo
  fi
  bootstrap_run sh -c \
    'curl -LsSf https://astral.sh/uv/0.11.32/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh'
fi

export PATH="/usr/local/bin:$PATH"
bootstrap_prepare_managed_node
