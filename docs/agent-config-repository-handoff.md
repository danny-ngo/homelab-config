---
layout: default
title: "Handoff: build the agent-config repository"
---

# Handoff: build the agent-config repository

## Assignment and context

Create a dedicated repository, provisionally named `agent-config`, for personal
agent instructions, prompts, and skills. It must reproduce the preferred setup
across machines and agent harnesses, with different skill selections for
different machine/node profiles.

The user also wants to import skills from multiple GitHub repositories, track
upstream updates while preserving local changes, and author skills based on two
or more upstream skills.

This document captures the discussion as an implementation brief. The separate
repository and patterns below are the recommended starting design; the exact
repository location, supported harnesses, and initial skill sources have not
been selected. Do not invent existing repositories, upstream sources, or user
preferences. Start with a local, reviewable implementation and document any
remaining deployment choices.

Work in the new agent-config repository. This file is stored in `homelab-config`
only as a handoff; do not implement the agent system in the homelab repository
or alter unrelated in-progress changes there.

## Ownership boundaries

- **agent-config:** canonical instructions and skills, profile selection,
  harness adapters, upstream provenance, and application of its own content.
- **homelab-config/external provisioning:** install Git, runtimes, harnesses,
  and other prerequisites; obtain a pinned agent-config checkout; choose the
  target user's profile and invoke its apply command.
- **dotfiles:** personal shell, terminal, and other user configuration. Keep it
  configuration-only, consistent with the existing
  [dotfiles handoff](dotfiles-config-only-handoff.md).
- **project repositories:** project-specific instructions and skills.

An earlier discussion suggested dotfiles could bootstrap agent-config. The
existing configuration-only dotfiles contract makes external provisioning the
appropriate integration point instead. Do not add machine bootstrap logic to
dotfiles.

Keep credentials, harness session state, caches, and authentication outside
agent-config. Skills may declare prerequisites, but applying a profile should
not implicitly install packages or enable external services.

## Suggested repository layout

```text
agent-config/
├── README.md
├── instructions/             # composable personal instruction fragments
├── prompts/                  # reusable prompts, when distinct from skills
├── skills/                   # curated skills that may be installed
│   └── <skill>/
│       ├── SKILL.md
│       └── references/
├── upstream/                 # pristine, committed source snapshots
│   └── <source-id>/<skill>/
├── harnesses/                # path mappings and configuration adapters
├── profiles/                 # explicit content and harness selection
├── sources.yaml              # sources and curated-skill ancestry
├── sources.lock              # exact resolved revisions/integrity information
├── bin/
│   ├── apply
│   ├── validate
│   └── update-upstream
└── tests/
```

Use a small implementation with a documented runtime and minimal dependencies.
Avoid a general plugin/package framework for the first version. The manifest
format and command names here are proposals, not native harness schemas.

## Profiles and harness adapters

Profiles should compose a base profile with explicit additions and removals.
For example:

```yaml
# Proposed schema; finalize and document before implementation.
extends: [base]
harnesses: [codex]
instructions: [homelab]
skills: [infrastructure, code-review]
```

Define deterministic inheritance, list merging, exclusions, and ordering.
Reject cycles, unknown identifiers, duplicate output destinations, and
ambiguous collisions. Machine provisioning selects a named profile; the
agent-config system should not guess capabilities from a hostname. Allow a
small explicit machine override when needed.

Keep common content independent of harness paths. Adapters should specify
discovery locations, instruction filenames, supported formats, and any
necessary rendering. Similar file formats do not guarantee equivalent skill
behavior: tools, triggers, permissions, and relative resource paths need review.

Verify current official documentation and installed versions before implementing
an adapter. As checked during the design discussion, Codex documents user skills
under `~/.agents/skills` and supports symlinked skill directories:
<https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills>.
Recheck rather than assuming that every harness uses the same paths. This
environment also exposes skills through harness-specific/plugin locations.

Implement one verified adapter first. If no harness choice is available, Codex
is a reasonable explicitly documented initial assumption; do not claim support
for unimplemented adapters.

## Applying a profile

Provide commands equivalent to:

```sh
bin/validate
bin/apply --profile workstation --target-home /tmp/example-home --dry-run
bin/apply --profile workstation --target-home /tmp/example-home
```

Required behavior:

- Link individual selected skill directories rather than the entire catalog.
- Render combined instruction fragments into harness-specific output files in
  a stable, documented order. Preserve working resource paths for skills.
- Support copying where symlinks are unsuitable; keep the initial scope small.
- Maintain an ownership/state record outside the source checkout containing
  installed destinations, profile, and applied repository revision.
- Make repeated application idempotent. Profile switching removes stale
  managed outputs while preserving manual/unmanaged content.
- Refuse to overwrite unmanaged files. Do not adopt or delete content merely
  because its name matches a selected skill.
- If a previously managed file or link was manually changed, report a conflict
  instead of overwriting or deleting it. Record enough state to detect this.
- Validate the entire plan before mutation, constrain destinations to the
  selected target, and use atomic file replacement where practical.
- Make dry-run report additions, updates, removals, and conflicts without
  modifying the target or state.

Do not apply to the operator's real home during initial development. Use
temporary target directories. Applying to a machine should be an explicit
operation; cloning or updating the repository must not change its setup.

