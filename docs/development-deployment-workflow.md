---
layout: default
title: Development and application deployment workflow
---

# Development and application deployment workflow

- Status: proposed operating model
- Last reviewed: 2026-08-12

This plan separates interactive development, continuous integration, host
configuration, and production application delivery. The ThinkCentre execution
node is the disposable development and test machine. The ThinkPad is the
persistent infrastructure and production host: Docker runs stateful platform
services, while K3s runs developed applications. GitHub repositories are the
source of truth and GitHub Actions is the pipeline orchestrator.

The initial delivery model is push-based. An approved GitHub-hosted Actions job
joins the tailnet as a short-lived workload identity and applies a specific
release through a restricted deployment endpoint on the ThinkPad. No
persistent Actions runner or production credential resides on the ThinkCentre,
and no in-cluster GitOps controller continuously reconciles repositories. This
keeps the existing no-GitOps baseline while making builds and deployments
repeatable, auditable, and isolated from the development node.

## Architecture and responsibilities

```text
developer workstation
        |
        | remote development
        v
ThinkCentre execution node ---- feature branch / pull request ----> GitHub
  - source workspaces                                             - Git repos
  - local Docker tests                                            - hosted CI
  - integration tests                                             - GHCR images
                                                                    - releases
                                                                         |
                                                   approved image digest |
                                                                         v
                                                ephemeral GitHub runner
                                                  - GitHub OIDC
                                                  - Tailscale tag
                                                                         |
                                                    restricted SSH only |
                                                                         v
ThinkPad <-------------------------------- forced deployment command ----+
  - Docker: databases, monitoring, automations
  - K3s server: production applications
  - persistent data and backups
```

| Concern | Owner | Normal change path |
| --- | --- | --- |
| Application source and tests | Application repository | Feature branch, pull request, review, merge |
| Application image | GitHub Actions and GHCR | Build once from a reviewed commit; publish an immutable digest |
| K3s application definition | Application repository | Versioned Helm chart or Kubernetes manifests deployed by the application pipeline |
| Production promotion | Private deployment repository and GitHub-hosted runner | Manual digest selection, ephemeral Tailscale identity, and restricted ThinkPad command |
| Docker infrastructure stacks | `homelab-config` | Reviewed Compose definition, validation, backup gate, protected deployment |
| ThinkPad OS, Docker engine, and K3s lifecycle | `homelab-config` and Ansible | CI validates; the MacBook controller performs the reviewed Ansible apply |
| Production runtime state | ThinkPad | Named data paths and protected backups; never Git |
| Secrets | Ansible Vault, protected GitHub deployment secrets, or the selected runtime secret store | Encrypted or injected at deployment; never committed or built into an image |
| Deployment evidence | GitHub Actions plus runtime annotations | Commit, image digest, workflow run, environment, time, and result |

The MacBook remains the Ansible controller. A deployment pipeline may update an
application or an approved Docker Compose stack, but it must not silently take
over host provisioning, K3s upgrades, firewall policy, storage preparation, or
recovery operations.

## Repository model

Use one GitHub repository per independently released application. A typical
application repository should contain:

```text
app/
  src/
  tests/
  Dockerfile
  compose.test.yml             # optional execution-node integration stack
  deploy/
    chart/                     # Helm chart, or k3s/ for plain manifests
  .github/workflows/
    ci.yml
    release.yml
```

The application repository owns the code, build recipe, tests, runtime
contract, and workload definition. Its release publishes the image and either
an immutable OCI Helm artifact or another versioned deployment bundle. A
release Git tag identifies the source; artifact digests identify the exact
inputs. Do not deploy `latest` or another mutable tag. A human-friendly semantic
version or commit-SHA tag may be published as an alias, but production must
resolve and record immutable digests.

Keep production orchestration in a small private repository such as
`homelab-deploy`. This public infrastructure repository and any public
application repositories can build immutable artifacts, but must not have a
persistent self-hosted runner attached. The deployment repository contains only
reviewed workflow code, application allowlists, non-secret release metadata,
and the production workflow:

