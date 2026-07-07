# Session Orchestration

Session Orchestration is the optional milestone-level execution mode for large
SPEC-Kit work.

It reduces manual copy/paste by separating long-running control from temporary
execution and review controllers. It does not replace Phase Execution or Wave
Execution. It wraps multiple phase executions inside a milestone-level packet
flow.

Use this mode when a milestone has multiple phases, multiple lanes, independent
review needs, or repeated handoff overhead.

Do not use this mode for small tasks, typo fixes, narrow bug fixes, or a single
phase that can be completed cleanly in one controller session.

## Role Model

| Role | Lifetime | Responsibility | Must Not Do |
|---|---|---|---|
| Project Manager Controller | Long-running project session | Project direction, milestone boundary, execution packet, structural gate, final decision. | Perform full technical review or rewrite Coder results. |
| Coder Controller | One milestone | Orchestrate phase workers and lane workers, collect evidence, produce milestone result packet. | Redefine milestone scope, open approval gates, accept the milestone. |
| Final Review Controller | One milestone | Orchestrate review workers, validation lanes, re-review, and final verdict. | Trust Coder self-report without verification or accept the milestone directly. |
| Phase Worker | One phase | Execute one phase under the phase boundary. | Expand scope or modify unrelated files. |
| Lane Worker | One lane | Execute one read-only, writable, or validation lane. | Edit shared files or controller-owned startup docs. |
| Review Worker | One review slice | Verify phase, lane, contract, evidence, or risk area. | Change implementation unless assigned a corrective lane. |
| Corrective Worker | One bounded fix | Fix only findings named in a corrective packet. | Redesign, expand scope, or fix unassigned issues. |

## Standard Flow

```text
Project Manager Controller
  -> Milestone Execution Packet

Coder Controller
  -> phase workers and lane workers
  -> Milestone Result Packet

Project Manager Controller
  -> Structural Gate only

Final Review Controller
  -> review workers, validation lanes, corrective packets
  -> Final Review Packet

Coder Controller or Corrective Worker
  -> bounded corrections when requested

Final Review Controller
  -> re-review

Project Manager Controller
  -> accept, handoff, blocked, or next prompt
```

## Controller Rules

- The Project Manager Controller owns direction, scope, gates, and final
  decision.
- The Coder Controller owns execution orchestration, not product judgment.
- The Final Review Controller owns independent verification, not final project
  acceptance.
- Coder and Final Review controllers should delegate work to phase, lane,
  review, validation, or corrective workers when doing so reduces serial
  handoff and file ownership remains clear.
- Controllers may run workers in parallel only when the execution packet names
  disjoint file ownership, runtime ownership, evidence expectations, and stop
  conditions.
- Controllers integrate worker outputs, resolve conflicts, and produce the
  packet for the next controller. Workers do not hand off directly to the next
  controller unless the packet says so.
- Coder Controller must perform a self review before returning the result
  packet. This is execution-side integration review, not final acceptance.
- Coder and Final Review controllers must reassess whether phases or lanes can
  run in parallel, must stay serial, or must stop for Project Manager decision.
- One milestone should normally use one Coder Controller and one Final Review
  Controller.
- Additional controllers are exceptional and must be justified by scope,
  context contamination, specialized review, or independent runtime ownership.

## Capability Routing

Before creating worker prompts, Coder and Final Review controllers must inspect
the available skill, plugin, connector, and tool metadata exposed by the
runtime.

They must route workers to specialist capabilities when relevant, such as code
review, frontend testing, browser automation, GitHub, database, document, PDF,
or runtime-specific tools.

Do not load every capability body by default. Read only the selected capability
instructions needed for the worker's task.

Each worker prompt or packet must name:

- selected skills, plugins, connectors, or tools;
- capabilities the worker should check for in its own runtime;
- unavailable capabilities and fallback;
- SPEC-Kit docs and packets that still govern scope, files, gates, and
  evidence.

SPEC-Kit remains the governance harness. Specialist capabilities perform the
domain work.

