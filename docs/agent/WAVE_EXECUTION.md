# Wave Execution

Wave Execution speeds up development by parallelizing safe work inside a phase
while keeping integration, verification, approval gates, and submission serial.

For milestone-level Project Manager, Coder, and Final Review controller
handoff, use `docs/agent/SESSION_ORCHESTRATION.md`. Wave Execution remains the
rule for safe parallel lanes inside a phase.

The rule is:

```text
phase stays linear
waves run in parallel where safe
gates stay serial
governance level is assigned per lane
```

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

Wave 0 - Controller Setup:
- scope:
- phase doc:
- integration owner:

Wave 1 - Parallel Read-Only Lanes:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  selected capabilities:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  selected capabilities:

Wave 2 - Serial Freeze:
- contracts frozen:
- shared files:
- writable ownership:

Wave 3 - Parallel Writable Lanes:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  selected capabilities:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  selected capabilities:

Wave 4 - Parallel Validation Lanes:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
  selected capabilities:
- lane: `<name>`
  governance level: `Light, Standard, or Heavy`
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

- wave plan used;
- lanes assigned;
- governance level assigned per lane;
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