```text
homelab-deploy/
  applications.yml              # allowed image/chart repos and namespaces
  deploy/
    chart-values/               # non-secret production values
  .github/workflows/
    deploy-production.yml
```

Promotion is deliberately pull-by-digest rather than an automatic cross-
repository deployment. The operator supplies a digest already published by a
successful application release. The deployment workflow verifies its source
repository and release evidence before contacting the homelab.

This repository owns shared host and platform configuration. Add Docker stacks
under a consistent path such as:

```text
services/docker/
  databases/
  monitoring/
  automations/
```

Each stack should contain a Compose file, an example environment file with no
secrets, health checks, resource limits, backup and restore instructions, and a
short ownership note. The deployed definitions live under
`/opt/infra/containers`; persistent state lives separately under
`/srv/infra/data`. Runtime credentials should use protected files or another
selected secret mechanism under `/srv/infra/secrets`, not a committed `.env`
file.

## Environments

There are three meaningful environments, even if only production is long-lived:

| Environment | Location | Purpose | Lifetime |
| --- | --- | --- | --- |
| Development | ThinkCentre workspace | Fast edit, unit test, debugger, and local dependency loop | Per session |
| Test | ThinkCentre Docker/temporary processes | Integration, migration, and release-candidate smoke tests | Ephemeral and reproducible |
| Production | ThinkPad K3s plus Docker infrastructure | Stable applications and durable platform services | Persistent |

Development and test data is disposable or synthetic. It must not reuse the
production database, credentials, volumes, or kubeconfig. If a production-like
dataset is needed, create a sanitized fixture and document how it was derived.

## Day-to-day development workflow

1. Clone or fetch the application on the ThinkCentre under the managed source
   workspace. Confirm the expected GitHub remote and create a short-lived branch.
2. Run dependencies locally or through `compose.test.yml`. Pin versions so the
   test environment can be recreated after the execution node is rebuilt.
3. Make the change and run formatting, linting, unit tests, integration tests,
   and a local image build. Database changes must include a migration and a
   tested compatibility or rollback plan.
4. Commit and push meaningful checkpoints. Open a pull request; do not leave the
   only copy of active work on the execution node.
5. GitHub Actions repeats the portable checks on a clean GitHub-hosted runner.
   Hardware- or LAN-specific tests may run on a separately labelled runner in
   an isolated ThinkCentre VM, but untrusted pull-request code must never
   receive deployment credentials.
6. Merge only after required checks and review pass. Keep `main` releasable and
   use Git tags or GitHub releases for versions worth promoting.

See [ThinkCentre workspace durability](runbooks/thinkcentre-workspaces.md) for
the start-of-session, checkpoint, and rebuild rules.

## Application pipeline

Split validation, artifact publication, and production deployment into distinct
jobs or workflows. This prevents a retry from rebuilding different bytes and
allows the same artifact to be promoted or rolled back.

### 1. Pull-request validation

Run on a GitHub-hosted runner with read-only repository permissions and no
production secrets:

- formatting, linting, unit tests, and dependency validation;
- integration tests using disposable containers;
- Dockerfile and Kubernetes/Helm validation;
- an image build without production deployment; and
- architecture checks for the nodes on which the application may run.

GitHub-hosted CI is an independent clean-room check; it complements the faster
development loop on the ThinkCentre. A self-hosted runner on the ThinkCentre is
optional only for hardware- or LAN-specific trusted tests. If one is required,
isolate it in a dedicated VM, attach it only to an explicitly allowed private
repository, and give it no production identity or network access.

### 2. Build and publish

After a reviewed merge to `main`, or when a release tag is pushed:

1. Check out the exact commit and rerun the required tests.
2. Build the image once and push it to GHCR using the workflow's short-lived
   repository token where possible.
3. Publish a commit-SHA or release tag and capture the registry digest.
4. Package the matching chart or workload definition as a versioned artifact
   and record its digest or immutable release revision.
