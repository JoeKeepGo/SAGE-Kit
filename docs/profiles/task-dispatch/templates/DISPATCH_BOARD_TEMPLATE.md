# Dispatch Board: M<ID>

Use this board as a compact index. Keep detailed task evidence in each task's
`task.yaml` and `evidence.yaml`.

## Active Tasks

| Task | Type | Priority | Owner | Status | Required Levels | Resource Locks | Evidence | Next Action |
|---|---|---|---|---|---|---|---|---|
| `TASK-000` | `spec` | `P2` | `unassigned` | `NEW` | `L0` | `none` | `TASK-000/evidence.yaml` | `define scope` |

## Resource Locks

| Resource | Owner | Mode | Status | Expires Or Release Rule | Task |
|---|---|---|---|---|---|
| `<resource>` | `<owner>` | `exclusive/shared` | `active/released` | `<rule>` | `<task>` |

## Blocked Tasks

| Task | Blocker | Owner | Decision Needed | Since |
|---|---|---|---|---|
| `<task>` | `<blocker>` | `<owner>` | `<decision>` | `<date/ref>` |

## Gate Candidates

| Task | Gate | Validator | Final Review Focus |
|---|---|---|---|
| `<task>` | `<task/phase/milestone>` | `<pass/fail/not run>` | `<focus>` |
