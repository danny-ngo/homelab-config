---
layout: default
title: "Handoff: make the dotfiles repository configuration-only"
---

# Handoff: make the dotfiles repository configuration-only

## Assignment

Update `https://github.com/danny-ngo/dotfiles` so it contains and documents
user configuration only. Remove its bootstrap and software-installation
scripts. Do not replace them with another installer, task runner, package
manifest, or setup framework.

Work in the dotfiles repository, not in `homelab-config`. The homelab repository
is context for the ownership boundary only.

## Baseline inspected

This handoff was prepared on 2026-07-15 after inspecting dotfiles `main` at
commit `0e6bfc094f8c6867fa71684e5aa87b517feeede0` (`add Displaylink to installed
apps`). Reinspect the latest branch and preserve any newer user changes before
editing.

At the inspected revision, the relevant layout is:

```text
dotfiles/
├── git/.gitconfig
├── install.sh
├── raycast/Raycast 2025-02-19 09.41.31.rayconfig
├── README.md
├── scripts/.install_linux.sh
├── scripts/.install_mac.sh
├── starship/.config/starship.toml
├── wallpapers/*.jpg
├── wezterm/.wezterm.lua
└── zsh/.zshrc
```

`install.sh` selects an operating-system script. The macOS script currently
installs Homebrew packages and applications, runs GNU Stow, and changes Dock
defaults. The Linux script is only a placeholder. All three are bootstrap
concerns and should be removed.

## Ownership boundary

After this change, the dotfiles repository owns:

- shell, prompt, Git, terminal, and other user-level configuration;
- configuration exports such as the Raycast export;
- configuration-associated assets already tracked in the repository; and
- a short README explaining what the repository contains and how an external
  manager may consume its Stow-compatible directories.

It does not own:

- Homebrew or another package manager;
- formula, cask, OS-package, or application installation;
- language/runtime installation;
- operating-system defaults or machine provisioning;
- platform detection;
- cloning itself;
- orchestration of GNU Stow; or
- bootstrapping a new workstation.

Those machine-level concerns belong to external provisioning. In the current
environment, `homelab-config` is intended to own reviewed packages and invoke
the dotfiles repository explicitly. The dotfiles repository should assume its
consumer has already installed Git, GNU Stow, and any programs needed by the
tracked configs.

## Required changes

1. Delete these files:

   ```text
   install.sh
   scripts/.install_linux.sh
   scripts/.install_mac.sh
   ```

2. Remove `scripts/` if it is empty afterward. If newer work has added
   non-bootstrap scripts, inspect them individually and keep them unless they
   install software, provision a machine, or orchestrate config deployment.

3. Rewrite the README so it reflects the configuration-only contract:

   - describe the repository as personal user configuration;
   - state that software and machine provisioning happen elsewhere;
   - state that directories such as `git`, `starship`, `wezterm`, and `zsh`
     use a GNU Stow-compatible layout where applicable;
   - explain that the calling environment is responsible for selecting and
     applying packages;
   - optionally show a direct, non-installing Stow example for a user who
     already has the prerequisites; and
   - retain useful descriptions of tracked tools/configs, but do not present
     them as a package list that this repository promises to install.

4. Remove all README instructions that bootstrap a machine, including:

   - the Homebrew remote installer command;
   - `brew install` commands;
   - clone-as-installation steps; and
   - `sh install.sh` instructions.

5. Search the entire repository for stale references to the deleted scripts
   and to repository-owned installation. Fix documentation references without
   changing the configs themselves.

## Preserve unless separately authorized

Do not use this cleanup as a reason to rewrite or delete existing dotfiles.
In particular, preserve `git/`, `starship/`, `zsh/`, `wezterm/`, the Raycast
export, and the wallpapers. Some are deprecated, non-Stow data, or supporting
assets, but deciding whether to retire them is separate from removing bootstrap
installation. Also avoid opportunistic formatting or cross-platform changes to
the configuration payloads.

Do not edit `homelab-config` as part of this assignment. If external
provisioning is missing a package or does not yet apply a desired Stow package,
report that as follow-up work rather than putting installation logic back into
dotfiles.

## Suggested README shape

Keep the README compact. A useful structure is:

1. repository purpose and configuration-only boundary;
2. tracked configuration packages;
3. prerequisite statement;
4. optional Stow usage example; and
5. deprecated configs or future configuration work, if still relevant.

An acceptable usage example would only link already-provisioned configs, such
as:

```sh
stow --restow --target="$HOME" git starship zsh
```

Do not wrap that command in a repository script. Do not use `stow --adopt`,
because it can overwrite the repository with pre-existing target files.

## Validation

Run checks equivalent to the following from the dotfiles repository root:

```sh
test ! -e install.sh
test ! -e scripts/.install_mac.sh
test ! -e scripts/.install_linux.sh
rg -n --hidden -g '!.git/**' \
  'install\.sh|\.install_(mac|linux)\.sh|brew install|Homebrew/install|curl.+\|.+sh' .
git diff --check
git status --short
```

The `rg` command should return no stale bootstrap instructions. Review any
match rather than suppressing it blindly.

If GNU Stow is available, validate the active Stow packages against a temporary
home so the real home directory is untouched:

```sh
tmp_home="$(mktemp -d)"
stow --dir="$PWD" --target="$tmp_home" git starship zsh
find "$tmp_home" -type l -print
rm -rf "$tmp_home"
```

Do not include `raycast` or `wallpapers` in that smoke test; they are stored
data/assets rather than home-directory packages. Treat `wezterm` according to
the README's existing deprecated status, but preserve it in this assignment.

## Acceptance criteria

- The three inspected bootstrap scripts are gone, and `scripts/` is gone if it
  has no other legitimate content.
- No tracked file installs packages or applications, detects a platform,
  changes OS defaults, or orchestrates workstation setup.
- No documentation instructs users to run a repository installer.
- The README clearly says provisioning is external and this repository owns
  user configuration only.
- Existing configuration and assets are preserved byte-for-byte unless a
  change is strictly needed to remove a stale installer reference.
- Stow-layout validation succeeds for the active config packages, or any
  pre-existing layout problem is reported without broadening the task.
- The final handoff back includes the changed/deleted file list, validation
  results, and any external-provisioning gaps discovered. Do not push or merge
  unless the operator separately asks for that action.