5. Generate provenance, an SBOM, and a vulnerability report when the chosen
   toolchain supports them. A critical finding blocks promotion.
6. Store the source commit, image and deployment artifact digests, supported
   architectures, and test result in the workflow summary or GitHub release.

Images that may run on both the ThinkPad and Pi workers need a tested
`linux/amd64` and `linux/arm64` manifest. An amd64-only image must declare a
node selector or affinity so K3s cannot schedule it onto an ARM worker.

### 3. Promote to production

Run production promotion from the private deployment repository with an
explicit `workflow_dispatch` input containing a previously built image digest.
The manual dispatch is the initial human gate; add a protected `production`
environment when the repository plan and reviewer model provide an independent
approval. The production job must not rebuild the image.

The job runs on a fresh GitHub-hosted runner. It requests a GitHub OIDC token,
exchanges that workload identity through Tailscale, and joins the tailnet as an
ephemeral node tagged `tag:github-deploy`. Tailnet policy permits this tag to
reach only the ThinkPad's OpenSSH endpoint. It must not reach databases, the
K3s API, Docker, monitoring interfaces, other LAN nodes, or the ThinkCentre.

Use ordinary OpenSSH over the Tailscale path; the existing Tailscale SSH
exclusion remains unchanged. Store a dedicated SSH private key as a protected
deployment secret. Its matching ThinkPad `authorized_keys` entry must force a
root-owned dispatcher and disable interactive shells, PTY allocation, agent
forwarding, port forwarding, and arbitrary commands.

```text
restrict,command="/usr/local/libexec/homelab-deploy" ssh-ed25519 DEPLOY_PUBLIC_KEY
```

The dispatcher file is owned and writable only by root, but runs as the
unprivileged deployment account with only its scoped K3s identity.

The forced command accepts only a small typed request such as an application
identifier, an allowed GHCR digest, and the GitHub run identifier. It validates
every value against an allowlist, resolves the matching chart or workload from
an allowlisted immutable release artifact, and only then invokes Helm or
`kubectl`. It does not accept raw manifests, archives, scripts, or shell syntax
over SSH. The local deployment user has a namespace-scoped Kubernetes identity;
it never uses the K3s administrator kubeconfig, node token, Ansible Vault
password, Docker socket, or database credentials.

```text
GitHub-hosted runner
  └─ GitHub OIDC → ephemeral Tailscale tag
       └─ restricted OpenSSH → ThinkPad forced command
            └─ namespace-scoped Helm/kubectl → local K3s API
```

An illustrative workflow skeleton is:

```yaml
name: Deploy production

on:
  workflow_dispatch:
    inputs:
      application:
        type: choice
        options: [example-app]
        required: true
      image_digest:
        description: Full GHCR sha256 digest from a successful release
        required: true

permissions:
  contents: read
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    concurrency:
      group: production-${{ inputs.application }}
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - uses: tailscale/github-action@780049a30b6ff5c378a9e7b389d15ece7a204888 # v4.1.3
        with:
          oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
          audience: ${{ secrets.TS_AUDIENCE }}
          tags: tag:github-deploy
          ping: ${{ vars.THINKPAD_TAILSCALE_NAME }}
      - name: Promote verified digest
        env:
          APPLICATION: ${{ inputs.application }}
          IMAGE_DIGEST: ${{ inputs.image_digest }}
          SSH_PRIVATE_KEY: ${{ secrets.PRODUCTION_DEPLOY_SSH_KEY }}
        run: ./scripts/promote-production
```

The checked-in `promote-production` client must validate inputs, load the SSH
key without printing it, verify the pinned ThinkPad host key, and send only the
restricted request. Do not interpolate untrusted inputs into a shell command.
The server-side dispatcher repeats all validation; client validation is not a
security boundary.

The deployment job should:

1. Verify that the requested digest was produced by the expected repository and
   successful release workflow.
2. Render the Helm chart or manifests with the immutable digest and validate the
   result before contacting the cluster.
3. Record the current release and confirm that a known-good older digest is
   available.
