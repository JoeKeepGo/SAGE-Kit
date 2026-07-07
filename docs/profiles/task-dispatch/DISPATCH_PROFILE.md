# Task Dispatch Profile

This profile adds machine-checkable task and evidence records to SPEC-Kit. It
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

Do not enable it only because a project uses SPEC-Kit. For small work, normal
phase docs and completion reports are lighter and usually better.

## Records

Each dispatched task should have:

- `task.yaml`: scope, owner, status, dependencies, resource locks, required
  evidence levels, and run records.
- `evidence.yaml`: changed surfaces, executed checks, artifacts, L0-L4
  evidence, blockers, and conclusion.

The two files must share the same task ID.

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

An active run that uses a shared resource must have an active lease with owner,
resource, mode, and expiration or release rule.

## Resource Locks

Resource locks are coordination facts, not permission to widen scope.

Use locks to prevent two workers from editing or testing through the same
exclusive surface at the same time. Shared locks must still name the integration
owner and conflict rule.

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

## Mock And Fallback Rule

Mock fallback may be used only when the task explicitly allows it or when the
project owner accepts the fallback as a waiver. The evidence record must state
that a mock was used, why real evidence was unavailable, who accepted the
fallback, the accepted scope, and what follow-up remains.

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
