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

Session Orchestration is normally Heavy at the controller layer. Delegated
phase, lane, review, validation, and corrective workers must still receive
their own `Light`, `Standard`, or `Heavy` governance level based on their local
scope and risk.

## Role Model

| Role | Lifetime | Responsibility | Must Not Do |
|---|---|---|---|
| Project Manager Controller | Long-running project session | Project direction, milestone boundary, execution packet, structural gate, final decision. | Perform full technical review or rewrite Coder results. |
| Coder Controller | One milestone | Orchestrate phase workers and lane workers, collect evidence, produce milestone result packet. | Redefine milestone scope, open approval gates, accept the milestone, or self-execute the whole milestone. |
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
  -> phase workers and lane workers, or bounded self-execution only when allowed
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
- Coder Controller self-execution is exceptional. It is allowed only under
  `Coder Self-Execution Policy` below and must be recorded in the result packet.
- Controllers must assign each worker a governance level. Heavy milestone
  control does not automatically make every worker Heavy.
- Controllers may run workers in parallel only when the execution packet names
  disjoint file ownership, runtime ownership, evidence expectations, and stop
  conditions.
- Controllers integrate worker outputs, resolve conflicts, and produce the
  packet for the next controller. Workers do not hand off directly to the next
  controller unless the packet says so.
- `docs/ACTIVE_CONTEXT.md` and `docs/DOC_ROUTING.md` are controller-owned
  serial files. Phase, lane, review, and corrective workers return memory
  update proposals instead of editing those files directly.
- Coder Controller must perform a self review before returning the result
  packet. This is execution-side integration review, not final acceptance.
- When Task Dispatch Profile is active, Coder must keep task/evidence records
  current and include validator results in the milestone result packet.
- Coder and Final Review controllers must reassess whether phases or lanes can
  run in parallel, must stay serial, or must stop for Project Manager decision.
- Heavy controller mode does not imply parallelism and does not permit the
  Coder Controller to implement all phases directly.
- Coder may decide where to use worktrees only when the Project Manager
  execution packet authorizes Worktree Isolation.
- Final Review verifies worktree use and may recommend submit or cleanup, but
  must not commit, push, merge, or delete worktrees while acting as Final
  Review.
- When Task Dispatch Profile is active, Final Review must inspect the relevant
  task/evidence records, run or review the validator result, and use the
  records as an evidence index rather than as proof by themselves.
- If the same session is later used for submit or cleanup, Project Manager must
  first record the Final Review verdict, then issue a separate Submit
  Controller authorization.
- One milestone should normally use one Coder Controller and one Final Review
  Controller.
- Additional controllers are exceptional and must be justified by scope,
  context contamination, specialized review, or independent runtime ownership.

## Permission Mode Assignment

Use `docs/agent/GOVERNANCE_LEVELS.md#authority-matrix` before issuing a packet
or worker prompt.

Project Manager must select both:

- governance level: `Light`, `Standard`, or `Heavy`;
- permission mode: `READ_ONLY_REVIEW`, `WRITE_AUTHORIZED`,
  `CORRECTIVE_AUTHORIZED`, `ENVIRONMENT_WRITE_AUTHORIZED`, or
  `SUBMIT_AUTHORIZED`.

Governance level does not grant write authority by itself. Permission mode does
not reduce the governance level. A Heavy controller may start in
`READ_ONLY_REVIEW`, but it must still perform Heavy controller duties such as
scope decision, packet completeness, corrective routing, final decision, or
handoff when those duties are in scope.

Every worker or lane packet must name its permission mode. Default to
`READ_ONLY_REVIEW` unless the active packet explicitly authorizes writes,
corrective work, environment mutation, or submit/cleanup authority.

When a read-only review finds gate-affecting issues, milestone blockers, or
required corrections, read-only status does not close the run. The reviewer
must return a corrective packet, a Project Manager decision request, an
explicit blocker, or a recorded no-correction rationale.

## Capability Routing

Before creating worker prompts, Coder and Final Review controllers must inspect
the available skill, plugin, connector, MCP tool, CI, and review metadata
exposed by the runtime.

