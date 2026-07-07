# <Milestone Or Feature> Phase <N>: <Name>

Use this template for every milestone phase and future feature slice. Replace
placeholders with concrete content before implementation starts.

## Goal

State the one observable result this phase must produce.

## Governance Level

Select `Light`, `Standard`, or `Heavy` using
`docs/agent/GOVERNANCE_LEVELS.md`.

- Level:
- Why this level:
- Controls Enabled:
- Controls Not Enabled:
- Upgrade triggers:

## Permission Mode

Select the permission mode using
`docs/agent/GOVERNANCE_LEVELS.md#authority-matrix`.

- Mode:
- Why this mode:
- Write/corrective/environment/submit authority:
- Permission upgrade triggers:
- Stop for controller when:

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
- governance level per lane;
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

## Capability Routing

State which specialist skills, plugins, connectors, or tools may be used for
this phase. SPEC-Kit owns scope, authorization, files, gates, locks, evidence,
and completion status; external capabilities provide execution methods inside
that boundary.

Use `docs/agent/CAPABILITY_ADAPTERS.md` for optional providers. Name:

- adapter name;
- provider type;
- authorization level;
- documentation source that must be read before install or init;
- allowed files or read-only scope;
- approval gates;
- evidence expected;
- fallback path.

If superpowers is available, list the specific skills allowed for this phase and
the boundary they must stay inside. If unavailable, use the SPEC-Kit-native
phase, gate, packet, and evidence path.

External planning outputs must be written into or mapped to this phase doc, the
milestone ledger, or the controlling packet.

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
External capability completion is evidence only; it is not phase acceptance or
SPEC-Kit gate completion.

## Completion Report

Fill this after execution.

```markdown
Conclusion:

Governance Level:

Permission Mode:

Controls Enabled:

Controls Not Enabled:

Upgrade Triggers:

Stopped Worker / Controller Decision:

Corrective Closure:

Scope Implemented:

Files Changed:

Contract Evidence:

Capabilities Used:

Capability Adapters:

Adapter Authorization / Fallback:

superpowers Skills Used:

External Capability Evidence:

External Planning Output Mapped To:

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
| `<gate>` | `PASS`, `FAIL`, `BLOCKED`, `WAIVED`, or `N/A` | `<evidence>` | `<yes/no>` | `<owner>` | `<notes>` |

Skipped Checks:

Remaining Gaps:

Handoff:
```