## Coder Self Review

Before returning the Milestone Result Packet, Coder Controller must perform an
integration self review:

- check every phase and lane result for status, files, tests, smoke, blockers,
  and evidence;
- verify worker outputs stayed inside allowed files and non-goals;
- identify missing tests, skipped checks, runtime gaps, and contract risks;
- run bounded corrective workers for issues inside the execution packet;
- stop and return `HANDOFF` or `BLOCKED` when correction needs new scope,
  approval, public contract change, or shared ownership change.

Coder self review does not replace Final Review.

## Parallelism Assessment

Coder and Final Review controllers both assess execution shape:

- `SERIAL`: phase or lane order matters, shared files overlap, or gates are
  unresolved;
- `PARALLEL_WITH_WAVES`: lanes are independent inside a phase and serial gates
  remain protected;
- `PARALLEL_PHASES`: phases have disjoint ownership, frozen contracts, and no
  shared runtime or approval dependency;
- `STOP_FOR_PM`: parallelism or sequencing changes milestone scope, gates, or
  decision ownership.

Coder uses this assessment to choose worker execution. Final Review uses it to
verify whether the chosen execution shape was safe.

## Project Manager Structural Gate

The Project Manager Controller does not perform technical verification between
Coder and Final Review.

It checks only whether the Coder packet is structurally ready for review:

- every phase has a status;
- files changed are listed;
- contracts and ownership are named;
- tests and runtime smoke are reported or marked not applicable;
- skipped checks and blockers have reasons;
- approval gates are not silently opened;
- active context, document routing, ledger, and closeout notes are present;
- stop conditions are surfaced.

If the packet is incomplete, return it to the Coder Controller for packet repair
only. Do not send an incomplete packet to Final Review.

## Final Review Rules

Final Review must verify independently. It may use the Coder packet as an index,
but it must read the routed phase docs, changed files, evidence, tests, or
contracts needed to support the verdict.

Final Review returns one of:

- `ACCEPTABLE`
- `ACCEPTABLE_WITH_CONCERNS`
- `NEEDS_CORRECTION`
- `BLOCKED`

Final Review cannot mark the milestone accepted. The Project Manager Controller
makes the final decision.

## Corrective Rules

Corrective work is bounded by the Final Review findings.

- A corrective packet must name exact findings, allowed files, forbidden files,
  commands, and stop conditions.
- Coder may dispatch corrective workers for self-review findings only when the
  fix is inside the original execution packet.
- Final Review may request correction only through a corrective packet or by
  returning `BLOCKED` / `NEEDS_CORRECTION`.
- Corrective workers must not redesign the feature.
- Corrective workers must not expand milestone scope.
- Corrective workers must not open approval gates.
- Default maximum corrective rounds: 2.
- After the maximum rounds, return `HANDOFF` or `BLOCKED` to Project Manager.

## Serial Gates

These remain serial even in Session Orchestration:

- milestone boundary changes;
- public contract freeze;
- shared file ownership changes;
- approval gates;
- real runtime smoke unless exclusive runtime ownership is granted;
- final integration;
- active context and routing maintenance;
- milestone ledger update;
- milestone closeout;
- git commit, push, release, publish, merge, or destructive operations.

## Required Packets

- Use `docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md` from Project
  Manager to Coder.
- Use `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md` from Coder to Project
  Manager and Final Review.
- Use `docs/templates/STRUCTURAL_GATE_TEMPLATE.md` for Project Manager packet
  completeness checks.
- Use `docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md` from Final Review to
  Project Manager.
- Use `docs/templates/CORRECTIVE_PACKET_TEMPLATE.md` for bounded corrective
  work.

## Completion

A milestone run using Session Orchestration is not complete until:

- Coder packet is structurally complete;
- Final Review returns a verdict;
- corrective rounds are complete or explicitly stopped;
- Project Manager records the final decision;
- milestone ledger is current;
- active context and routing maintenance are handled;
- closeout is written when the milestone closes.
