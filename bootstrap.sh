#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bootstrap/lib/logging.sh
source "$root/bootstrap/lib/logging.sh"
# shellcheck source=bootstrap/lib/detect-platform.sh
source "$root/bootstrap/lib/detect-platform.sh"
# shellcheck source=bootstrap/lib/requirements.sh
source "$root/bootstrap/lib/requirements.sh"

profile=""
platform=""
limit=""
inventory="ansible/inventories/production/hosts.yml"
prepare_only=false
check_mode=false
dry_run=false
declare -a ansible_args=()

usage() {
  cat <<'EOF'
Usage: ./bootstrap.sh [options] [-- ansible-playbook-arguments]

Prepare a fresh machine or apply a machine profile from the macOS controller.

Options:
  --profile PROFILE    workstation, infra, execution-node, pihole, k3s-worker,
                       pi1-sentinel, or pi1-probe
  --limit TARGET       inventory host/group limit (profile-specific by default)
  --inventory PATH     inventory path (default: production inventory)
  --platform PLATFORM  override OS detection: macos, debian, or arch
  --check              run the selected playbook in Ansible check mode
  --prepare-only       prepare tooling without applying a profile
  --dry-run            print commands without running Ansible or changing the machine
  -h, --help           show this help

macOS is the Ansible controller and defaults to the workstation profile.
Debian and Arch are managed nodes: run --prepare-only on each fresh Linux host,
then run the desired profile from the macOS workstation.

--dry-run previews the command only. Use --check (without --dry-run) to run
Ansible against hosts in check mode; the two options are intentionally distinct.
EOF
}

while (($#)); do
  case "$1" in
    --profile)
      (($# >= 2)) || bootstrap_die "--profile requires a value"
      profile="$2"
      shift 2
      ;;
    --limit)
      (($# >= 2)) || bootstrap_die "--limit requires a value"
      limit="$2"
      shift 2
      ;;
    --inventory)
      (($# >= 2)) || bootstrap_die "--inventory requires a value"
      inventory="$2"
      shift 2
      ;;
    --platform)
      (($# >= 2)) || bootstrap_die "--platform requires a value"
      platform="$2"
      shift 2
      ;;
    --check)
      check_mode=true
      shift
      ;;
    --prepare-only)
      prepare_only=true
      shift
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      ansible_args=("$@")
      break
      ;;
    *)
      bootstrap_die "unknown option: $1"
      ;;
  esac
done

BOOTSTRAP_ROOT="$root"
BOOTSTRAP_DRY_RUN="$dry_run"
BOOTSTRAP_CHECK_MODE="$check_mode"
BOOTSTRAP_INVENTORY="$(bootstrap_absolute_path "$inventory")"
BOOTSTRAP_LIMIT="$limit"
# Bash 3.2 treats an empty declared array as unset under nounset. Temporarily
# relaxing nounset keeps the public script compatible with the system Bash on
# macOS while preserving exact argument boundaries when values are present.
set +u
BOOTSTRAP_ANSIBLE_ARGS=("${ansible_args[@]}")
set -u
export BOOTSTRAP_ROOT BOOTSTRAP_DRY_RUN BOOTSTRAP_CHECK_MODE BOOTSTRAP_INVENTORY BOOTSTRAP_LIMIT

if [[ -z "$platform" ]]; then
  platform="$(bootstrap_detect_platform)"
fi
bootstrap_validate_name "$platform" "platform"
platform_script="$root/bootstrap/platforms/$platform.sh"
[[ -f "$platform_script" ]] || bootstrap_die "unsupported platform: $platform"

if [[ -z "$profile" && "$prepare_only" != true ]]; then
  profile="$(bootstrap_default_profile "$platform")"
fi

profile_script=""
if [[ -n "$profile" ]]; then
  bootstrap_validate_name "$profile" "profile"
  profile_script="$root/bootstrap/profiles/$profile.sh"
  [[ -f "$profile_script" ]] || bootstrap_die "unsupported profile: $profile"
fi

bootstrap_log "Platform: $platform"
if [[ -n "$profile" ]]; then
  bootstrap_log "Profile: $profile"
fi

# Platform modules prepare only the machine running this command. The macOS
# workstation prepares controller tooling; Linux modules prepare managed-node
# prerequisites and never install or invoke Ansible.
# shellcheck source=/dev/null
source "$platform_script"

if [[ "$prepare_only" == true ]]; then
  if [[ "$platform" == "macos" ]]; then
    bootstrap_log "Workstation controller tooling is ready; no profile was applied."
  else
    bootstrap_log "Managed-node prerequisites are ready; apply its profile from the macOS workstation."
  fi
  exit 0
fi

[[ "$platform" == "macos" ]] ||
  bootstrap_die "Ansible profiles must be applied from the macOS workstation"

if [[ "$BOOTSTRAP_DRY_RUN" != true && ! -f "$BOOTSTRAP_INVENTORY" ]]; then
  bootstrap_initialize_inventory
  bootstrap_die "created $BOOTSTRAP_INVENTORY; replace the example values, create the encrypted vault, then rerun bootstrap"
fi

# shellcheck source=/dev/null
source "$profile_script"
