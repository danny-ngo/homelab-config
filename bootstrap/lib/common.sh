#!/usr/bin/env bash

bootstrap_log() {
  printf '[bootstrap] %s\n' "$*"
}

bootstrap_die() {
  printf '[bootstrap] error: %s\n' "$*" >&2
  exit 2
}

bootstrap_validate_name() {
  local value="$1"
  local label="$2"
  [[ "$value" =~ ^[a-z0-9-]+$ ]] || bootstrap_die "invalid $label: $value"
}

bootstrap_absolute_path() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$BOOTSTRAP_ROOT" "$path"
  fi
}

bootstrap_detect_platform() {
  local kernel
  kernel="$(uname -s)"
  case "$kernel" in
    Darwin)
      printf 'macos\n'
      ;;
    Linux)
      [[ -r /etc/os-release ]] || bootstrap_die "cannot detect Linux distribution: /etc/os-release is missing"
      # shellcheck source=/etc/os-release
      source /etc/os-release
      case "${ID:-}" in
        debian|ubuntu|raspbian)
          printf 'debian\n'
          ;;
        arch|cachyos|manjaro)
          printf 'arch\n'
          ;;
        *)
          case " ${ID_LIKE:-} " in
            *" debian "*) printf 'debian\n' ;;
            *" arch "*) printf 'arch\n' ;;
            *) bootstrap_die "unsupported Linux distribution: ${ID:-unknown}" ;;
          esac
          ;;
      esac
      ;;
    *)
      bootstrap_die "unsupported operating system: $kernel"
      ;;
  esac
}

bootstrap_default_profile() {
  case "$1" in
    macos) printf 'workstation\n' ;;
    arch) printf 'execution-node\n' ;;
    debian) bootstrap_die "Debian hosts require --profile (infra, k3s-worker, or pihole)" ;;
    *) bootstrap_die "no default profile for platform: $1" ;;
  esac
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

bootstrap_prepare_ansible() {
  if [[ "$BOOTSTRAP_DRY_RUN" != true ]]; then
    bootstrap_require_command uv
    bootstrap_require_command git
    bootstrap_require_command ssh
  fi

  if [[ "$BOOTSTRAP_DRY_RUN" == true || ! -x "$BOOTSTRAP_ROOT/.venv/bin/python" ]]; then
    if [[ "$BOOTSTRAP_DRY_RUN" != true && -e "$BOOTSTRAP_ROOT/.venv" ]]; then
      bootstrap_die "$BOOTSTRAP_ROOT/.venv exists but is not a usable virtual environment"
    fi
    bootstrap_run uv venv --python 3.12 "$BOOTSTRAP_ROOT/.venv"
  fi
  bootstrap_run uv pip install \
    --python "$BOOTSTRAP_ROOT/.venv/bin/python" \
    -r "$BOOTSTRAP_ROOT/requirements-dev.txt"
  bootstrap_run env "ANSIBLE_CONFIG=$BOOTSTRAP_ROOT/ansible/ansible.cfg" \
    "$BOOTSTRAP_ROOT/.venv/bin/ansible-galaxy" collection install \
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

  [[ -n "$selected_limit" ]] || bootstrap_die "the selected profile requires --limit"

  local -a command=(
    "$BOOTSTRAP_ROOT/.venv/bin/ansible-playbook"
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
