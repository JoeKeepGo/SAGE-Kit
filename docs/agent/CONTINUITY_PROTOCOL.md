# Continuity Protocol

Candidate binding, evidence reuse, and opt-in convergence semantics are
canonical at `docs/agent/EXECUTION_ECONOMY.md#sage-loop-006`,
`docs/agent/EXECUTION_ECONOMY.md#sage-loop-007`, and
`docs/agent/EXECUTION_ECONOMY.md#sage-loop-009`. This document owns only their
checkpoint serialization, resume validation, and fail-closed continuity delta.

SAGE-Kit uses one local, compact checkpoint:

```text
.sagekit/runtime/CURRENT_RUN.json
```

The file is runtime state. It is gitignored, must never be tracked, and contains
no complete chat transcript, credentials, secrets, or unbounded command output.

## Checkpoint Fields

The checkpoint records:

```yaml
run_id:
goal:
repository_root:
branch:
base_sha:
head_sha:
authority:
change_class:
completed_work:
open_findings:
evidence_references:
invalidated_evidence:
execution_counters:
  verification_attempts:
candidate:
  authority_anchor:
  root_cause_id:
  open_findings_count:
  no_progress_rounds:
  convergence_authority_digest:
  root_cause_family:
  finding_severity:
  targeted_review_closed:
  finding_trend:
convergence_authority:
  authority_id:
  execution_scope:
  root_cause_family:
  allowed_paths:
  invariant:
  semantic_change_policy:
  targeted_review_required:
  stop_conditions:
  approved_by:
  authority_ref:
next_action:
allowed_paths:
stop_conditions:
```

It also carries a schema version and timestamps. Authority contains a bounded
summary, a version, an internal digest, and optional repository-relative file
references with SHA-256 digests. Evidence references are compact fingerprints
or repository-relative digests, never copied logs.

## API Surface

```python
sagekit.create_checkpoint(
    repository_root,
    *,
    run_id=..., goal=..., authority_id=..., authority_version=...,
    authority_summary=..., change_class=..., completed_work=...,
    open_findings=..., evidence_references=..., invalidated_evidence=...,
    execution_counters=..., next_action=..., allowed_paths=...,
    stop_conditions=..., authority_references=(), base_sha=None,
    candidate=None, convergence_authority=None,
)
sagekit.get_checkpoint_status(repository_root)
sagekit.resume_checkpoint(
    repository_root,
    *,
    expected_authority_id=None,
    expected_authority_version=None,
    expected_convergence_authority=None,
)
sagekit.clear_checkpoint(repository_root)
```

`sagekit.create_checkpoint` captures the canonical repository, named branch, HEAD,
authority, preliminary and per-candidate final counters, started verification
attempts, optional frozen candidate, allowed paths, and next action.
`sagekit.get_checkpoint_status` is structural and parse-only: it validates the
stored checkpoint but does not verify current repository state. Use
`sagekit.resume_checkpoint` for current-state validation and the bounded resume
packet. It
returns the bounded resume packet. It never executes arbitrary commands.
`sagekit.clear_checkpoint` removes only `CURRENT_RUN.json`.

Pass an `ExecutionCounters` value when creating a checkpoint.
Callers that hold an authority anchor should pass `expected_authority_id` and
`expected_authority_version` to `sagekit.resume_checkpoint`; a mismatch fails
closed. `get_checkpoint_status` accepts no current-authority expectation.
Callers resuming a Preauthorized Convergence Window may pass
`expected_convergence_authority` to `sagekit.resume_checkpoint`; replacement of
its digest, allowed paths, execution scope, family, invariant, or stop
conditions fails closed.

## Resume Contract

Resume:

1. finds and parses the checkpoint;
2. validates schema and size bounds;
3. verifies repository root, branch, and exact HEAD;
4. verifies the whole continuation payload digest, the authority payload,
   optional caller authority anchors, and reference digests;
5. verifies typed file or evidence-fingerprint references;
6. verifies any candidate HEAD/diff fingerprint and closure state;
7. emits completed work, open findings, invalidated evidence, counters,
   candidate, allowed paths, stop conditions, and `next_action`.

The checkpoint schema v4 preserves structured verification attempts, including
attempt id, kind, stage, candidate fingerprint, preflight checks, and lifecycle
state. Resuming a `STARTED`, `PASSED`, `FAILED`, or `ABORTED` attempt never
increments its counter again.
The checkpoint persists started verification attempts before handoff so resume
cannot repeat their consumption.

When a human-approved corrective resumes `HANDOFF_READY`, the successor
candidate persists its authority anchor, root-cause id, current finding count,
and consecutive no-progress rounds. Resume therefore cannot turn an
unapproved handoff into automatic execution or alter the canonical convergence
outcome at `docs/agent/EXECUTION_ECONOMY.md#sage-loop-008`.

Schema v4 also persists the complete serialized Preauthorized Convergence
Window and binds its digest to the current candidate. Resume restores the
authority id, execution scope, root-cause family and id, finding count and
severity, no-progress rounds, allowed paths, invariant, stop conditions,
targeted-review state, and current candidate. Authority, allowed-path, or
invariant replacement fails closed. A checkpoint cannot synthesize approval.

A v3 checkpoint preserves structured attempts but has no convergence-authority
field; it resumes with the window inactive. A v2 checkpoint has per-candidate
counters but no attempt records; it resumes
with an empty attempt map while preserving those counters, so exhausted
candidate budgets remain exhausted. A v1 checkpoint's old aggregate full-suite
and wheel counts migrate conservatively to preliminary counts; they never
consume a final-candidate budget or fabricate a started attempt.

Any mismatch must fail closed. Report all repository, branch, HEAD, authority,
and evidence differences in one result; do not continue from a partly matching
state. Missing and corrupt checkpoints use distinct findings.

Reaching a deterministic worker, review, or verification limit creates or
refreshes this checkpoint and records the canonical local-limit outcome from
`docs/agent/EXECUTION_ECONOMY.md#sage-loop-008`. The user does not need to copy
prior chat history into the next session.

## Source Hygiene

Source-repository checks must emit:

```text
FAIL: .sagekit/runtime content is tracked by Git
```

The finding rule may carry the machine-readable form, but its message must name
the tracked runtime paths. Packaged templates and policies remain trackable;
runtime instances do not.

Cross-machine export/import is outside the MVP.
