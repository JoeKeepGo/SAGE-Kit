# Task Dispatch Profile

Validation contract selection is governed by
`docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md`. Active/new records use
explicit v2 metadata. Terminal unversioned history uses only the frozen
contract selected by trusted accepted immutable container scope. A Validation
Scope Manifest may provide explicit migration authority and select frozen v0
or v1 for each declared container, but cannot authorize nonterminal or
unlisted work.
Ambiguous or mixed records fail closed, and validation failure never triggers
another contract.
Frozen schema runtime behavior follows the selected historical validator: v0
retains digest-bound schema artifacts but validates records with its Python
rules, while the hardened v1 baseline also executes its frozen schema checks.

This profile adds machine-checkable task and evidence records to SAGE-Kit. It
is optional and should be activated by the Project Manager in the milestone
entry gate or execution packet.

## Activation Criteria

Use this profile when at least one condition is true:

- many worker tasks must be dispatched and reconciled;
- task outcomes need structured evidence rather than narrative summaries;
- several workers compete for shared files, runtimes, databases, queues,
  devices, test accounts, or external services;
- bug/spec/integration work needs repeatable verification across attempts;
- the milestone has a high risk of being marked complete from self-report
  instead of evidence;
- Final Review needs a compact index of what was tested, blocked, waived, or
  proven.

Do not enable it only because a project uses SAGE-Kit. For small work, normal
phase docs and completion reports are lighter and usually better.

For `Light` work, Task Dispatch is off unless an activation condition above or
an entry-gate trigger explicitly enables it.

## Records

Each dispatched task should have:

- `task.yaml`: scope, owner, status, dependencies, resource locks, required
  evidence levels, and run records.
- `evidence.yaml`: changed surfaces, executed checks, artifacts, L0-L4
  evidence, blockers, and conclusion.

The two files must share the same task ID.

An orphan `task.yaml` or `evidence.yaml` is invalid. Every board task must
resolve to exactly one matching pair, and every pair must appear on the board
or be explicitly archived by an active decision.

## Record Contract

- IDs, objective, runtime shape, owner, authority source/grant/scope, phase,
  and next action are non-empty.
- Top-level `task.status` is the sole task lifecycle status. Lifecycle phase,
  review result, and next action use the schema contract.
- Run attempts are positive integers. Accepted run status values are exactly
  `PENDING`, `RUNNING`, `PASSED`, `FAILED`, `BLOCKED`, and `ABORTED`; aliases
  are invalid.
  `uses_shared_resource` is explicit; a lease is required only when it is
  `true`.
- A lease names resource, owner, mode, status, and an expiry or release rule.
- Locks name status and whether they were carried. Carried locks name their
  source; released locks name release time and evidence.
- `VERIFIED` and `CLOSED` tasks include `accepted_by`, `accepted_at`,
  `review_result`, and `evidence_ref`; `CLOSED` also includes `closed_at`.
- Evidence records name highest level, changed surfaces, artifacts, skipped
  checks, command provenance, blockers, and next action. Required-command IDs
  are unique `CMD-*` values and map exactly to
  `artifacts.commands[].command_id` or `skipped_checks[].id`. Skipped-check IDs
  are unique `CMD-*` or `CHECK-*` values; `CMD-*` means the named required
  command was skipped.
- Mock use records rationale, scope, follow-up, `mock_accepted_by`, and an
  acceptance reference. When fallback is accepted, its acceptor, scope,
  reason, and reference must be coherent with the mock acceptance metadata.

## Evidence Levels

| Level | Meaning | Typical Evidence |
|---|---|---|
| `L0` | Static and structural evidence. | Files changed, diff review, lint, typecheck, schema presence. |
| `L1` | Focused behavior evidence. | Unit tests, component tests, fixture checks. |
| `L2` | Contract or integration evidence. | API, event, CLI, worker, database, or consumer checks. |
| `L3` | Runtime evidence. | Live process, logs, curl, CLI invocation, browser smoke, queue/device smoke. |
| `L4` | Release or production-path evidence. | Build artifact, packaging, deploy smoke, rollback note, monitoring check. |

