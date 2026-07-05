# M<ID> Entry Gate: <Name>

Use this template to start a milestone.

## Objective

State the one milestone outcome.

## Accepted Inputs

- `<input doc, decision, baseline, or artifact>`

## Scope

- `<included scope>`

## Non-Goals

- `<excluded scope>`

## Closed Approval Gates

- `<gate>`

## Phase Decomposition Matrix

Implementation must not start until every phase row is concrete.

| Phase | Objective | Owner | Contract | Allowed Files | Read-Only Files | Forbidden Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<files>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

## Shared Files

| File | Owner | Rule |
|---|---|---|
| `<file>` | `<owner>` | `<serial-only or exclusive lane>` |

## Wave Policy

State which phases may use Wave Execution and which must remain serial.

## Milestone Closure Gate

Final milestone acceptance follows this order:

1. Required phases are `accepted` or explicitly `superseded`.
2. The milestone ledger is current.
3. `MILESTONE_CLOSEOUT.md` is written or updated.
4. The milestone is marked closed or accepted.

The milestone can be closed only after:

- every required phase is `accepted` or explicitly `superseded`;
- blocking gates are `PASS` or explicitly `WAIVED` by the project owner;
- runtime evidence is fresh where applicable;
- closed approval gates remain closed unless explicitly opened;
- `MILESTONE_CLOSEOUT.md` summarizes the milestone outcome and links to
  evidence;
- final handoff records remaining gaps.