4. Create the ephemeral tailnet path and invoke only the forced ThinkPad
   deployment command. The server applies or upgrades the workload with an
   atomic timeout where the deployment tool supports it.
5. Wait for rollout completion, then run an internal readiness check and a
   user-visible smoke test.
6. Annotate the workload with the source revision and workflow run, and create a
   GitHub deployment record containing the digest and result.
7. Roll back to the recorded known-good release if rollout or smoke validation
   fails. Preserve logs and events before failed pods are removed.

Only one production deployment per application should run at a time. Use an
Actions concurrency group rather than allowing two releases to race.

The selected K3s node pulls the image directly from GHCR; the image does not
pass through the GitHub runner or ThinkCentre. A private image uses a namespace-
scoped K3s image-pull credential.

### 4. Verify after deployment

A successful Kubernetes rollout is necessary but not sufficient. Verify the
real application protocol, its dependency connection, and an external or
independent health signal. Monitoring on the ThinkPad can inspect application
behavior, while an off-host heartbeat is needed to detect loss of the entire
ThinkPad, its power, or its network path.

## Database changes

Applications in K3s consume databases provided by Docker on the ThinkPad over a
private, explicitly allowed network path. Database ports must not be publicly
exposed. Use a distinct database role and credential per application.

Treat schema changes as stateful operations:

- prefer backward-compatible expand/migrate/contract changes;
- back up and verify restore inputs before a destructive migration;
- run migrations as a bounded release job, not from every application replica;
- deploy code that can tolerate both the old and expanded schema before
  removing old columns or constraints; and
- do not assume an application rollback can reverse a committed data migration.

A destructive migration requires a separate approval and maintenance plan. Its
rollback is normally restore or forward repair, not merely redeploying an older
container.

## Docker infrastructure pipeline

Databases, monitoring, and automation services change less often than
applications and need a stricter path.

1. A pull request to `homelab-config` validates YAML, renders Compose
   configuration with non-secret example values, checks image pins, and runs the
   repository's existing test suite.
2. The operator reviews storage paths, port exposure, resource limits, secrets,
   and backup impact. Stateful version upgrades require release-note review and
   a tested restore point.
3. After merge, a protected manual workflow may use the same ephemeral
   GitHub/Tailscale path to invoke a separate forced Docker-stack command. That
   command copies only the reviewed definition to
   `/opt/infra/containers/<stack>` and runs `docker compose pull` followed by
   `docker compose up -d`.
4. The workflow waits for container health and verifies the actual service
   protocol. On failure it captures status and logs, then follows the stack's
   documented rollback; it must not delete or recreate persistent data
   automatically.

Start with manual deployment from the MacBook controller until the restricted
SSH command, workload identity, tailnet policy, secret files, and backup gate
are implemented.
Automating `docker compose` is an optimization, not a prerequisite for safely
running the first stack.

## Security boundaries

- Keep pull-request, build, and production jobs on fresh GitHub-hosted runners.
  Do not attach a persistent self-hosted runner to this public repository.
- Keep the ThinkPad a deployment target, never an Actions runner. Workflow code
  must not execute beside K3s server state, Docker data, backups, or databases.
- Keep the ThinkCentre free of production credentials. Its development account
  has root-equivalent Docker access, so another Unix account on the same host is
  not an adequate secret boundary. Put any optional trusted-test runner in a
  dedicated VM with no shared folders or production network access.
- Pin third-party Actions to reviewed commit SHAs and grant each workflow the
  smallest `permissions` block it needs.
- Protect workflow files and deployment definitions with review. Changes to a
  trusted workflow are equivalent to changes to the credentials it can use.
- Use separate identities for Tailscale workload enrollment, restricted SSH,
  GHCR pulls, per-application K3s deployment, and Docker-stack deployment. Do
  not reuse the Ansible, K3s node-token, or cluster-administrator credentials.
- Permit `tag:github-deploy` to reach only the forced OpenSSH endpoint. Do not
  expose a runner service, SSH, or the K3s API to the public Internet.
