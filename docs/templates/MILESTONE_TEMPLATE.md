# M<ID> Milestone: <Name>

Use this template when starting a new milestone.

## Required Files

Create:

- `docs/M<ID>/00-entry-gate.md`
- `docs/M<ID>/MILESTONE_LEDGER.md`
- one phase file per independently reviewable work slice

Create when closing the milestone:

- `docs/M<ID>/MILESTONE_CLOSEOUT.md`

Reference:

- `docs/ACTIVE_CONTEXT.md`
- `docs/DOC_ROUTING.md`
- `docs/QUALITY_GATES.md`
- `docs/agent/MILESTONE_PLANNING.md`
- `docs/templates/PHASE_TEMPLATE.md`
- `docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md`

## Entry Gate Requirements

The entry gate must include:

- milestone objective;
- accepted inputs;
- product constraints and non-goals;
- phase sequence;
- file boundary;
- module ownership;
- public contract;
- test and smoke expectations;
- approval gates;
- completion gate.

## Milestone Granularity Gate

Before implementation starts, the milestone must be decomposed into reviewable
phases.

Each phase must have:

- one observable result;
- one primary ownership boundary;
- one public contract or clear no-contract reason;
- bounded allowed files;
- explicit read-only and forbidden files;
- focused tests;
- runtime smoke or a clear non-applicability reason;
- non-goals;
- stop conditions.

Planning is blocked when a phase is too broad to assign exclusive file
ownership, test independently, or review without reading unrelated history.

Use `docs/agent/MILESTONE_PLANNING.md` for the decomposition checklist.

## Phase Decomposition Matrix

Every milestone entry gate must include this matrix.

| Phase | Objective | Owner | Contract | Allowed Files | Read-Only Files | Forbidden Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<files>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

## Auto-Advance Policy

Auto-advance is opt-in. A project may auto-advance from one accepted phase to
the next only when:

- the next phase is already inside the entry-gate scope;
- the ledger is current;
- verification evidence does not contradict the ledger;
- no approval gate, blocker, or review stop is required.

## Milestone Closeout

Close the milestone by writing `docs/M<ID>/MILESTONE_CLOSEOUT.md` after the
ledger is current.

Closure order:

1. Accept or explicitly supersede required phases.
2. Update `MILESTONE_LEDGER.md`.
3. Write or update `MILESTONE_CLOSEOUT.md`.
4. Mark the milestone closed or accepted.

The closeout is a compact historical outcome index. It records what shipped,
what changed, key decisions, verification summary, known gaps, follow-up
milestones, and links to detailed evidence.

Do not add the closeout to default startup context. Read it only when
`docs/DOC_ROUTING.md` says historical milestone context is needed.
