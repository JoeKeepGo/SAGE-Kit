# Wave Execution

Wave Execution speeds up development by parallelizing safe work across
independent phases or inside a phase while keeping integration, final
verification, approval gates, and submission serial.

For milestone-level Project Manager, Coder, and Final Review controller
handoff, use `docs/agent/SESSION_ORCHESTRATION.md`. Wave Execution remains the
rule for safe parallel phases and phase-internal lanes after admission under
`docs/SAGE_CORE.md#sage-grf-001`.

<a id="sage-grf-002"></a>

## Execution Shape

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

The dependency DAG records real ordering edges whose successors wait for a
predecessor contract, evidence, or gate. A parallel candidate has no unmet
ordering barrier and has isolatable write and resource ownership. A serial
barrier is a concrete dependency, ownership conflict, gate, or runtime
constraint. A phase-internal lane is a bounded phase subdivision with named
objective, ownership, and evidence.

Shared serial ownership does not justify milestone-wide serial execution.
Keep shared files with a named serial integration owner and evaluate the
remaining mutually exclusive files as parallel candidates. Before declaring
`SERIAL`, record the dependency DAG, serial barriers, phase-internal lanes, and
the concrete phase or lane dependency, file conflict, gate, or runtime
ownership reason that prevents safe parallel work.
If a shared file appears in multiple prepared lanes, those lanes must be merged or
reassigned before that file is edited; no active wave may run disjoint
parallel write on the same shared path.

<a id="sage-grf-006"></a>

## Active Shape Changes

Do not repartition an already active phase by default. Adopt a changed wave
shape at the next safe barrier or wave unless active authority explicitly
permits repartitioning. This safe-barrier rule does not authorize runtime or
dynamic Graph rewrite.

## Why Waves Exist

Linear phase execution is safe but slow. Unbounded parallel execution is fast
but risky. Wave Execution keeps the phase as the reviewable unit while allowing
read-only lanes, disjoint writable lanes, and validation lanes to run in
parallel.

## Collapsible Example Shape

Waves are optional and follow the real DAG. A task may use zero waves, one
serial wave, or any bounded number of useful waves. The 0-5 sequence below is
an example for complex work, not a standard or mandatory lifecycle; collapse,
omit, or renumber it freely while preserving actual dependencies and gates.

| Wave | Purpose | Parallelism |
|---|---|---|
| Wave 0 | Controller reads context, confirms scope, and defines file ownership. | Serial |
| Wave 1 | Read-only exploration, risk scan, contract review, and test gap review. | Parallel |
| Wave 2 | Contract, schema, file ownership, and lane plan freeze. | Serial |
| Wave 3 | Disjoint implementation lanes. | Parallel when file ownership does not overlap |
| Wave 4 | Validation, review, targeted tests, and regression checks. | Parallel |
| Wave 5 | Integration, final verification, optional immutable ledger event, and handoff. | Serial |

## Controller Responsibilities

The controller owns:

- coordination of the project-granted phase scope;
- lane governance levels;
- lane permission modes;
- wave plan;
- file ownership table;
- lane prompts or task cards;
- conflict resolution;
- final integration;
- final verification;
- optional immutable milestone ledger event appends;
- active context and document routing updates only for durable changes;
- serial integration of memory update proposals;
- git operations when used.

Light and Standard controllers may execute bounded work directly under the
canonical matrix in `docs/agent/GOVERNANCE_LEVELS.md`. Use waves only when
parallel or independent lanes add concrete execution or evidence value; a
single writable executor normally uses a bounded serial loop.

## Wave Readiness Gate

Before starting multiple waves, the controller must show that wave execution
is useful and safe.

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

<a id="sage-grf-005"></a>

### Affected Serialization

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
lanes are usually `Standard`. Use `Heavy` only for a concrete high-risk trigger
from the canonical matrix; delegation or a shared toolchain alone is not one.

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
- final completion reference and optional immutable ledger event append;
- active context and document routing updates only for durable changes.

## Writable Lane Rules

- Every writable lane must have exclusive allowed files.
- If two lanes need the same file, they are not parallel writable lanes. Merge
  the lanes, make one read-only, or assign the shared file to a serial
  controller lane.
- Shared files require a named integration owner and serial handling.
- A lane may not edit the project-selected current-truth authority path or
  routing authority unless explicitly named as their writer. Return a bounded
  proposal only when durable truth or routing actually changed; otherwise omit
  memory maintenance.
- A lane may not expand its file boundary.
- A lane may not open approval gates.
- A lane may commit locally only in an isolated worktree when explicitly
  authorized. Staging/committing shared integration state, push, publish,
  release, and merge remain controller-serialized.

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

Actual waves (zero, one, or many according to the DAG):
- wave: `<id/name>`
  purpose: `<dependency/evidence/integration value>`
  mode: `<serial/parallel>`
  lanes: `<actual lanes only>`
  governance/permission: `<per lane>`
  ownership and checks: `<paths/resources/evidence>`
  barrier or successor: `<actual edge/gate/none>`

Current-truth update: `<reference only when durable truth changed; otherwise omit>`
```

## Completion Evidence

A phase that used waves reports only the waves and lanes actually used:

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
- project-selected current-truth or routing updates only when durable facts or
  routing changed;
- skipped checks and remaining gaps.

<a id="sage-grf-011"></a>

## Lane Status Semantics

- `DONE`: lane objective completed and required lane checks passed.
- `DONE_WITH_CONCERNS`: controller review required before integration; this
  status cannot auto-advance a phase or acceptance.
- `HANDOFF`: nonterminal transfer of unfinished review, approval, integration,
  or next-action responsibility to a named owner.
- `BLOCKED`: lane cannot proceed; the phase remains blocked or returns to
  planning until the blocker is resolved.
