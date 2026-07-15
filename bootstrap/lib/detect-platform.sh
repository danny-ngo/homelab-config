#!/usr/bin/env bash

bootstrap_validate_name() {
  local value="$1"
  local label="$2"
  [[ "$value" =~ ^[a-z0-9-]+$ ]] || bootstrap_die "invalid $label: $value"
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
