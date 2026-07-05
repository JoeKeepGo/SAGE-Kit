# M<ID> Milestone Ledger: <Name>

## Objective

## Current State

## Phase Status

| Phase | Status | Owner | Change Ref | Evidence | Next Action |
|---|---|---|---|---|---|
| `00-entry-gate` | `accepted` | `planning` | `<commit, PR, changelist, or n/a>` | `<evidence>` | `<next action>` |

Allowed statuses:

- `planned`
- `in_progress`
- `validating`
- `accepted`
- `blocked`
- `handoff`
- `superseded`

Acceptance invariant:

- `accepted` requires every blocking gate for that phase to be `PASS` or
  explicitly `WAIVED` by the project owner.
- `DONE_WITH_CONCERNS`, failed commands, unresolved blocking gaps, or skipped
  blocking gates cannot be marked `accepted`.

## Decisions

## Decomposition Notes

| Phase | Objective | Owner | Contract | Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|
| `<phase>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

## Gate Status

| Phase | Gate | Status | Evidence | Blocking | Owner | Notes |
|---|---|---|---|---|---|---|
| `<phase>` | `<gate>` | `PASS | FAIL | BLOCKED | WAIVED | N/A` | `<evidence>` | `<yes/no>` | `<owner>` | `<notes>` |

## Wave Status

Use this table only when Wave Execution is used.

| Phase | Wave Plan | Lanes | Conflicts | Controller Verification |
|---|---|---|---|---|
| `<phase>` | `<yes/no>` | `<lanes>` | `<conflicts>` | `<evidence>` |

## Agent Lanes

## Verification Evidence

## Approval Gates

## Blockers

## Context Notes For Resume
