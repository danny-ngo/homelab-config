---
layout: default
title: "0003: Python, Ansible, and uv bootstrap ownership"
---

# 0003: Python, Ansible, and uv bootstrap ownership

- Status: accepted
- Date: 2026-07-28

## Decision

Use the MacBook as the Ansible controller. Use the curl-delivered `install.sh`
as the fresh-machine entry point and keep `./bootstrap.sh` as the local
operation entry point within repository source. Prepare a fresh macOS
workstation in this order:

1. have `install.sh` install Homebrew when absent, ensure Git is available, and
   create or safely reuse the persistent checkout;
2. have the checkout bootstrap install uv through Homebrew;
3. install a uv-managed Python 3.14;
4. install `ansible-core==2.20.7` into uv's user-global tool environment; and
5. create the locked repository environment and install the pinned Ansible
   collections next to this checkout.

The operational `ansible-playbook` and `ansible-galaxy` commands come only from
the uv tool environment, not Homebrew, macOS's system Python, or the repository
virtual environment. The Brewfile therefore does not contain `ansible`.
Bootstrap invokes their absolute paths from `uv tool dir --bin`, so the first
run does not depend on that directory already being in the interactive shell's
`PATH`.

Retain a separate checkout-local `.venv` for development, lint, syntax checks,
and unit tests. uv creates it with a managed Python 3.14 and synchronizes it
from the committed `pyproject.toml` and `uv.lock`. `.python-version` records the
requested interpreter line. `requirements-dev.txt` is retired so dependency
metadata has one source of truth.

The project environment also contains `ansible-core` because Ansible lint,
syntax validation, filters, and repository tests import or execute Ansible
code. This does not make `.venv/bin/ansible-playbook` the operational
controller CLI; `make check`, `make apply`, and bootstrap use the uv tool
command.

For the local Mac workstation connection, set
`ansible_python_interpreter` to `ansible_playbook_python`. Local Ansible modules
therefore use the uv tool's Python 3.14 instead of the macOS `/usr/bin/python3`
3.9 installation.

Every managed Linux node runs the remote `install.sh` locally before the
MacBook targets it. The installer downloads a temporary repository archive and
hands off to `./bootstrap.sh --prepare-only`. That initial bootstrap:

1. installs the distribution's system Python and SSH prerequisites;
2. installs a machine-global uv executable;
3. runs `uv python install --managed-python 3.14` as the administrator account;
4. runs `uv python pin --global 3.14` for that account; and
5. on Debian laptops, detects the lid switch, installs the shared persistent
   lid-close ignore policy, and reloads `systemd-logind`; and
6. stops without installing Ansible or applying a profile.

On Debian, the pinned uv standalone installer writes to `/usr/local/bin`
because Debian 13 does not provide uv as a stable distribution package. On
Arch, Pacman installs the `uv` package into `/usr/bin`. uv-managed Python and
the global pin remain per-user even though the uv executable is machine-global.
The global pin is uv's fallback when no nearer `.python-version` exists; it
does not replace the operating system's Python.

Managed Linux nodes retain their distribution-owned system Python for Ansible
module execution:

- Debian 13's default `python3` package is Python 3.13. A standard image may
  already contain it, but minimal images are not assumed to do so; the Debian
  bootstrap explicitly installs `python3`.
- Arch's minimal `base` package does not include Python. Arch is rolling
  release and its `python` package was 3.14.6 when this decision was recorded;
  bootstrap explicitly installs the unversioned `python` package rather than
  relying on an image default.

Inventory explicitly selects `/usr/bin/python3` for the `linux_nodes` group.
The MacBook's uv-tool Python runs Ansible and controller-side plugins; after
SSH transport, `/usr/bin/python3` runs the transferred module payload. The
uv-managed 3.14 installation on Linux is ready for user workloads and future
explicit uv-based tasks, but is not Ansible's implicit remote interpreter.

Do not install Ansible through Homebrew or a Linux package manager. Linux
bootstrap does not install Ansible at all.

The current x86_64, aarch64, and ARMv7 managed inventory can install
uv-managed Python 3.14. ARMv6 can run the uv executable but has no published
uv-managed CPython 3.14 build, so bootstrap rejects `armv6l` explicitly. The Pi
1 boards remain outside `linux_nodes`; their recorded `pi1_edge_nodes`
exception uses Raspberry Pi OS `/usr/bin/python3` only for the two
purpose-specific roles and does not invoke bootstrap or uv.

## Dependency and upgrade policy

- Pin direct Python tools in `pyproject.toml` and commit the complete
  cross-platform resolution in `uv.lock`.
- Use `uv sync --frozen` during bootstrap and CI so those paths cannot silently
  rewrite the lock.
- Pin the operational uv tool package as `ansible-core==2.20.7`.
- Pin Debian's standalone uv installer URL; let Homebrew and Pacman own uv
  upgrades on their respective platforms.
- Pin Ansible collections in `ansible/requirements.yml`.
- Upgrade Python, Ansible, linters, or collections through a reviewed change
  that regenerates the lock and passes `make ci`.
- Treat Arch's system Python patch/minor level as distribution state; Ansible
  compatibility is guarded by the pinned `ansible-core` support range rather
  than by freezing Arch packages.

## Consequences

- macOS's system Python is not modified and cannot contaminate Ansible's
  control dependencies.
- Operational Ansible remains globally available to the controller account
  while retaining uv's per-tool isolation.
- The repository has a reproducible Python 3.14 validation environment.
- Linux users receive a consistent uv-managed Python 3.14 default without
  changing the distribution interpreter used by Ansible.
- Linux target system Python remains patchable by the distribution package
  manager.
- Managed nodes cannot accidentally become controllers through bootstrap.
- Homebrew and the uv tool environment are recovery prerequisites for the
  controller, while the repository and lockfile remain their source of truth.

## References

- [Homebrew installation](https://docs.brew.sh/Installation)
- [uv tool installation](https://docs.astral.sh/uv/guides/tools/)
- [uv Python management](https://docs.astral.sh/uv/concepts/python-versions/)
- [uv installer options](https://docs.astral.sh/uv/reference/installer/)
- [Detailed bootstrap flow](../bootstrap-python-flow.md)
- [Ansible support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html)
- [Debian 13 `python3`](https://packages.debian.org/stable/python/python3)
- [Arch `base`](https://archlinux.org/packages/core/any/base/)
- [Arch `python`](https://archlinux.org/packages/core/x86_64/python/)
