# Task Dispatch Profile

Validation contract selection is governed by
`docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md`. Active and new records use
explicit v2 metadata and are strict: a selected v2 failure fails closed and
never tries another contract. Frozen v0/v1 are compatibility-only for
explicitly selected, accepted immutable-history containers. A Validation Scope
Manifest may provide that explicit migration authority and select frozen v0 or
v1 for each declared container, but cannot authorize current, nonterminal, or
unlisted work. Accepted history remains read-only: validation never writes it
back, batch-rewrites it, or represents it as v2.
Ambiguous or mixed records fail closed, and validation failure never triggers
another contract.
Frozen schema runtime behavior follows the selected historical validator: v0
retains digest-bound schema artifacts but validates records with its Python
rules, while the hardened v1 baseline also executes its frozen schema checks.

This profile adds machine-checkable task and evidence records to SAGE-Kit. It
is optional. It becomes active only when the active project's authority or its
active execution packet explicitly adopts Task Dispatch for the current task,
phase, or gate. A milestone entry gate or normalized project configuration may
be that active project authority. The presence of a `dispatch` directory,
`task.yaml`, `evidence.yaml`, board, or template is discovery input only and
never activates this profile.

Historical use, accepted legacy records, a legacy v0/v1 compatibility result,
or a `Heavy` governance level never activates Task Dispatch. They may explain
why an active project authority chooses to adopt it, but they are not adoption
authority.

## Activation Criteria

An active project authority may use these considerations when deciding whether
to adopt this profile:

- many worker tasks must be dispatched and reconciled;
- task outcomes need structured evidence rather than narrative summaries;
- several workers compete for shared files, runtimes, databases, queues,
  devices, test accounts, or external services;
- bug/spec/integration work needs repeatable verification across attempts;
- the milestone has a high risk of being marked complete from self-report
  instead of evidence;
- Final Review needs a compact index of what was tested, blocked, waived, or
  proven.

Do not enable it only because a project uses SAGE-Kit. These considerations,
the project history, and the selected governance level are not automatic
triggers. For small work, normal phase docs and completion reports are lighter
and usually better.

For `Light`, `Standard`, and `Heavy` work, Task Dispatch remains off unless the
active project authority or active execution packet explicitly enables it.
Profile absence does not block the basic Harness, normal phase documents, or
ordinary quality gates for `Light` and `Standard` work; it only omits this
profile's structured-record and validator gates.

## Canonical Governance Pointers

This profile does not redefine Core, Loop, or Graph governance. Core authority
and approval semantics are canonical at `docs/SAGE_CORE.md#sage-auth-001`;
review, corrective, evidence-reuse, and completion-loop semantics are canonical
at `docs/agent/EXECUTION_ECONOMY.md#sage-loop-013`; dependency-graph and
execution-shape semantics are canonical at `docs/SAGE_CORE.md#sage-grf-001`
and `docs/agent/WAVE_EXECUTION.md#sage-grf-002`. This profile defines only the
Task Dispatch-specific record, evidence, lock, reconciliation, and validator
semantics below.

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

When the active project authority or active execution packet activates this
profile, the host must invoke the
compatibility-aware Task Dispatch validation operation exposed by the embedded
Harness before accepting the task, phase, or milestone gate. The Harness first
resolves profile activation, container scope, and the declared validation
contract, then selects frozen v0/v1 only for explicitly authorized accepted
immutable history or strict current v2 for active work. Ambiguous authority,
mixed metadata, and validation failure fail closed without contract fallback.

The procedural `validate_records` function is an implementation detail of the
selected current contract. It is not a standalone gate API. SAGE-Kit does not
ship or document a Task Dispatch command-line validator.

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
After explicit activation for the current task, phase, or gate, read them only
when:

- the active task, phase, or gate uses this profile;
- routing points to a task or evidence record for that active use;
- an active profile gate, review, or closeout needs structured task evidence;
- Project Manager, Coder, or Final Review is reconciling active dispatched
  work.

Routing and historical record pointers are read pointers only; neither can
activate the profile. When the profile is absent, do not require Task Dispatch
records, reconciliation, or validation for the basic `Light` or `Standard`
Harness path.

The milestone ledger should link to task records instead of copying their full
contents.
