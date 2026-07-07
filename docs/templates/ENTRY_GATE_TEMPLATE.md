# M<ID> Entry Gate: <Name>

Use this template to start a milestone.

## Objective

State the one milestone outcome.

## Primary Capability

Name the one primary capability from `docs/CAPABILITY_MAP.md`, or record `N/A`
with a reason when no capability map is used.

## Accepted Inputs

- `<input doc, decision, baseline, or artifact>`

## Scope

- `<included scope>`

## Non-Goals

- `<excluded scope>`

## Closed Approval Gates

- `<gate>`

## Governance Level

Use `docs/agent/GOVERNANCE_LEVELS.md`.

- Milestone controller level: `Light`, `Standard`, or `Heavy`
- Why this level:
- Controls Enabled:
- Controls Not Enabled:
- Worker or lane level policy:

## Phase Decomposition Matrix

Implementation must not start until every phase row is concrete.

| Phase | Governance Level | Objective | Owner | Contract | Allowed Files | Read-Only Files | Forbidden Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `Light, Standard, or Heavy` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<files>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

## Shared Files

| File | Owner | Rule |
|---|---|---|
| `<file>` | `<owner>` | `<serial-only or exclusive lane>` |

## Wave Policy

State which phases may use Wave Execution and which must remain serial.

## Worktree Isolation Policy

State whether Project Manager allows worktree isolation.

If yes, define:

- allowed mode;
- maximum worktree count;
- branch and worktree naming;
- base branch or commit;
- phases or lanes eligible for isolation;
- shared files that remain serial;
- runtime ownership;
- integration owner;
- submit authority;
- cleanup policy.

## Task Dispatch Policy

State whether this milestone adopts Task Dispatch Profile.

If yes, define:

- dispatch board path;
- task record root;
- evidence record root;
- required L0-L4 levels by task class;
- resource lock policy;
- Run/Attempt/Lease policy;
- validator command;
- gate where validator success is required;
- owner of task record updates;
- owner of evidence record updates.

## Capability Routing Policy

State which specialist skills, plugins, connectors, or tools should be used for
implementation, validation, review, runtime smoke, or artifact work when the
agent runtime exposes them.

If superpowers is available, list the specific skills that may be used for
execution discipline inside this milestone boundary.

Do not require loading every capability body by default. Select from metadata
and load only the selected capability instructions.

## Session Orchestration Policy

State whether this milestone uses Session Orchestration.

If yes, name:

- Project Manager Controller;
- Coder Controller;
- Final Review Controller;
- corrective round limit;
- packet storage location.

## Milestone Closure Gate

Final milestone acceptance follows this order:

1. Required phases are `accepted` or explicitly `superseded`.
2. The milestone ledger is current.
3. `MILESTONE_CLOSEOUT.md` is written or updated.
4. The milestone is marked closed or accepted.

The milestone can be closed only after:

- every required phase is `accepted` or explicitly `superseded`;
- blocking gates are `PASS` or explicitly `WAIVED` by the project owner;
- Task Dispatch validator passes when the profile is active and the gate
  requires it;
- runtime evidence is fresh where applicable;
- closed approval gates remain closed unless explicitly opened;
- `MILESTONE_CLOSEOUT.md` summarizes the milestone outcome and links to
  evidence;
- final handoff records remaining gaps.