- Never print kubeconfigs, tokens, Compose secret files, database URLs, or
  rendered Kubernetes Secrets in Actions logs or artifacts.
- Revoke the Tailscale federated identity and restricted SSH key independently.
  Ephemeral tailnet membership does not remove the need to rotate the SSH key.

## Rollback and recovery

For a stateless application rollback, redeploy the last known-good image digest
with its matching chart or manifests, wait for rollout, and repeat smoke tests.
Do not use a mutable tag as the rollback reference.

For a Docker infrastructure rollback, restore the previous Compose definition
and pinned image only after checking the service's data-format compatibility.
Never delete a volume as a generic rollback step. Restore state from the
verified backup when an upgrade changed it incompatibly.

K3s server recovery is independent of application delivery. Restore the
ThinkPad's K3s state first, then reconcile application releases from their
recorded commits and digests. Follow [K3s recovery](runbooks/k3s-recovery.md).

## Adoption plan and acceptance gates

### Phase 1: conventions and CI

- Choose one pilot application and add the standard repository layout.
- Protect `main`, require pull-request checks, and make CI run without production
  credentials.
- Build and publish an immutable GHCR image with a recorded digest.

Gate: a fresh clone on the ThinkCentre and a clean GitHub runner produce passing
tests; the published artifact maps unambiguously to one Git commit.

### Phase 2: protected K3s delivery

- Create the private deployment repository and manual digest workflow.
- Configure GitHub-to-Tailscale workload identity for
  `tag:github-deploy` and allow that tag to reach only ThinkPad OpenSSH.
- Create the forced ThinkPad dispatcher plus one namespace-scoped deployment
  identity for the pilot application.
- Add an approved production workflow, rollout checks, deployment evidence, and
  concurrency control.

Gate: a fresh GitHub-hosted runner joins the tailnet ephemerally, cannot reach
unapproved services, deploys the pilot by digest through the forced command,
and restores the prior release without rebuilding it. Neither primary homelab
computer stores a persistent Actions runner credential.

### Phase 3: state and observability

- Add application health dashboards and an independent heartbeat.
- Implement the chosen encrypted backup destination and perform a clean-location
  restore test for every production database and K3s server state.
- Exercise a backward-compatible database migration and application rollback.

Gate: recovery uses written instructions and verified backups rather than the
original containers or execution-node workspace.

### Phase 4: Docker stack automation

- Standardize Compose stack layout, secret files, image pins, health checks, and
  per-stack runbooks.
- Add a restricted deployment command or identity and a protected manual
  workflow for one non-critical stack.
- Extend automation to stateful stacks only after backup, restore, and
  data-format rollback behavior has been proven.

Gate: a Compose update changes only the selected stack, exposes no secrets in
logs, preserves persistent data, and has a tested operator rollback.

## Decisions to complete before production

The following implementation details remain explicit gates rather than hidden
assumptions:

- the application ingress, internal DNS name, TLS, and authentication model;
- the runtime secret delivery mechanism for K3s applications and Compose stacks;
- the private deployment repository, workflow ownership, and manual or
  independent approval policy;
- the Tailscale federated identity, `tag:github-deploy` ownership, destination
  rule, and revocation procedure;
- the restricted SSH key, pinned ThinkPad host key, forced-command request
  format, dispatcher allowlist, and key rotation procedure;
- the GHCR visibility and K3s image-pull credential model;
- the backup target, retention, encryption, off-host copy, and restore schedule;
- the monitoring destination and alert owner; and
- the initial pilot application's CPU, memory, storage, architecture, and
  availability requirements.

These choices should be added to the relevant repository before its first
production deployment. They do not require changing the overall workflow.

## References

- [GitHub self-hosted runner communication](https://docs.github.com/en/actions/reference/runners/self-hosted-runners#communication)
- [GitHub secure use and self-hosted runner hardening](https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners)
- [GitHub deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [Tailscale GitHub Action and workload identity](https://tailscale.com/docs/integrations/github/github-action)
