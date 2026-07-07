# M<ID> Milestone Ledger: <Name>

## Objective

## Primary Capability

Name the capability from `docs/CAPABILITY_MAP.md`, or record `N/A` with a
reason when no capability map is used.

## Current State

## Closeout Status

- Closeout file: `docs/M<ID>/MILESTONE_CLOSEOUT.md`
- Closeout status: `not_started | drafted | finalized | blocked | superseded`
- Closeout change ref: `<commit, PR, changelist, or n/a>`
- Closeout notes: `<short note or n/a>`

The ledger is the detailed milestone evidence record. The closeout is the
compressed historical outcome index written after the ledger is current.

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

| Phase | Objective | Primary Capability | Owner | Contract | Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|
| `<phase>` | `<objective>` | `<capability or n/a>` | `<owner>` | `<contract or none>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

## Gate Status

| Phase | Gate | Status | Evidence | Blocking | Owner | Notes |
|---|---|---|---|---|---|---|
| `<phase>` | `<gate>` | `PASS | FAIL | BLOCKED | WAIVED | N/A` | `<evidence>` | `<yes/no>` | `<owner>` | `<notes>` |

## Wave Status

Use this table only when Wave Execution is used.

| Phase | Wave Plan | Lanes | Conflicts | Controller Verification |
|---|---|---|---|---|
| `<phase>` | `<yes/no>` | `<lanes>` | `<conflicts>` | `<evidence>` |

## Capability Routing Status

Use this table when specialist skills, plugins, connectors, or tools are
available or expected.

| Task | Capability | Used | Evidence | Fallback |
|---|---|---|---|---|
| `<task>` | `<skill/plugin/connector/tool>` | `<yes/no/unavailable>` | `<evidence>` | `<fallback>` |

## Worktree Status

Use this table when Worktree Isolation is used.

| Worktree | Branch | Scope | Owner | Status | Integration | Cleanup |
|---|---|---|---|---|---|---|
| `<path>` | `<branch>` | `<phase/lane/review>` | `<owner>` | `<status>` | `<evidence>` | `<recommendation/status>` |

## Task Dispatch Status

Use this table when Task Dispatch Profile is used.

| Task | Status | Required Levels | Validator | Resource Locks | Evidence | Next Action |
|---|---|---|---|---|---|---|
| `<task>` | `<status>` | `<L0-L4>` | `<pass/fail/not run>` | `<locks or none>` | `<evidence.yaml>` | `<next action>` |

## Session Orchestration Status

Use this table only when Session Orchestration is used.

| Controller | Packet | Status | Evidence | Next Action |
|---|---|---|---|---|
| `Project Manager` | `<execution/structural/final decision packet>` | `<status>` | `<evidence>` | `<next action>` |
| `Coder` | `<milestone result packet>` | `<status>` | `<evidence>` | `<next action>` |
| `Final Review` | `<review verdict packet>` | `<status>` | `<evidence>` | `<next action>` |

## Agent Lanes

## Verification Evidence

## Approval Gates

## Blockers

## Context Notes For Resume

## Closeout Inputs

Use these notes only while preparing `MILESTONE_CLOSEOUT.md`.

- What shipped:
- Key decisions:
- Verification summary:
- Known gaps:
- Follow-up milestones:
