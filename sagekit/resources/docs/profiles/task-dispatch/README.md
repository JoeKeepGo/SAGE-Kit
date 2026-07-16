# Task Dispatch Profile

## Validation Contract

New and active task/evidence pairs declare the v2 `validation_contract` block
shown in the templates. The policy digest must match the packaged v2 policy.
Terminal legacy pairs without version metadata use frozen v1 only with trusted
accepted closeout authority for an inactive milestone.
Mixed records, unversioned active records, unsupported versions, and policy
tamper fail closed. A v2 failure never falls back to v1.

See `docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md`. Closed history is
excluded from active duplicate, lease, lock, and dispatch-board reconciliation
after its own pair validation.

Task Dispatch is an optional SAGE-Kit profile for milestones that need stronger
task dispatch, evidence capture, resource coordination, and gate closeout than
plain phase documents provide.

Use it when a milestone has many worker tasks, repeated validation paths,
resource contention, cross-surface integration, or a high risk of verbal
green-lighting without machine-checkable evidence.

Do not use it for small single-phase changes where normal phase docs,
completion reports, and quality gates already provide enough control.

## What It Adds

- `task.yaml`: the structured task record.
- `evidence.yaml`: the structured evidence record.
- Run, Attempt, and Lease records for worker execution.
- Resource locks for shared files, runtimes, databases, devices, queues, or
  external services.
- L0-L4 evidence levels for progressive verification.
- A validator that catches missing records, mismatched task IDs, incomplete
  required evidence, unsafe mock fallback, active lease gaps, and common
  surface-specific evidence gaps.
- A State Truth Reconciliation gate defined in `DISPATCH_PROFILE.md`.

## Files

```text
docs/profiles/task-dispatch/
  DISPATCH_PROFILE.md
  README.md
  schemas/
    task.schema.json
    evidence.schema.json
  templates/
    TASK_RECORD_TEMPLATE.yaml
    EVIDENCE_RECORD_TEMPLATE.yaml
    DISPATCH_BOARD_TEMPLATE.md
    DECISIONS_TEMPLATE.md
scripts/
  validate_task_dispatch.py
```

## Adoption

Copy the profile into a project only when the project explicitly adopts
structured task dispatch. A typical project layout is:

```text
docs/M<ID>/
  MILESTONE_LEDGER.md
  dispatch/
    DISPATCH_BOARD.md
    decisions.md
    TASK-001/
      task.yaml
      evidence.yaml
```

Run gate-ready validation before a task, phase, or milestone gate is accepted:

```bash
python scripts/validate_task_dispatch.py \
  --gate-ready \
  --task docs/M<ID>/dispatch/TASK-001/task.yaml \
  --evidence docs/M<ID>/dispatch/TASK-001/evidence.yaml \
  --schema-dir docs/profiles/task-dispatch/schemas
```

The profile is a structured evidence layer. It does not replace phase docs,
quality gates, completion reports, milestone ledgers, or Project Manager final
decision authority.

For `Light` work it remains inactive unless an activation trigger is present.
When active, apply the profile reconciliation gate to the whole dispatch set;
orphan records and overlapping active exclusive locks are invalid.
