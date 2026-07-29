#!/usr/bin/env bash

bootstrap_absolute_path() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$BOOTSTRAP_ROOT" "$path"
  fi
}

bootstrap_run() {
  if [[ "$BOOTSTRAP_DRY_RUN" == true ]]; then
    printf '[bootstrap] Would run:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

bootstrap_require_command() {
  command -v "$1" >/dev/null 2>&1 || bootstrap_die "missing required command: $1"
}

bootstrap_uv_tool_bin_dir() {
  if [[ "$BOOTSTRAP_DRY_RUN" == true ]]; then
    printf '%s\n' "${UV_TOOL_BIN_DIR:-${XDG_BIN_HOME:-$HOME/.local/bin}}"
  else
    uv tool dir --bin
  fi
}

bootstrap_prepare_managed_node() {
  if [[ "$BOOTSTRAP_DRY_RUN" != true ]]; then
    bootstrap_require_command uv

    if [[ "$(uname -m)" == "armv6l" ]]; then
      bootstrap_die "uv-managed Python 3.14 is not published for ARMv6; this host cannot satisfy the managed-node bootstrap contract"
    fi
  fi

  bootstrap_run uv python install --managed-python 3.14
  bootstrap_run uv python pin --global 3.14
}

bootstrap_prepare_controller() {
  local ansible_version=""
  local recreate_venv=false
  local tool_bin_dir

  if [[ "$BOOTSTRAP_DRY_RUN" != true ]]; then
    bootstrap_require_command uv
    bootstrap_require_command git
    bootstrap_require_command ssh
  fi

  bootstrap_run uv python install --managed-python 3.14

  tool_bin_dir="$(bootstrap_uv_tool_bin_dir)"
  BOOTSTRAP_ANSIBLE_PLAYBOOK="$tool_bin_dir/ansible-playbook"
  BOOTSTRAP_ANSIBLE_GALAXY="$tool_bin_dir/ansible-galaxy"
  export PATH="$tool_bin_dir:$PATH"

  if [[ "$BOOTSTRAP_DRY_RUN" != true && -x "$BOOTSTRAP_ANSIBLE_PLAYBOOK" ]]; then
    ansible_version="$("$BOOTSTRAP_ANSIBLE_PLAYBOOK" --version 2>/dev/null || true)"
  fi

  if [[ "$BOOTSTRAP_DRY_RUN" == true ]] ||
    [[ ! -x "$BOOTSTRAP_ANSIBLE_PLAYBOOK" ]] ||
    [[ "$ansible_version" != *"core 2.20.7"* ]]; then
    bootstrap_run uv tool install \
      --managed-python \
      --python 3.14 \
      --force \
      "ansible-core==2.20.7"
  fi

  if [[ "$BOOTSTRAP_DRY_RUN" != true && -x "$BOOTSTRAP_ROOT/.venv/bin/python" ]] && \
    ! "$BOOTSTRAP_ROOT/.venv/bin/python" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 14))'; then
    recreate_venv=true
  fi

  if [[ "$BOOTSTRAP_DRY_RUN" == true || ! -x "$BOOTSTRAP_ROOT/.venv/bin/python" || "$recreate_venv" == true ]]; then
    if [[ "$BOOTSTRAP_DRY_RUN" != true && -e "$BOOTSTRAP_ROOT/.venv" ]]; then
      if [[ "$recreate_venv" == true ]]; then
        bootstrap_run uv venv --clear --managed-python --python 3.14 "$BOOTSTRAP_ROOT/.venv"
      else
        bootstrap_die "$BOOTSTRAP_ROOT/.venv exists but is not a usable virtual environment"
      fi
    else
      bootstrap_run uv venv --managed-python --python 3.14 "$BOOTSTRAP_ROOT/.venv"
    fi
  fi

  bootstrap_run uv sync \
    --frozen \
    --managed-python \
    --python 3.14 \
    --project "$BOOTSTRAP_ROOT"

  bootstrap_run env "ANSIBLE_CONFIG=$BOOTSTRAP_ROOT/ansible/ansible.cfg" \
    "$BOOTSTRAP_ANSIBLE_GALAXY" collection install \
    -r "$BOOTSTRAP_ROOT/ansible/requirements.yml" \
    -p "$BOOTSTRAP_ROOT/.ansible/collections"
}

bootstrap_initialize_inventory() {
  local destination
  destination="$(dirname "$BOOTSTRAP_INVENTORY")"
  [[ "$BOOTSTRAP_INVENTORY" == */hosts.yml ]] || bootstrap_die "automatic inventory initialization requires a hosts.yml path"
  [[ ! -e "$destination" ]] || bootstrap_die "inventory file is missing from existing directory: $destination"
  bootstrap_run cp -R "$BOOTSTRAP_ROOT/ansible/inventories/example" "$destination"
}

bootstrap_run_playbook() {
  local playbook="$1"
  local default_limit="$2"
  local selected_limit="${BOOTSTRAP_LIMIT:-$default_limit}"

  [[ -n "${BOOTSTRAP_ANSIBLE_PLAYBOOK:-}" ]] ||
    bootstrap_die "Ansible controller tooling is unavailable; run this profile from the macOS workstation"
  [[ -n "$selected_limit" ]] || bootstrap_die "the selected profile requires --limit"

  local -a command=(
    "$BOOTSTRAP_ANSIBLE_PLAYBOOK"
    -i "$BOOTSTRAP_INVENTORY"
    "$BOOTSTRAP_ROOT/$playbook"
    --limit "$selected_limit"
  )

  if [[ "$BOOTSTRAP_CHECK_MODE" == true ]]; then
    command+=(--check)
  fi
  set +u
  command+=("${BOOTSTRAP_ANSIBLE_ARGS[@]}")
  set -u

  bootstrap_log "Playbook: $playbook (limit: $selected_limit)"
  if [[ "$BOOTSTRAP_DRY_RUN" == true ]]; then
    bootstrap_run env "ANSIBLE_CONFIG=$BOOTSTRAP_ROOT/ansible/ansible.cfg" "${command[@]}"
  else
    ANSIBLE_CONFIG="$BOOTSTRAP_ROOT/ansible/ansible.cfg" "${command[@]}"
  fi
}