The Project Manager decides which levels are required for each task. A task
cannot be marked verified unless every required level is `PASS`, `N/A` with a
reason, or explicitly waived by the project owner through the normal quality
gate process.

When a required level is `WAIVED`, the evidence record must include `reason`,
`waived_by`, and `waiver_scope`. `N/A` requires a concrete reason.

## Run, Attempt, And Lease

Use Run records to show who attempted the task and what happened.

Use Lease records when a worker holds a scarce or shared resource:

- file or generated artifact ownership;
- migration or lockfile ownership;
- local runtime port, device, queue, browser, database, or test account;
- external service quota or integration environment.

Only a run with `uses_shared_resource: true` requires a lease. The lease names
owner, resource, mode, status, and expiration or release rule; release is
recorded when the run no longer holds the resource.

## Resource Locks

Resource locks are coordination facts, not permission to widen scope.

Use locks to prevent two workers from editing or testing through the same
exclusive surface at the same time. Shared locks must still name the integration
owner and conflict rule.

Two tasks holding overlapping `ACTIVE` or `HELD` exclusive locks is a
validation failure, even when each task/evidence pair is valid alone. A carried
lock remains active until its named owner records release; a `RELEASED` lock
cannot authorize later work.

## State Truth Reconciliation Gate

Before an acceptance gate advances, compare task `status`, authority, and
`lifecycle.phase`, `lifecycle.review_result`, and `lifecycle.next_action` with
evidence `conclusion.status`, `conclusion.review_result`,
`conclusion.next_action`, authority, and phase. Reconcile those values with the
board/ledger state, active decision, active run/lease/lock, changed-surface
evidence, and result/review packets. Missing, stale, orphaned, or conflicting
truth blocks the gate.

Reconciliation is inspect-only by default. Mutation requires both the named
surface owner and matching write or corrective authority:

| Surface | Named Owner |
|---|---|
| Dispatch board | Dispatch Controller named by the entry gate |
| Task record | Task owner named in `task.yaml` |
| Evidence record | Evidence owner named by the entry gate |
| Milestone ledger | Project Manager Controller |
| Decision log | Project Manager Controller |
| Result packet | Coder Controller or named packet author |
| Review packet | Final Review Controller or named packet author |

When the reconciler is not that owner with authority, it emits an update
proposal, corrective packet, or `HANDOFF`; it does not repair the surface.
Only an `ACTIVE` decision supplies current authority. `PROPOSED`,
`SUPERSEDED`, `REVOKED`, or `EXPIRED` stop decisions are historical evidence,
not current authority.

## Validator Gate

When this profile is active, run the validator in gate-ready mode before
accepting the task, phase, or milestone gate:

```bash
python scripts/validate_task_dispatch.py \
  --gate-ready \
  --task <path/to/task.yaml> \
  --evidence <path/to/evidence.yaml> \
  --schema-dir docs/profiles/task-dispatch/schemas
```

Default validator success means the structured records are complete enough to
review. Gate-ready validator success additionally means the task/evidence
records claim verified status, required levels are `PASS`, `N/A`, or `WAIVED`,
and no blockers remain. It still does not mean the work is correct. Final
Review must inspect the actual evidence and changed files needed for the
verdict.

Pair validation does not replace dispatch-set reconciliation. Acceptance also
requires no orphan records, no cross-task exclusive-lock conflict, and a
passing State Truth Reconciliation gate.

## Mock And Fallback Rule

Mock fallback may be used only when the task explicitly allows it or when the
project owner accepts the fallback as a waiver. The evidence record must state
that a mock was used, why real evidence was unavailable, its scope, follow-up,
who accepted it, the accepted scope, and the authority reference.

Hidden fallback paths are blockers.

## Routing Rule

Do not add task-dispatch records to default startup context for every session.
Read them only when:

- the active task uses this profile;
- `DOC_ROUTING.md` points to a task or evidence record;
- a gate, review, or closeout needs structured task evidence;
- Project Manager, Coder, or Final Review is reconciling dispatched work.

The milestone ledger should link to task records instead of copying their full
contents.
