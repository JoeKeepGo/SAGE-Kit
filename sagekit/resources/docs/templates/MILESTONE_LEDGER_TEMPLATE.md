# M<ID> Milestone Ledger: <Name>

## Objective

## Primary Capability

Name the capability from `docs/CAPABILITY_MAP.md`, or record `N/A` with a
reason when no capability map is used.

## Current State

## Closeout Status

- Closeout file: `docs/M<ID>/MILESTONE_CLOSEOUT.md`
- Closeout status: `not_started`, `drafted`, `finalized`, `closed_blocked`,
  `deferred`, `abandoned`, or `superseded`
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
  explicitly `WAIVED` by the named owner.
- `DONE_WITH_CONCERNS`, failed commands, unresolved blocking gaps, or skipped
  blocking gates cannot be marked `accepted`.

## Decisions

## Decomposition Notes

| Phase | Governance Level | Permission Mode | Objective | Primary Capability | Owner | Contract | Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `Light, Standard, or Heavy` | `<mode>` | `<objective>` | `<capability or n/a>` | `<owner>` | `<contract or none>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

## Gate Status

| Phase | Gate | Status | Evidence | Blocking | Finding Owner | Waiver Authority | Decision Or Delegation Ref | Notes |
|---|---|---|---|---|---|---|---|---|
| `<phase>` | `<gate>` | `PASS`, `FAIL`, `BLOCKED`, `WAIVED`, or `N/A` | `<evidence>` | `<yes/no>` | `<owner>` | `<authority or n/a>` | `<explicit decision/delegation ref or n/a>` | `<notes>` |

An ordinary quality-finding waiver needs an explicit decision from the named
Waiver Authority or a documented delegation reference. Finding ownership alone
does not grant waiver authority. A human-only approval gate may be waived only
by its named human authority.

## Wave Status

Use this table only when Wave Execution is used.

| Phase | Wave Plan | Lanes | Conflicts | Controller Verification |
|---|---|---|---|---|
| `<phase>` | `<yes/no>` | `<lanes>` | `<conflicts>` | `<evidence>` |

## Capability Routing Status

Use this table when specialist skills, plugins, connectors, or tools are
available or expected.

| Task | Capability | Adapter Type | Authorization | Used | Evidence | Fallback |
|---|---|---|---|---|---|---|
| `<task>` | `<skill/plugin/connector/tool/CLI/CI/reviewer>` | `<built-in/reference/external>` | `<metadata/read/write/gated>` | `<yes/no/unavailable>` | `<evidence>` | `<fallback>` |

When superpowers is used, record the selected skill name and the SAGE-Kit
boundary it served. A superpowers completion signal is execution evidence, not
milestone acceptance.

When any external planning output is used, record the SAGE-Kit artifact where
it was written or mapped. Do not rely on an untracked external plan as the
source of truth.

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

| Stage | Owner | Record | Status | Evidence | Next Action |
|---|---|---|---|---|---|
| `PM execution issuance` | `Project Manager` | `<execution packet>` | `<issued/held>` | `<evidence>` | `<next action>` |
| `Coder result` | `Coder Controller` | `<milestone result packet>` | `<status>` | `<evidence>` | `<next action>` |
| `Structural gate` | `Project Manager` | `<structural gate record>` | `PASS`, `REPAIR_REQUIRED`, or `BLOCKED` | `<evidence>` | `<next action>` |
| `Final verdict` | `Final Review Controller` | `<review verdict packet>` | `ACCEPTABLE`, `ACCEPTABLE_WITH_CONCERNS`, `NEEDS_CORRECTION`, or `BLOCKED` | `<evidence>` | `<next action>` |
| `PM/owner acceptance` | `<Project Manager/project owner>` | `<decision record>` | `<accepted/accepted_with_concerns/close_blocked/deferred/abandoned/superseded/pending>` | `<authority/evidence>` | `<next action>` |
| `Closeout` | `<closeout owner>` | `<closeout file>` | `<not_started/drafted/finalized>` | `<evidence>` | `<next action>` |

When Final Review returns `NEEDS_CORRECTION` or `BLOCKED`, the next action must
name a corrective packet, Project Manager decision request, blocker, or waiver
path.

`HANDOFF` is not a terminal milestone or closeout state. A blocked milestone
remains open until an authorized owner records resume, close-blocked, abandon,
or defer; resume does not permit closeout.

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
