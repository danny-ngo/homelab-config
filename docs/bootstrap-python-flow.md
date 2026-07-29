# Bootstrap Python, Ansible, and uv flow

This repository has one controller and two deliberately different bootstrap
paths:

```text
Fresh MacBook
  curl install.sh | bash
    → Homebrew + Git prerequisite
      → persistent checkout
        → Homebrew uv
          → uv-managed Python 3.14
            ├─→ uv tool environment → ansible-core 2.20.7
            └─→ repository .venv → locked lint/test dependencies
                  ↓
            ansible-playbook over SSH
                  ↓
Fresh Linux node
  curl install.sh | bash
    → temporary source archive
      → apt/pacman → system Python + SSH prerequisites + global uv executable
        → per-user uv-managed Python 3.14
          → per-user global uv pin 3.14
            → stop; wait for the MacBook controller
                ↓
          /usr/bin/python3 executes transferred Ansible modules
```

## Fresh MacBook controller

Run the remote `install.sh` with the curl command in the README. It creates or
reuses the checkout and then invokes `./bootstrap.sh`; macOS defaults to the
`workstation` profile.

1. `install.sh` downloads and runs the official Homebrew installer when
   `brew` is missing. It installs Homebrew Git only when no Git command is
   available afterward, then creates or safely reuses the persistent checkout.
2. The checkout's macOS bootstrap requires Homebrew and installs the `uv`
   executable. macOS's system Python is not used.
3. `uv python install --managed-python 3.14` installs the latest available
   CPython 3.14 patch release in uv's per-user data directory.
4. `uv tool install --managed-python --python 3.14 --force
   ansible-core==2.20.7` creates an isolated, per-user tool environment. Its
   `ansible-playbook` and `ansible-galaxy` executables are the operational
   controller commands.
5. uv creates or recreates the checkout's `.venv` with Python 3.14 and runs
   `uv sync --frozen`. This environment is for lint, syntax checks, filters,
   and tests; it is not the operational Ansible installation.
6. The uv-tool `ansible-galaxy` installs the collection versions pinned in
   `ansible/requirements.yml` under `.ansible/collections`.
7. If production inventory does not exist, bootstrap copies the safe example
   and stops. Otherwise, it applies the selected profile.

Ansible is intentionally absent from the Brewfile. Homebrew owns `uv`; `uv
tool` exclusively owns operational Ansible.

## Fresh Linux managed node

Run the remote `install.sh` locally on every Debian-family or Arch-family node
before targeting it from the MacBook. The installer downloads a temporary
source archive and invokes `./bootstrap.sh --prepare-only`; it removes the
archive on exit.

1. The distribution package manager installs the remote-execution
   prerequisites, including system Python:
   - Debian installs `ca-certificates`, `curl`, `git`, `openssh-client`, and
     `python3`.
   - Arch installs `uv`, `git`, `openssh`, and `python`.
2. Debian installs the pinned standalone `uv` executable into
   `/usr/local/bin`; Arch's `uv` executable is installed into `/usr/bin` by
   Pacman. These are machine-global executables.
3. The unprivileged administrator account runs `uv python install
   --managed-python 3.14`. The interpreter itself remains per-user under uv's
   data directory.
4. That same account runs `uv python pin --global 3.14`. The pin is stored as
   `.python-version` in the user's uv configuration directory and becomes uv's
   fallback only when a checkout has no nearer pin.
5. Bootstrap stops. It does not install Ansible, create a repository virtual
   environment, install collections, or run a playbook on Linux.

The global pin does not replace `/usr/bin/python3`, modify the OS package
database, or make uv-managed Python Ansible's remote interpreter.

## What runs when the MacBook applies a play

1. The MacBook's uv-tool Python runs `ansible-playbook` and all controller-side
   plugins.
2. Ansible connects to the selected Linux node over SSH.
3. Ansible transfers a module payload to the node.
4. Inventory explicitly selects `/usr/bin/python3`, so the node's
   distribution Python executes that payload.
5. Tasks that deliberately invoke `uv` use the global uv executable; uv
   resolves Python 3.14 from a repository pin first and the user's global pin
   second.

This keeps the bootstrap acyclic: system Python makes a fresh Linux node
Ansible-manageable, while uv-managed Python is ready for user workloads without
being a prerequisite for Ansible's own remote module runtime.

## The four meanings of “global” and “local”

| Component | Scope | Owner | Purpose |
| --- | --- | --- | --- |
| Linux `/usr/local/bin/uv` or `/usr/bin/uv` | Machine-global executable | Initial bootstrap / OS package manager | Makes `uv` available to users and future Ansible tasks |
| uv global Python pin | One user account | `uv python pin --global` | Default uv Python request when no project pin exists |
| Mac uv-tool Ansible | One controller account, globally callable | `uv tool` | Operational Ansible CLI in an isolated environment |
| Repository `.venv` | One checkout | `uv sync` | Locked development and CI environment |

## System Python answers

- Debian 13's `python3` package currently resolves to Python 3.13. A standard
  installation may contain it, but a minimal image is not guaranteed to, so
  bootstrap installs it explicitly.
- Arch's minimal `base` package does not include Python. The rolling `python`
  package is currently Python 3.14, so bootstrap installs it explicitly rather
  than treating it as part of the base image.

Distribution versions can change independently of this repository. The stable
contract is `/usr/bin/python3` for Ansible module execution, not a frozen patch
version.

## Dependency locking and upgrades

- `.python-version` pins this checkout to the Python 3.14 line.
- `pyproject.toml` declares direct development dependencies.
- `uv.lock` contains the complete resolved development dependency graph.
- `ansible-core==2.20.7` is also pinned independently in the `uv tool`
  installation command because that environment is outside `uv.lock`.
- `ansible/requirements.yml` pins collection versions.
- Debian's standalone uv installer URL is pinned to `0.11.32`; Homebrew and
  Pacman own uv upgrades on macOS and Arch.

After changing a Python dependency, run `uv lock`, review `uv.lock`, then run
`uv sync --frozen` and `make ci`.

## Architecture boundary

uv and uv-managed CPython 3.14 builds are available for the inventory's
x86_64, aarch64, and ARMv7 nodes. uv publishes an ARMv6 executable, but the
managed CPython source used by uv does not publish an ARMv6 Python 3.14 build.
Bootstrap therefore rejects `armv6l` with an explicit error. The Pi 1 boards
remain outside managed inventory; bringing one into service requires a
documented Python exception or replacement hardware.