Use `docs/agent/CAPABILITY_ADAPTERS.md` for optional external providers,
unavailable capability fallback, installation, hooks, MCP config, frontend or
browser adapter evidence, and environment-write boundaries.

They must route workers to specialist capabilities when relevant, such as code
review, frontend testing, browser automation, GitHub, database, document, PDF,
or runtime-specific tools.

Do not load every capability body by default. Read only the selected capability
instructions needed for the worker's task.

Each worker prompt or packet must name:

- selected skills, plugins, connectors, MCP tools, CI, or reviewers;
- selected capability adapter type and authorization level when applicable;
- capabilities the worker should check for in its own runtime;
- unavailable capabilities and fallback;
- SPEC-Kit docs and packets that still govern scope, files, gates, and
  evidence.

SPEC-Kit remains the governance harness. Specialist capabilities perform the
domain work under `docs/SPEC_CORE.md#external-capability-boundary`.

External planning outputs must be written into or mapped to the milestone
execution packet, phase docs, lane packets, or corrective packets. External
execution may continue only inside the approved packet boundary and must stop
for closed gates, scope expansion, shared-file or resource-lock conflicts,
failed required evidence, unapproved runtime, destructive, submit, merge, push,
or cleanup operations, or higher controller decisions.

Superpowers is a reference integration for execution discipline when available.
It does not change Project Manager, Coder, Final Review, or Submit Controller
authority.

## Coder Self-Execution Policy

Coder Controller should normally orchestrate workers instead of acting as the
main implementation worker.

Coder Controller may self-execute only when every condition is true:

- the work is one narrow phase, one integration glue step, or one bounded
  corrective fix;
- allowed files, read-only files, forbidden files, tests, smoke, and stop
  conditions are already explicit in the execution packet or phase doc;
- no safe parallelism is available or worker dispatch would add more handoff
  overhead than risk reduction;
- no shared contract, migration, lockfile, generated artifact, runtime
  ownership, approval gate, or cross-component integration decision is being
  invented during execution;
- the Coder can still return a complete Milestone Result Packet and submit to
  independent Final Review.

Coder Controller must not self-execute when:

- the milestone contains multiple implementation phases;
- writable work spans unrelated modules or user workflows;
- file ownership is unclear or shared;
- the work would benefit from read-only review, validation, frontend,
  database, security, or runtime specialist lanes;
- the controller would be both primary implementer and only verifier;
- the execution packet expects phase, lane, or task-dispatch workers.

If Coder self-executes, the result packet must record:

- why self-execution was allowed;
- which worker dispatch was skipped and why;
- exact files changed;
- checks and smoke run;
- remaining independent review required.

Self-execution does not reduce Final Review responsibility. Final Review should
treat self-executed work as higher review risk because separation between
orchestration and implementation was reduced.

## Wave Readiness Gate

Before using `PARALLEL_WITH_WAVES` or `PARALLEL_PHASES`, Coder Controller must
prove wave readiness.

A wave is ready only when the execution packet or phase doc names:

- independent lane objectives;
- exclusive writable files per lane;
- shared files that remain serial;
- public contracts frozen before writable lanes;
- runtime, database, queue, browser, device, or service ownership;
- validation lanes and evidence expected;
- integration owner;
- stop conditions for conflicts.

If any item is missing, keep execution `SERIAL` or return `STOP_FOR_PM`. Do not
create a cosmetic wave plan where the Coder Controller still performs all
implementation work directly.

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

## Governance Level Assignment

Use `docs/agent/GOVERNANCE_LEVELS.md` before dispatching workers.

Default controller level:

- Project Manager milestone controller: `Heavy`.
- Coder Controller for a whole milestone: `Heavy`.
- Final Review Controller for a whole milestone: `Heavy`.

Default worker level:

- informational-only read-only review, scan, or small corrective lane: `Light`;
- bounded phase or module implementation: `Standard`;
- integration, shared contract, state, release, or approval-sensitive lane:
  `Heavy`.

