# Dispatch Board: M<ID>

Use this board as a compact index. Keep detailed task evidence in each task's
`task.yaml` and `evidence.yaml`.

- Board owner: `<named Dispatch Controller>`
- Board authority: `<source / grant / scope>`
- Current phase: `<phase>`
- Current next action: `<next action>`

## Active Tasks

| Task | Type | Priority | Task / Evidence Owner | Status | Phase | Authority Ref | Required Levels | Resource Locks | Evidence | Next Action |
|---|---|---|---|---|---|---|---|---|---|---|
| `TASK-000` | `spec` | `P2` | `task-owner / validation-owner` | `NEW` | `triage` | `<ref>` | `L0` | `none` | `TASK-000/evidence.yaml` | `define scope` |

## Resource Locks

| Resource | Owner | Mode | Status | Carried / Source | Expires Or Release Rule | Released / Evidence | Task |
|---|---|---|---|---|---|---|---|
| `<resource>` | `<owner>` | `exclusive/shared` | `ACTIVE/HELD/RELEASED/EXPIRED` | `<no, or yes/ref>` | `<expiry/rule>` | `<time/evidence or n/a>` | `<task>` |

Overlapping `ACTIVE` or `HELD` exclusive locks across tasks fail validation.

## Blocked Tasks

| Task | Blocker | Owner | Decision Needed | Since |
|---|---|---|---|---|
| `<task>` | `<blocker>` | `<owner>` | `<decision>` | `<date/ref>` |

## Gate Candidates

| Task | Gate | Validator | Final Review Focus |
|---|---|---|---|
| `<task>` | `<task/phase/milestone>` | `<pass/fail/not run>` | `<focus>` |

## State Truth Reconciliation

| Task | Applicable / Reason | Profile Ref | Owners / Authority Checked | Mismatches Or Handoff | Result |
|---|---|---|---|---|---|
| `<task>` | `<yes or N/A reason>` | `DISPATCH_PROFILE.md` | `<refs>` | `<none/ref>` | `PASS/BLOCKED/N/A` |