## Sourcing and provenance

Vendor selected directories from upstream repositories as committed pristine
snapshots. Do not require Git submodules for the first implementation. Keep
curated installable content in `skills/` separate from `upstream/`.

For each source, record:

- stable source identifier and repository URL;
- selected subdirectory and upstream tracking branch/tag, if any;
- exact full commit SHA in the lock file;
- snapshot destination and integrity information where useful;
- license, attribution, and required notices; and
- import/update notes and any required supporting files outside the skill folder.

For each curated skill, record its source identifiers, customization mode
(`direct`, `modified`, or `synthesized`), and relevant source sections/resources.
Assign manifest and lock-file fields a single clear responsibility rather than
duplicating revision values that can drift.

A public repository is not automatically licensed for redistribution. Inspect
the actual license before vendoring, preserve required notices, and flag absent
or incompatible licensing for resolution. Treat upstream instructions/scripts
as content to inspect; do not execute fetched scripts during import.

Upstream snapshots should include the resources needed to understand and use
the imported skill. Validate references and detect dependencies outside the
selected path. Reject unsafe paths and escaping symlinks in imported content.

## Updating a skill with one upstream

Use a three-way merge:

```text
base   = previous pristine upstream snapshot
ours   = current curated/customized skill
theirs = new pristine upstream snapshot
```

Preserve the old snapshot through Git history or an explicit staging area until
the merge is finished. Handle resource additions, removals, renames, and binary
files as well as `SKILL.md`. Do not silently overwrite local modifications or
present unresolved conflict markers as usable content.

Run updates in an isolated staging area or branch. Resolve the requested
upstream ref to an exact SHA, show the old-to-new source diff, and propose the
curated changes. If merging fails, preserve a reviewable conflict report and
leave the installed setup untouched. Update snapshots and lock records together.

A fork with upstream merges remains an option for heavily customized whole
collections, but selected-directory vendoring is the default for this repository.

## Synthesizing a skill from multiple upstreams

Own one coherent skill with its own name, purpose, trigger conditions, and
workflow. Do not concatenate multiple `SKILL.md` files. Reconcile assumptions,
tool requirements, approval rules, duplicated steps, and conflicting guidance.

Example: a review skill can own the overall review workflow while drawing a
maintainability checklist from source A and a security checklist from source B.
Keep separable checklists as attributed references when that makes updates easier.

There is usually no meaningful single merge base for the synthesized skill.
On each upstream update:

1. Diff each changed source against its previous pinned snapshot.
2. Use the recorded ancestry to identify affected curated sections/resources.
3. Propose adaptations, with human/agent review of applicability and conflicts.
4. Record adopted changes and intentionally omitted changes with brief reasons.
5. Validate the whole resulting workflow and its references.

The updater may prepare diffs and a review checklist; it must not claim to have
mechanically merged semantic changes from multiple sources. Unchanged source
material should not force unnecessary rewriting of the synthesized skill.

## Reproducibility and rollout

Pin both the agent-config repository revision and third-party source revisions
for servers/CI. Workstations may follow a development branch by explicit choice.
Document required runtimes, harness versions tested, and external prerequisites.

Start with manual upstream update commands. Scheduled update branches/PRs can
be added later. An update report should identify old/new revisions, snapshot
changes, curated changes, unresolved conflicts, omitted changes, and validation.
Do not push, publish, or configure scheduled jobs just to complete the initial
local implementation.

## Implementation sequence

1. Inspect the destination repository and its instructions, preserving existing
   work. Establish the schemas, ownership contract, and initial adapter.
2. Implement profile resolution, validation, dry-run, and safe application.
3. Demonstrate with small clearly labeled original fixtures, not invented
   third-party imports presented as real user skills.
4. Implement pinned import and staged single-source updates with provenance.
5. Add multi-source ancestry and update-review reports.
6. Document external provisioning integration; make homelab changes only as a
   separately scoped follow-up.

## Validation and acceptance criteria

Use temporary homes and small local Git fixture repositories to test meaningful
behavior without network dependence or changing the operator's installed setup.

- A fresh profile apply installs exactly the selected content.
- Reapplying produces no changes; profile switching removes only owned outputs.
- Unmanaged collisions and manually changed managed outputs fail safely.
- Dry-run leaves both target and state unchanged.
- Invalid inheritance, escaping paths, and destination collisions are rejected.
- Rendered instructions have deterministic ordering and usable resource links.
- Imports record exact revisions and preserve applicable attribution/notices.
- A non-conflicting upstream update retains a local tweak while incorporating
  upstream changes; a conflicting update preserves reviewable evidence.
- A multi-source update identifies affected sources and requests synthesis
  review without blindly replacing the curated skill.
- Updating sources does not mutate the installed setup.
- Documentation explains profiles, supported adapters, apply/conflict behavior,
  imports, updates, provenance, and revision pinning.
- Run relevant tests and `git diff --check`; report limitations honestly.

The final agent response should identify the repository location, implemented
commands and adapters, validation results, unresolved choices, and exact steps
for a first real deployment. Repository hosting, initial real skill selection,
and machine deployment remain explicit follow-up choices if not supplied.