Workers must stop for controller decision when they discover a higher-level
trigger that was not in their packet.

## Worktree Isolation

Use `docs/agent/WORKTREE_ISOLATION.md` when a milestone, phase, lane, or review
needs an isolated workspace.

Project Manager decides whether Worktree Isolation is allowed and sets:

- isolation mode;
- maximum worktree count;
- branch and worktree naming;
- base branch or base commit;
- allowed phases or lanes;
- shared files that remain serial;
- runtime ownership;
- integration owner;
- submit authority;
- cleanup policy.

Coder Controller decides which authorized phases or lanes actually receive
worktrees and records the worktree map in the result packet.

Final Review checks whether the worktree use was authorized, isolated, and
integrated correctly. Final Review returns submit and cleanup recommendations.

Project Manager or a separately authorized Submit Controller makes the final
commit, push, merge, and cleanup decision.

## Task Dispatch

Use `docs/profiles/task-dispatch/DISPATCH_PROFILE.md` when a milestone needs
structured task records, evidence records, resource locks, Run/Attempt/Lease
tracking, and validator-backed closeout.

Project Manager decides whether Task Dispatch Profile is active and sets:

- dispatch board path;
- task record root;
- evidence record root;
- required L0-L4 levels;
- resource lock policy;
- Run/Attempt/Lease policy;
- validator command;
- the gate where validator success is required;
- task and evidence update owners.

Coder Controller updates the task and evidence records while integrating worker
results. Final Review independently checks the records, validator output, and
underlying evidence needed for the verdict.

Default validator success means the records are structurally ready for review.
Gate-ready validator success means the records also claim verified status,
passlike required levels, and no blockers. Neither mode accepts the milestone
or replaces Final Review judgment.

## Project Manager Structural Gate

The Project Manager Controller does not perform technical verification between
Coder and Final Review.

It checks only whether the Coder packet is structurally ready for review:

- every phase has a status;
- primary capability and capability-map reference are present or marked not
  applicable;
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

Final Review must classify findings before returning a non-acceptable verdict:

- `AUTO_CORRECTIVE`: fixable inside the active boundary and allowed files;
- `PM_DECISION`: needs scope, acceptance, waiver, gate, sequencing, or product
  judgment;
- `BLOCKED`: cannot proceed because evidence, environment, dependency, runtime,
  or authority is missing;
- `DEFER`: can be postponed only with an explicit owner, waiver, or follow-up
  milestone.

If Final Review is in `READ_ONLY_REVIEW`, it must not edit files or dispatch a
fixing worker, but `NEEDS_CORRECTION` must include an inline or referenced
corrective packet, Project Manager decision request, or blocker. If Final
Review is in `CORRECTIVE_AUTHORIZED` and findings are `AUTO_CORRECTIVE`, it
should open a corrective round up to the configured round limit.

Final Review cannot mark the milestone accepted. The Project Manager Controller
makes the final decision.

## Corrective Rules

Corrective work is bounded by the Final Review findings.

- A corrective packet must name exact findings, allowed files, forbidden files,
  commands, and stop conditions.
- A corrective packet must name the permission mode and whether the round was
  packet-only, auto-opened, or waiting for Project Manager decision.
- Coder may dispatch corrective workers for self-review findings only when the
  fix is inside the original execution packet.
- Final Review may request correction only through a corrective packet,
  Project Manager decision request, or by returning `BLOCKED` with the blocking
  authority/evidence gap named.
- `Corrective Packet Required: yes` without a packet, handoff target, or blocker
  is incomplete.
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
- branch base changes;
- schema, migration, lockfile, and generated artifact changes;
- task-dispatch validator gate;
- real runtime smoke unless exclusive runtime ownership is granted;
- final integration;
- active context and routing maintenance, including worker memory update
  proposal integration;
- milestone ledger update;
- milestone closeout;
- git commit, push, release, publish, merge, or destructive operations;
- worktree cleanup.

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
- task-dispatch records and validator result are current when the profile is
  active;
- active context and routing maintenance are handled;
- closeout is written when the milestone closes.
