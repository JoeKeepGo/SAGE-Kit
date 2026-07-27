# Task Dispatch Profile

## Validation Contract

New and active task/evidence pairs declare the strict v2
`validation_contract` block shown in the templates. The policy digest must
match the packaged v2 policy, and a selected v2 failure never falls back to
another version. Frozen v0/v1 are compatibility-only for explicitly selected,
accepted immutable-history containers. Existing projects may supply an explicit
Validation Scope Manifest as migration authority when newer structured
active-set fields are unavailable. Each accepted legacy container names its
target-relative path and exact contract version; unlisted, conflicting, mixed,
current, or nonterminal records still fail closed. Accepted history is
read-only: validation does not write it back, batch-rewrite it, or present it
as v2.
Mixed records, unversioned active records, unsupported versions, and policy
tamper fail closed. Validation never tries another version after a failure.

See `docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md`. Closed history is
excluded from active duplicate, lease, lock, and dispatch-board reconciliation
after its own pair validation.

Task Dispatch is an optional SAGE-Kit profile for milestones that need stronger
task dispatch, evidence capture, resource coordination, and gate closeout than
plain phase documents provide. It is active only when active project authority
or the active execution packet explicitly adopts it for the current task,
phase, or gate.

When project authority activates the profile, the Harness may discover bounded
record pairs below one `docs/**/dispatch/` segment. Discovery does not activate
the profile. A manifest may also authorize a generic non-milestone container.
Framework templates, profile resources, `_TEMPLATE` paths, nested `dispatch`
paths, and target-external symlinks are excluded.

Historical use, accepted legacy records, v0/v1 compatibility results, and a
`Heavy` governance level are not activation authority. Record, directory, or
routing-pointer presence is also not activation authority.

Use it when a milestone has many worker tasks, repeated validation paths,
resource contention, cross-surface integration, or a high risk of verbal
green-lighting without machine-checkable evidence.

Do not use it for small single-phase changes where normal phase docs,
completion reports, and quality gates already provide enough control.

Profile absence does not block the basic Harness, ordinary phase documents, or
ordinary quality gates for `Light` and `Standard` work. It only omits this
profile's structured-record, reconciliation, and validator gates.

## Canonical Governance Pointers

Task Dispatch does not redefine Core, Loop, or Graph governance. Core authority
and approval semantics are canonical at `docs/SAGE_CORE.md#sage-auth-001`;
review, corrective, evidence-reuse, and completion-loop semantics are canonical
at `docs/agent/EXECUTION_ECONOMY.md#sage-loop-013`; dependency-graph and
execution-shape semantics are canonical at `docs/SAGE_CORE.md#sage-grf-001`
and `docs/agent/WAVE_EXECUTION.md#sage-grf-002`. This profile supplies only its
task/evidence, lock, reconciliation, and validation behavior.

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
```

## Adoption

Copy the profile into a project only when active project authority or an active
execution packet explicitly adopts structured task dispatch. The selection
considerations above, historical use, and governance level do not activate it.
A typical project layout is:

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

Before accepting a task, phase, or milestone gate, the host invokes the
compatibility-aware Task Dispatch validation operation exposed by the embedded
Harness. It resolves project activation and container authority before selecting
frozen v0/v1 history validation or current v2 validation. Bare procedural
validation is not a gate API.

The profile is a structured evidence layer. It does not replace phase docs,
quality gates, completion reports, milestone ledgers, or Project Manager final
decision authority.

For `Light`, `Standard`, and `Heavy` work it remains inactive unless active
project authority or the active execution packet explicitly enables it. Record
or directory presence is not activation authority.
When active, apply the profile reconciliation gate to the whole dispatch set;
orphan records and overlapping active exclusive locks are invalid.
