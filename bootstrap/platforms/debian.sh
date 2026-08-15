#!/usr/bin/env bash

# System Python is retained for Ansible module execution. uv itself is
# installed system-wide, while uv-managed Python and its global pin belong to
# the administrator account running this initial bootstrap.

bootstrap_debian_has_lid_switch() {
  local name_file name

  [[ -d /proc/acpi/button/lid ]] && return 0

  for name_file in /sys/class/input/event*/device/name /sys/class/input/input*/name; do
    [[ -r "$name_file" ]] || continue
    IFS= read -r name <"$name_file" || continue
    [[ "$name" == "Lid Switch" ]] && return 0
  done

  return 1
}

bootstrap_prepare_lid_policy() {
  local policy_source="$BOOTSTRAP_ROOT/ansible/roles/infra_host/templates/logind-lid.conf.j2"
  local policy_destination="/etc/systemd/logind.conf.d/60-homelab-lid.conf"

  if [[ "$BOOTSTRAP_DRY_RUN" != true ]] && ! bootstrap_debian_has_lid_switch; then
    bootstrap_log "No lid switch detected; leaving logind lid policy unchanged."
    return
  fi

  [[ -f "$policy_source" ]] || bootstrap_die "missing lid policy: $policy_source"
  bootstrap_log "Installing the persistent lid-close ignore policy."
  bootstrap_run sudo install --directory --mode 0755 /etc/systemd/logind.conf.d
  bootstrap_run sudo install --mode 0644 "$policy_source" "$policy_destination"

  # systemd-logind supports a SIGHUP configuration reload. `systemctl reload`
  # activates the policy without terminating the login service or its sessions.
  if [[ "$BOOTSTRAP_DRY_RUN" == true ]] || systemctl is-active --quiet systemd-logind.service; then
    bootstrap_run sudo systemctl reload systemd-logind.service
    bootstrap_log "Lid-close ignore policy is active; the lid can now be closed."
  else
    bootstrap_log "Lid policy is persistent and will activate when systemd-logind starts."
  fi
}

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
bootstrap_prepare_lid_policy
