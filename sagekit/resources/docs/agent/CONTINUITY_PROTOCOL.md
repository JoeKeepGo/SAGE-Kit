# Continuity Protocol

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
candidate:
next_action:
allowed_paths:
stop_conditions:
```

It also carries a schema version and timestamps. Authority contains a bounded
summary, a version, an internal digest, and optional repository-relative file
references with SHA-256 digests. Evidence references are compact fingerprints
or repository-relative digests, never copied logs.

## Commands

```text
sagekit checkpoint create
sagekit checkpoint status
sagekit resume
sagekit checkpoint clear
```

`checkpoint create` captures the canonical repository, named branch, HEAD,
authority, preliminary and per-candidate final counters, optional frozen
candidate, allowed paths, and next action. `checkpoint status` verifies
the current state without printing the full checkpoint. `sagekit resume`
returns the bounded resume packet. It never executes arbitrary commands.
`checkpoint clear` removes only `CURRENT_RUN.json`.

Use repeated `--counter NAME=VALUE` arguments when creating a checkpoint.
Callers that hold an authority anchor should pass `--expect-authority-id` and
`--expect-authority-version` to `status` or `resume`; a mismatch fails closed.

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

Checkpoint schema v2 preserves preliminary counts separately from final
full-suite and wheel/install counts keyed by candidate fingerprint. A v1
checkpoint's old aggregate full-suite and wheel counts migrate conservatively
to preliminary counts; they never consume a final-candidate budget.

Any mismatch must fail closed. Report all repository, branch, HEAD, authority,
and evidence differences in one result; do not continue from a partly matching
state. Missing and corrupt checkpoints use distinct findings.

Reaching a deterministic worker, review, or verification limit creates or
refreshes this checkpoint and returns `HANDOFF_READY`. The user does not need to
copy prior chat history into the next session.

## Source Hygiene

Source-repository checks must emit:

```text
FAIL: .sagekit/runtime content is tracked by Git
```

The finding rule may carry the machine-readable form, but its message must name
the tracked runtime paths. Packaged templates and policies remain trackable;
runtime instances do not.

Cross-machine export/import is outside the MVP.
