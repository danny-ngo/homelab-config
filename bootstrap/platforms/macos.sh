#!/usr/bin/env bash

if [[ "$BOOTSTRAP_DRY_RUN" != true ]]; then
  bootstrap_require_command brew
  if ! command -v uv >/dev/null 2>&1; then
    bootstrap_run brew install uv
  fi
fi
bootstrap_prepare_ansible
