# <Milestone Or Feature> Phase <N>: <Name>

Use this template for every milestone phase and future feature slice. Replace
placeholders with concrete content before implementation starts.

## Goal

State the one observable result this phase must produce.

## Requirement IDs

List product, architecture, API, security, UI, data, runtime, or local feature
IDs.

## Inputs

List prior phase outputs, contracts, docs, commands, runtime services, and known
constraints needed for this phase.

## Outputs

List exact artifacts this phase will produce: source files, tests, docs,
contracts, smoke evidence, or handoff notes.

## Non-Goals

List work explicitly excluded from this phase.

## File Boundary

List expected files to create or modify and each file's responsibility.

Also list:

- allowed read-only files;
- forbidden files;
- shared files requiring exclusive ownership.

## Module Ownership

State which module, page, runtime component, data boundary, or integration this
phase owns.

## Wave Plan

State whether this phase uses Wave Execution.

If yes, list:

- controller or integration owner;
- read-only lanes;
- writable lanes and exclusive allowed files;
- validation lanes;
- shared files requiring serial ownership;
- gates that must remain serial.

If no, state why parallel execution is not useful or not safe.

## Public Contract

Define request, response, event, config, UI, CLI, or data contract. Include:

- owner;
- consumer;
- success shape;
- error shape;
- security boundary.

## Test Plan

Name exact test commands and focused cases.

If behavior changes and no test path exists, adding the test path is part of the
phase unless the phase is explicitly investigation-only.

## Runtime Smoke

Name exact runtime checks required for this phase, including process, API,
browser, worker, database, CLI, or service checks when applicable.

## Edge And Adversarial Cases

List empty input, malformed data, unavailable upstreams, auth/config failures,
timeouts, partial failures, concurrency, and security exposure cases relevant to
the phase.

## Change Control Evidence

```text
Change Control Evidence:
- path:
- branch or change record:
- base or baseline:
- current revision:
- dirty files before work:
```

## Task Dispatch Evidence

Use only when Task Dispatch Profile is active for this phase.

```text
Task Dispatch Evidence:
- task record:
- evidence record:
- required L0-L4 levels:
- resource locks:
- validator command:
- validator result:
```

## Completion Gate

List exact evidence required before this phase can be called complete.

## Completion Report

Fill this after execution.

```markdown
Conclusion:

Scope Implemented:

Files Changed:

Contract Evidence:

Wave / Lane Evidence:

Tests Run:

Runtime Smoke:

Approval Gates:

Security / Data Hygiene:

Memory Maintenance:

Change Control Status:

Task Dispatch Status:

Gate Status:

| Gate | Status | Evidence | Blocking | Owner | Notes |
|---|---|---|---|---|---|
| `<gate>` | `PASS | FAIL | BLOCKED | WAIVED | N/A` | `<evidence>` | `<yes/no>` | `<owner>` | `<notes>` |

Skipped Checks:

Remaining Gaps:

Handoff:
```
