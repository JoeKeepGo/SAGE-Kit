# Worktree Isolation

Worktree Isolation is an optional isolation policy for milestones, phases, or
lanes that need stronger file, dependency, runtime, or agent isolation.

It is not the default for all development. Use it when isolation lowers merge
risk or enables safe parallel work. Avoid it when work is small, serial, or
touches the same shared files.

## Authority Model

| Role | Owns | Must Not Do |
|---|---|---|
| Project Manager Controller | Whether worktree isolation is allowed, max count, naming, branch base, cleanup policy, submit authority. | Delegate unlimited worktree creation without bounds. |
| Coder Controller | Decide which approved phases or lanes get worktrees, create the worktree map, integrate results. | Create worktrees outside the execution packet or bypass shared-file gates. |
| Phase or Lane Worker | Work inside the assigned worktree and file boundary. | Push, merge, delete worktrees, or change isolation policy. |
| Final Review Controller | Verify worktree use, integration evidence, stale worktree risks, and submit readiness. | Commit, push, merge, or delete worktrees while acting as Final Review. |
| Submit Controller or Project Manager | Final commit, push, merge, and cleanup decision. | Submit unverified or unowned worktree output. |

## Isolation Modes

| Mode | Use For |
|---|---|
| `NONE` | Small, serial, or tightly shared work. |
| `MILESTONE_WORKTREE` | One isolated workspace for a whole milestone. |
| `PHASE_WORKTREE` | High-risk or parallel phases with clear boundaries. |
| `LANE_WORKTREE` | Independent lane work with disjoint writable files. |
| `REVIEW_WORKTREE` | Independent final review or validation without touching the coder workspace. |

## Project Manager Authorization

Worktree isolation may be used only when the Project Manager execution packet
allows it.

The packet must define:

- allowed isolation mode;
- maximum worktree count;
- branch and worktree naming convention;
- base branch or base commit;
- allowed phases or lanes;
- shared files that remain serial;
- runtime ownership;
- integration owner;
- submit authority;
- cleanup policy;
- forbidden scenarios.

## Coder Decision Rule

Coder Controller may decide where to create worktrees only inside the Project
Manager authorization.

Coder may create a phase or lane worktree when:

- writable files are disjoint;
- public contracts are frozen or the phase owns the migration;
- runtime ownership is exclusive or not required;
- dependency, lockfile, schema, migration, and generated-file conflicts are
  absent or assigned to a serial owner;
- the worker has a bounded prompt, expected evidence, and stop conditions;
- integration owner and final verification path are known.

Coder must keep work serial or return `STOP_FOR_PM` when:

- multiple phases need the same shared file;
- a migration, lockfile, generated artifact, state table, router, registry, or
  runtime environment is shared;
- approval gates are closed;
- branch base or naming is undefined;
- worktree count would exceed the authorized maximum;
- cleanup or submit ownership is unclear.

## Worktree Map

Every worktree run must report a map:

| Worktree | Branch | Scope | Owner | Allowed Files | Runtime | Status | Integration |
|---|---|---|---|---|---|---|---|
| `<path>` | `<branch>` | `<phase/lane/review>` | `<owner>` | `<files>` | `<runtime or n/a>` | `<status>` | `<owner/action>` |

## Final Review Rules

Final Review verifies:

- worktrees were authorized by the execution packet;
- each worktree stayed inside its file boundary;
- integration evidence exists;
- serial gates stayed serial;
- runtime and dependency ownership did not conflict;
- stale or abandoned worktrees are identified;
- submit and cleanup recommendations are explicit.

Final Review may recommend commit, push, merge, or cleanup. It must not execute
those actions while acting as Final Review.

If the same session is later used for submit or cleanup, Project Manager must
first record the Final Review verdict, then issue a separate Submit Controller
authorization.

## Cleanup Gate

A worktree may be cleaned only when:

- it is not the active working directory;
- no process or runtime depends on it;
- its changes are merged, pushed, superseded, or explicitly abandoned;
- no uncommitted changes need preservation;
- evidence is recorded in the ledger, closeout, completion report, or handoff;
- Project Manager or Submit Controller approves cleanup.

If any condition is unclear, return a cleanup recommendation instead of deleting
the worktree.

## Serial Gates

These remain serial even when worktrees are used:

- approval gates;
- branch base changes;
- public contract freeze;
- shared file integration;
- schema, migration, lockfile, and generated artifact changes;
- real runtime smoke unless exclusive runtime ownership is granted;
- final verification;
- ledger, closeout, active context, and routing maintenance;
- commit, push, merge, release, publish, and cleanup.
