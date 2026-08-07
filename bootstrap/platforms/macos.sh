#!/usr/bin/env bash

if [[ "$BOOTSTRAP_DRY_RUN" != true ]]; then
  bootstrap_require_command brew
fi

if [[ "$BOOTSTRAP_DRY_RUN" == true || ! -x "$(command -v uv 2>/dev/null || true)" ]]; then
  bootstrap_run brew install uv
fi

bootstrap_prepare_controller
