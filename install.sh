#!/usr/bin/env bash
set -Eeuo pipefail

repository="${HOMELAB_CONFIG_REPOSITORY:-https://github.com/danny-ngo/homelab-config.git}"
checkout_parent="${HOMELAB_CONFIG_PARENT:-$HOME/src}"
archive_ref="${HOMELAB_CONFIG_REF:-main}"
archive_url="${HOMELAB_CONFIG_ARCHIVE_URL:-https://github.com/danny-ngo/homelab-config/archive/refs/heads/$archive_ref.tar.gz}"
installer_tmp_dir=""

installer_log() {
  printf '[installer] %s\n' "$*"
}

installer_die() {
  printf '[installer] error: %s\n' "$*" >&2
  exit 2
}

installer_require_command() {
  command -v "$1" >/dev/null 2>&1 || installer_die "missing required command: $1"
}

installer_download() {
  local url="$1"
  local destination="$2"

  installer_require_command curl
  curl \
    --proto '=https' \
    --tlsv1.2 \
    --fail \
    --silent \
    --show-error \
    --location \
    --retry 3 \
    --output "$destination" \
    "$url"
}

installer_remove_tmp_dir() {
  if [[ -n "$installer_tmp_dir" && -d "$installer_tmp_dir" ]]; then
    rm -rf -- "$installer_tmp_dir" || true
  fi
  installer_tmp_dir=""
}

installer_cleanup() {
  local status=$?
  trap - EXIT INT TERM
  installer_remove_tmp_dir
  exit "$status"
}

trap installer_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

installer_expand_home() {
  case "$1" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s/%s\n' "$HOME" "${1#\~/}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

installer_repository_name() {
  local value="${1%/}"
  value="${value%.git}"
  value="${value##*/}"
  value="${value##*:}"
  [[ -n "$value" && "$value" != "." && "$value" != ".." ]] ||
    installer_die "cannot determine repository name from: $1"
  [[ "$value" =~ ^[A-Za-z0-9._-]+$ ]] ||
    installer_die "unsafe repository name derived from: $1"
  printf '%s\n' "$value"
}

installer_normalize_repository() {
  local value="${1%/}"
  value="${value%.git}"
  value="${value#https://}"
  value="${value#http://}"
  value="${value#ssh://git@}"
  value="${value#git@}"
  if [[ "$value" == *:* ]]; then
    value="${value%%:*}/${value#*:}"
  fi
  printf '%s\n' "$value"
}

installer_homebrew_bin() {
  if command -v brew >/dev/null 2>&1; then
    command -v brew
  elif [[ -x /opt/homebrew/bin/brew ]]; then
    printf '%s\n' /opt/homebrew/bin/brew
  elif [[ -x /usr/local/bin/brew ]]; then
    printf '%s\n' /usr/local/bin/brew
  else
    return 1
  fi
}

installer_activate_homebrew() {
  local brew_bin
  brew_bin="$(installer_homebrew_bin)" ||
    installer_die "Homebrew installation completed but brew was not found"
  eval "$("$brew_bin" shellenv)"
}

installer_install_homebrew() {
  command -v brew >/dev/null 2>&1 && return

  installer_require_command mktemp
  installer_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/homelab-homebrew.XXXXXXXX")"
  local homebrew_installer="$installer_tmp_dir/install.sh"

  installer_log "Installing Homebrew"
  installer_download \
    "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh" \
    "$homebrew_installer"

  if ( : </dev/tty ) 2>/dev/null; then
    /bin/bash "$homebrew_installer" </dev/tty
  else
    NONINTERACTIVE=1 /bin/bash "$homebrew_installer"
  fi

  installer_remove_tmp_dir
}

installer_ensure_checkout() {
  local parent="$1"
  shift
  local repository_name checkout origin
  repository_name="$(installer_repository_name "$repository")"
  checkout="$parent/$repository_name"

  mkdir -p -- "$parent"

  if [[ ! -e "$checkout" ]]; then
    installer_log "Cloning $repository into $parent"
    (
      cd "$parent"
      git clone -- "$repository"
    )
  else
    [[ -d "$checkout" ]] ||
      installer_die "checkout path exists and is not a directory: $checkout"
    [[ "$(git -C "$checkout" rev-parse --is-inside-work-tree 2>/dev/null || true)" == "true" ]] ||
      installer_die "checkout path exists but is not a Git repository: $checkout"
    origin="$(git -C "$checkout" remote get-url origin 2>/dev/null || true)"
    [[ -n "$origin" ]] ||
      installer_die "existing checkout has no origin remote: $checkout"
    [[ "$(installer_normalize_repository "$origin")" == "$(installer_normalize_repository "$repository")" ]] ||
      installer_die "existing checkout origin does not match $repository: $checkout"
    installer_log "Using existing checkout without pulling or replacing local changes: $checkout"
  fi

  [[ -f "$checkout/bootstrap.sh" ]] ||
    installer_die "checkout does not contain bootstrap.sh: $checkout"

  installer_log "Checkout ready: $checkout"
  installer_log "Running the macOS controller bootstrap"
  (
    cd "$checkout"
    /bin/bash ./bootstrap.sh "$@"
  )
}

installer_macos() {
  installer_install_homebrew
  installer_activate_homebrew

  local brew_bin
  brew_bin="$(command -v brew)"
  if ! command -v git >/dev/null 2>&1; then
    installer_log "Installing Git with Homebrew"
    "$brew_bin" install git
  fi
  installer_require_command git

  checkout_parent="$(installer_expand_home "$checkout_parent")"
  [[ "$checkout_parent" == /* ]] ||
    installer_die "HOMELAB_CONFIG_PARENT must be an absolute path or start with ~/: $checkout_parent"
  installer_ensure_checkout "$checkout_parent" "$@"
}

installer_linux() {
  installer_require_command tar
  installer_require_command mktemp

  [[ "$archive_ref" =~ ^[A-Za-z0-9._/-]+$ && "$archive_ref" != *".."* ]] ||
    installer_die "invalid HOMELAB_CONFIG_REF: $archive_ref"

  installer_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/homelab-bootstrap.XXXXXXXX")"
  local archive="$installer_tmp_dir/homelab-config.tar.gz"
  local source_dir="$installer_tmp_dir/source"

  installer_log "Downloading homelab-config at $archive_ref"
  installer_download "$archive_url" "$archive"

  mkdir "$source_dir"
  tar -xzf "$archive" -C "$source_dir" --strip-components=1
  [[ -f "$source_dir/bootstrap.sh" ]] ||
    installer_die "downloaded archive does not contain bootstrap.sh"

  installer_log "Running managed-node preparation"
  (
    cd "$source_dir"
    /bin/bash ./bootstrap.sh --prepare-only "$@"
  )
}

case "$(uname -s)" in
  Darwin) installer_macos "$@" ;;
  Linux) installer_linux "$@" ;;
  *) installer_die "unsupported operating system: $(uname -s)" ;;
esac
