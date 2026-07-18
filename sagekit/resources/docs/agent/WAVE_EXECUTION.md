# Wave Execution

Wave Execution speeds up development by parallelizing safe work across
independent phases or inside a phase while keeping integration, final
verification, approval gates, and submission serial.

For milestone-level Project Manager, Coder, and Final Review controller
handoff, use `docs/agent/SESSION_ORCHESTRATION.md`. Wave Execution remains the
rule for safe parallel phases and phase-internal lanes.

The rule is:

```text
dependency DAG controls phase order
waves run in parallel where safe
gates stay serial
governance level is assigned per lane
permission mode is assigned per lane
```

Heavy governance does not create wave readiness by itself. If a lane cannot be
made independent, keep that lane or affected node serial and continue testing
the remaining candidates for safe parallel execution.

Shared serial ownership does not justify milestone-wide serial execution.
Keep shared files with a named serial integration owner and evaluate the
remaining mutually exclusive files as parallel candidates. Before declaring
`SERIAL`, record the dependency DAG, serial barriers, phase-internal lanes, and
the concrete phase or lane dependency, file conflict, gate, or runtime
ownership reason that prevents safe parallel work.

Do not repartition an already active phase by default. Adopt a changed wave
shape at the next safe barrier or wave unless active authority explicitly
permits repartitioning.

## Why Waves Exist

Linear phase execution is safe but slow. Unbounded parallel execution is fast
but risky. Wave Execution keeps the phase as the reviewable unit while allowing
read-only lanes, disjoint writable lanes, and validation lanes to run in
parallel.

## Standard Wave Shape

| Wave | Purpose | Parallelism |
|---|---|---|
| Wave 0 | Controller reads context, confirms scope, and defines file ownership. | Serial |
| Wave 1 | Read-only exploration, risk scan, contract review, and test gap review. | Parallel |
| Wave 2 | Contract, schema, file ownership, and lane plan freeze. | Serial |
| Wave 3 | Disjoint implementation lanes. | Parallel when file ownership does not overlap |
| Wave 4 | Validation, review, targeted tests, and regression checks. | Parallel |
| Wave 5 | Integration, final verification, ledger update, and handoff. | Serial |

## Controller Responsibilities

The controller owns:

- phase scope;
- lane governance levels;
- lane permission modes;
- wave plan;
- file ownership table;
- lane prompts or task cards;
- conflict resolution;
- final integration;
- final verification;
- milestone ledger updates;
- active context and document routing maintenance;
- serial integration of memory update proposals;
- git operations when used.

The controller should not use waves as a label for doing all implementation
work directly. If the controller is also the only writable executor, the phase
is serial unless it meets the Coder self-execution policy in
`docs/agent/SESSION_ORCHESTRATION.md`.

## Wave Readiness Gate

Before Wave 1 starts, the controller must prove that wave execution is useful
and safe.

Wave readiness requires:

- at least two lanes with distinct objectives or evidence roles;
- exclusive writable files for every writable lane;
- shared files assigned to a serial controller or integration lane;
- frozen public contracts before writable lanes;
- named runtime ownership for browser, server, database, queue, device, or
  external service checks;
- clear lane evidence and return packet expectations;
- a named integration owner;
- stop conditions for file conflicts, contract drift, runtime conflicts, and
  failed required evidence.

A missing readiness item serializes only the affected node; continue evaluating
unaffected parallel candidates. Milestone-wide `SERIAL` is allowed only when
the barrier cannot be isolated. Return `STOP_FOR_PM` only when resolving the
affected node requires authority outside the approved plan. Do not start
parallel writable lanes from broad labels such as "frontend", "backend",
"tests", or "polish" unless each lane has concrete file ownership and evidence.

## Safe Parallel Work

These lanes are usually safe to parallelize:

- read-only spec review;
- read-only code risk scan;
- test coverage review;
- security or data hygiene scan;
- UI copy and forbidden-term scan;
- independent module implementation;
- independent test file implementation;
- independent validation after changes.

Read-only and small corrective lanes are usually `Light`. Bounded implementation
lanes are usually `Standard`. Shared contract, runtime, migration, release, or
approval-sensitive lanes are `Heavy` and must protect serial gates.

Parallel validation lanes may run local, fake, dry, fixture, static, or isolated
checks. Real runtime smoke remains a serial controller responsibility unless the
phase explicitly grants one lane exclusive ownership of the runtime environment.

## Serial Gates

These must remain serial unless the project explicitly defines a safer process:

- public contract freeze;
- shared schema or migration changes;
- shared router, navigation, registry, or state table changes;
- real runtime smoke;
- production data or credential use;
- destructive actions;
- release, publish, merge, push, or protected-branch operations;
- final completion report and milestone ledger update;
- active context and document routing maintenance.

## Writable Lane Rules

- Every writable lane must have exclusive allowed files.
- If two lanes need the same file, they are not parallel writable lanes. Merge
  the lanes, make one read-only, or assign the shared file to a serial
  controller lane.
- Shared files require a named integration owner and serial handling.
- A lane may not edit `docs/ACTIVE_CONTEXT.md` or `docs/DOC_ROUTING.md`;
  return proposed changes in `Memory Update Proposal` for controller
  integration.
- A lane may not expand its file boundary.
- A lane may not open approval gates.
- A lane may not stage, commit, push, publish, release, or merge.

## Wave Plan Template

```markdown
Wave Plan:

Wave Readiness:
- dependency DAG:
- parallel candidates:
- serial barriers:
- phase-internal lanes:
- useful parallel lanes:
- exclusive writable files:
- shared files kept serial:
- contracts frozen before writable work:
- runtime ownership:
- validation lanes:
- integration owner:
- conflict stop conditions:
- decision: `SERIAL`, `PARALLEL_WITH_WAVES`, or `STOP_FOR_PM`

Wave 0 - Controller Setup:
- scope:
- phase doc:
- integration owner:

Wave 1 - Parallel Read-Only Lanes:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  permission mode: `READ_ONLY_REVIEW`
  selected capabilities:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  permission mode: `READ_ONLY_REVIEW`
  selected capabilities:

Wave 2 - Serial Freeze:
- contracts frozen:
- shared files:
- writable ownership:

Wave 3 - Parallel Writable Lanes:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  permission mode: `WRITE_AUTHORIZED`
  selected capabilities:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  permission mode: `WRITE_AUTHORIZED`
  selected capabilities:

Wave 4 - Parallel Validation Lanes:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  permission mode: `READ_ONLY_REVIEW`
  selected capabilities:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  permission mode: `READ_ONLY_REVIEW`
  selected capabilities:

Wave 5 - Serial Integration:
- final checks:
- real runtime smoke:
- ledger update:
- memory maintenance:
- handoff:
```

## Completion Evidence

A phase that used waves must report:

- wave readiness decision and missing readiness items, if any;
- wave plan used;
- lanes assigned;
- governance level assigned per lane;
- permission mode assigned per lane;
- writable file ownership;
- conflicts found;
- tests and local, fake, dry, or isolated validation run by lanes;
- real runtime smoke run serially by the controller, when applicable;
- final verification run by the controller;
- active context and document routing maintenance run serially by the
  controller;
- memory update proposals from lanes integrated, compacted, or rejected by the
  controller;
- skipped checks and remaining gaps.

## Lane Status Semantics

- `DONE`: lane objective completed and required lane checks passed.
- `DONE_WITH_CONCERNS`: controller review required before integration; this
  status cannot auto-advance a phase.
- `BLOCKED`: lane cannot proceed; the phase remains blocked or returns to
  planning until the blocker is resolved.
