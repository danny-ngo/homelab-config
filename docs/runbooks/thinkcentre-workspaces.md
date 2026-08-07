# ThinkCentre workspace durability

The ThinkCentre is an always-on remote development server, but it must remain
rebuildable. T3 Code runs directly on the host and project repositories live
under `/home/<execution-user>/src`. GitHub is the durable source of truth for
project source, not the ThinkCentre filesystem or a Docker volume.

## Working policy

- Every active project must be a Git repository with an expected GitHub remote.
- Work on a project branch and push at each meaningful checkpoint, before
  switching machines, before maintenance or reboot, and at the end of the work
  session. While a project is active, do not leave the only copy of a day's
  work on the ThinkCentre.
- Before destructive experiments, create and push a checkpoint branch even if
  it is not ready to merge. Use draft pull requests for reviewable work in
  progress.
- Never have an agent automatically commit or push an unknown working tree.
  The operator must review the diff, generated files, repository, branch, and
  remote first.
- Secrets, credentials, `.env` files, caches, build products, databases, and
  large generated artifacts do not belong in Git. Ignore them explicitly and
  give any irreplaceable non-source data a separate backup destination.
- Docker volumes are runtime state, not source control. Repositories should be
  bind-mounted or cloned under the workspace, while stateful container data
  uses separately named and backed-up paths.

## Start and end a session

Inspect identity, branch, upstream, worktree, and remote before changing code:

```sh
git status --short --branch
git remote -v
git branch -vv
git fetch --prune
```

At a checkpoint, review exactly what will leave the machine:

```sh
git diff --check
git diff
git diff --cached
git status --short
```

Run the project's relevant tests, create an intentional commit, and push the
current branch:

```sh
git push --set-upstream origin HEAD
git status --short --branch
```

The final status should be clean and show the local branch aligned with its
upstream. If work cannot be committed safely, copy it to the selected encrypted
backup or another trusted machine before ending the session. A stash stored
only on the ThinkCentre does not satisfy the durability requirement.

## Periodic audit

Review all immediate child repositories without modifying them:

```sh
find ~/src -mindepth 1 -maxdepth 1 -type d -print0 |
  while IFS= read -r -d '' repo; do
    git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue
    printf '\n%s\n' "$repo"
    git -C "$repo" status --short --branch
    git -C "$repo" remote -v
  done
```

Investigate any repository with no GitHub remote, uncommitted changes older than
the current work session, a branch without an upstream, or commits that have not
been pushed. This audit is intentionally read-only; remediation remains a
reviewed operator action.

## Rebuild acceptance

A clean ThinkCentre rebuild is successful when the execution-node Ansible
profile restores the host tooling, T3 Code starts through Tailscale, every
active project can be recloned from GitHub, and no required project source
depends on the old disk.
