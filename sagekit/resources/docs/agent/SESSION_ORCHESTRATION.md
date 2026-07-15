# Session Orchestration

Session Orchestration is the optional milestone-level execution mode for large
SAGE-Kit work.

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
| Project Manager Controller | Long-running project session | Project direction, milestone boundary, execution issuance, structural gate, and owner-authorized final decision. | Perform full technical review, rewrite Coder results, waive a human-only gate, or invent owner waiver authority. |
| Coder Controller | One milestone | Orchestrate workers, synthesize results, perform preliminary integration review, and produce the milestone result packet. | Edit worker-owned implementation files, redefine scope, open approval gates, accept, submit, or clean up the milestone. |
| Workspace/Environment Controller | Bounded setup | Create an authorized review worktree before review handoff and report its map. | Review, correct, submit, or create unapproved worktrees. |
| Final Review Controller | One milestone | Remain read-only while inspecting directly and orchestrating useful review, validation, authorized corrective, and re-review lanes into a final verdict. | Edit implementation or corrective files, create its review worktree, trust self-report, or accept the milestone. |
| Phase Worker | One phase | Execute one phase under the phase boundary. | Expand scope or modify unrelated files. |
| Lane Worker | One lane | Execute one read-only, writable, or validation lane. | Edit shared files or controller-owned startup docs. |
| Review Worker | One review slice | Verify phase, lane, contract, evidence, or risk area. | Change implementation unless assigned a corrective lane. |
| Corrective Worker | One bounded fix | Fix only findings named in a corrective packet and return evidence. | Redesign, expand scope, fix unassigned issues, author/broaden a closure predicate, or record a closure receipt. |

## Standard Flow

```text
Project Manager Controller
  -> Milestone Execution Packet

Coder Controller
  -> phase workers and lane workers
  -> controller-level synthesis and preliminary integration review
  -> Milestone Result Packet to Project Manager Controller

Project Manager Controller
  -> Structural Gate only
  -> has Coder or named Workspace/Environment Controller create any authorized review worktree
  -> forwards to Final Review only on Structural Gate PASS

Final Review Controller
  -> review workers and validation lanes
  -> corrective packets and workers only when orchestration is authorized
  -> Final Review Packet

Corrective Worker
  -> bounded corrections and evidence when requested

Original Final Review Controller or named review packet author
  -> independent re-review, or deterministic receipt verification with no new review invocation
  -> mechanical verdict finalization when precommitted receipt conditions pass

Project Manager Controller
  -> owner-authorized accept, concern waiver, defer, abandon, or blocked-closure decision
  -> closeout
  -> optional separate post-verdict submit grant
```

## Controller Rules

- The Project Manager Controller owns direction, scope, gates, and final
  decision.
- The Coder Controller owns execution orchestration, not product judgment.
- The Final Review Controller owns independent verification, not final project
  acceptance.
- Orchestration authority does not grant worker write authority. Final Review
  remains `READ_ONLY_REVIEW`; when Project Manager authorizes corrective
  orchestration, each corrective worker receives its own
  `CORRECTIVE_AUTHORIZED` packet.
- Coder and Final Review controllers should delegate work to phase, lane,
  review, validation, or corrective workers when doing so reduces serial
  handoff and file ownership remains clear.
- Coder Controller may edit only explicitly controller-owned integration or
  packet files under the narrow policy below. It never edits files assigned to
  a phase, lane, integration, or corrective worker.
- Controllers must assign each worker a governance level. Heavy milestone
  control does not automatically make every worker Heavy.
- Controllers may run workers in parallel only when the execution packet names
  disjoint file ownership, runtime ownership, evidence expectations, and stop
  conditions.
- Controllers integrate worker outputs, resolve conflicts, and produce the
  packet for the next controller. Workers do not hand off directly to the next
  controller unless the packet says so.
- Each run names one Startup Context Controller that exclusively owns
  `docs/ACTIVE_CONTEXT.md` and `docs/DOC_ROUTING.md`. Workers and integration
  lanes return proposals; they never race or directly apply startup-context
  changes.
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
- The initial Coder execution packet never grants submit, commit, push, merge,
  release, publish, or cleanup authority.
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

`SUBMIT_AUTHORIZED` is valid only in a distinct post-verdict grant. It is not a
valid initial Coder execution mode. Final Review always uses
`READ_ONLY_REVIEW`; corrective orchestration authorization is recorded
separately and grants writes only to named corrective workers.

Governance level does not grant write authority by itself. Permission mode does
not reduce the governance level. A Heavy controller may start in
`READ_ONLY_REVIEW`, but it must still perform Heavy controller duties such as
scope decision, packet completeness, corrective routing, or handoff when those
duties are in scope. Project Manager final decisions are recorded as separate
PM decision authority and are not Final Review read-only acceptance.

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
- SAGE-Kit docs and packets that still govern scope, files, gates, and
  evidence.

SAGE-Kit remains the governance harness. Specialist capabilities perform the
domain work under `docs/SAGE_CORE.md#external-capability-boundary`.

External planning outputs must be written into or mapped to the milestone
execution packet, phase docs, lane packets, or corrective packets. External
execution may continue only inside the approved packet boundary and must stop
for closed gates, scope expansion, shared-file or resource-lock conflicts,
failed required evidence, unapproved runtime, destructive, submit, merge, push,
or cleanup operations, or higher controller decisions.

Superpowers is a reference integration for execution discipline when available.
It does not change Project Manager, Coder, Final Review, or Submit Controller
authority.

## Coder Controller Integration Edit Policy

Coder Controller should normally orchestrate workers instead of acting as the
main implementation worker.

Coder Controller may directly edit only when every condition is true:

- the work is one narrow controller-owned integration glue step or packet
  repair before Final Review;
- allowed files, read-only files, forbidden files, tests, smoke, and stop
  conditions are already explicit in the execution packet or phase doc;
- no safe parallelism is available or worker dispatch would add more handoff
  overhead than risk reduction;
- no shared contract, migration, lockfile, generated artifact, runtime
  ownership, approval gate, or cross-component integration decision is being
  invented during execution;
- the Coder can still return a complete Milestone Result Packet for independent
  Final Review.
- no implementation file is owned by a phase, lane, integration, or corrective
  worker.

Coder Controller must not directly edit when:

- the milestone contains multiple implementation phases;
- writable work spans unrelated modules or user workflows;
- file ownership is unclear or shared;
- the work would benefit from read-only review, validation, frontend,
  database, security, or runtime specialist lanes;
- the controller would be both primary implementer and only verifier;
- the execution packet expects phase, lane, or task-dispatch workers.
- any writable file is worker-owned.

If Coder directly edits controller-owned files, the result packet must record:

- why direct controller integration was allowed;
- which worker dispatch was skipped and why;
- exact files changed;
- checks and smoke run;
- remaining independent review required.

Direct controller edits do not reduce Final Review responsibility.

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
- run bounded integration repair workers under `WRITE_AUTHORIZED` for issues
  inside the execution packet;
- stop and return `HANDOFF` or `BLOCKED` when correction needs new scope,
  approval, public contract change, or shared ownership change.

Coder self review does not replace Final Review. Fixes made before the Coder
packet reaches Final Review are integration repairs, not corrective rounds.

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
- post-verdict submit owner;
- post-verdict cleanup policy.

Coder Controller decides which authorized phases or lanes actually receive
worktrees and records the worktree map in the result packet.

When `REVIEW_WORKTREE` is authorized, Project Manager must name Coder or a
Workspace/Environment Controller to create it before handoff to Final Review.
Final Review receives the path and base reference; it does not create or mutate
the worktree setup.

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

When Task Dispatch Profile is active, task, phase, or milestone acceptance gates
require gate-ready validator success. `n/a` is valid only when the named task is
explicitly recorded as not an acceptance gate.

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

Final Review must produce independent verification. It may inspect and verify
directly in read-only mode when delegation is unavailable or unnecessary, and
should delegate independent review slices or validation lanes where useful,
then synthesize all evidence. Corrective file changes are always delegated to a
separately authorized worker.

Final Review returns one of:

- `ACCEPTABLE`
- `ACCEPTABLE_WITH_CONCERNS`
- `NEEDS_CORRECTION`
- `BLOCKED`

Severity affects acceptance, not review discipline:

- Open `P0` and `P1` findings always block Project Manager acceptance. They
  may close only after the issue is fixed or explicitly reclassified with
  evidence by the required authority.
- `P2` findings block acceptance only for authority, false-green risk, an
  approval or security boundary, validator failure, source-authority risk, or
  evidence-integrity risk.
- Ordinary `P2` findings may close as
  `ACCEPTABLE_WITH_CONCERNS` or be auto-corrected when they do not affect the
  blocking boundary above.
- `P3` findings do not block acceptance. Record them as concerns, follow-up, or
  cleanup candidates.

Final Review must classify findings before returning a non-acceptable verdict:

- `AUTO_CORRECTIVE`: fixable inside the active boundary and allowed files;
- `PM_DECISION`: needs scope, acceptance, waiver, gate, sequencing, or product
  judgment;
- `BLOCKED`: cannot proceed because evidence, environment, dependency, runtime,
  or authority is missing;
- `DEFER`: can be postponed only with an explicit owner, waiver, or follow-up
  milestone.

Final Review is always `READ_ONLY_REVIEW` and never edits implementation or
corrective files. A `NEEDS_CORRECTION` verdict must include an inline or
referenced corrective packet, Project Manager decision request, or blocker. If
Project Manager separately authorized corrective orchestration, Final Review
may dispatch a `CORRECTIVE_AUTHORIZED` worker inside the approved boundary and
convergence budget; otherwise it returns `PM_DECISION_REQUIRED` and `HANDOFF`.

Final Review cannot mark the milestone accepted. The Project Manager Controller
makes the final decision through a separate PM decision authority record.

Each ordinary finding must name its Finding Owner and Waiver Authority. Project
Manager may record its waiver only with an explicit decision reference from the
Waiver Authority or a documented delegation reference. Finding ownership alone
does not grant waiver authority. A closed human-only approval gate requires its
named human authority; Project Manager alone cannot waive or open it.

## Corrective Rules

Corrective work is bounded by the Final Review findings.

- A corrective packet must name exact findings, allowed files, forbidden files,
  round, commands, stop conditions, changed-file return fields, and re-review
  owner/status.
- A corrective packet must name worker permission mode and whether Final Review
  corrective orchestration is authorized or waiting for Project Manager.
- Coder may dispatch integration repair workers for self-review findings only
  when the fix is inside the original execution packet. Do not call this a
  corrective round before Final Review.
- Final Review may request correction only through a corrective packet,
  Project Manager decision request, or by returning `BLOCKED` with the blocking
  authority/evidence gap named.
- `Corrective Packet Required: yes` without a packet, handoff target, or blocker
  is incomplete.
- Every corrective round that changes behavior, contracts, runtime behavior,
  authority, gate decisions, shared ownership, or required evidence must
  produce independent re-review evidence before Final Review can close the
  verdict. File changes also require re-review unless they qualify for the
  strict Deterministic Closure exception below and complete both receipt and
  verdict-finalization records.
- Corrective worker `DONE` means fix execution is complete. It does not close a
  finding, review verdict, gate, or milestone. A separately recorded re-review
  result or valid Deterministic Closure receipt closes the finding.
- Outside strict Deterministic Closure, Final Review may directly perform a
  narrow read-only diff inspection or delegate one narrow re-review for
  low-risk, local corrections. It must rerun affected review workers, review subagents, or
  validation lanes when the original review used them, the fix touches behavior,
  contracts, runtime, shared files, or gates, or the regression surface is
  unclear.
- When the corrective change only updates ledger, evidence, status, closeout,
  or other review bookkeeping without changing product semantics, permissions,
  source authority, information architecture, contracts, runtime behavior, or
  validator requirements, use strict Deterministic Closure when all of its
  conditions are pre-authored and satisfied; otherwise Final Review should run
  only the targeted status/evidence lanes named by the project review plan.
- When the corrective change alters semantics, permission or authority
  boundaries, source authority, information architecture, public contracts,
  security posture, runtime behavior, validator meaning, or approval gates,
  Final Review must rerun the full affected review lanes.
- Corrective workers must not redesign the feature.
- Corrective workers must not expand milestone scope.
- Corrective workers must not open approval gates.
- Corrective packets may name a maximum round or convergence budget, but the
  budget is a control signal rather than an unconditional blocker.
- Material convergence progress means the open finding count or finding
  severity is decreasing, scope does not expand, no blocking gate is bypassed,
  and no new authority, false-green, approval-boundary, security-boundary,
  validator-failure, source-authority, or evidence-integrity risk appears.
  Continue automatically only while that definition is satisfied inside an
  authorized corrective packet or boundary.
- At the first same-root round with no material progress, stop automatic
  continuation, keep the verdict `NEEDS_CORRECTION`, and return
  `PM_DECISION_REQUIRED` plus `HANDOFF`.
- Return `BLOCKED` when the same root cause shows no material progress for two
  consecutive corrective rounds, required evidence or authority is missing,
  the fix would exceed the approved boundary, or no authorized path can make
  progress.
- If the convergence budget is exhausted while the run is still converging,
  return `NEEDS_CORRECTION` with convergence evidence. When higher Project
  Manager judgment is needed, keep the Final Review verdict as
  `NEEDS_CORRECTION` and set closure/status to `PM_DECISION_REQUIRED` instead
  of inventing a new verdict or marking final `BLOCKED`.

## Automatic Review Scope Selection

Final Review must choose the narrowest review scope that protects authority and
evidence. This selection is part of the review packet; it should not depend on a
human remembering to request the right lane.

Use Deterministic Closure without starting another review lane, subagent, or
Final Review pass only when all are true:

- the original reviewer tagged the finding with closure eligibility class
  `MECHANICAL_STATUS` and authored the closure predicate before corrective
  editing; the normal finding classification remains `AUTO_CORRECTIVE`;
- the predicate names the finding ID, exact files and fields, authoritative
  value and source reference, allowed diff, closure commands, precommitted final
  verdict, Closure Receipt Owner, Closure Receipt Destination, and protected
  out-of-scope hashes;
- the substantive evidence and authoritative value were already reviewed; the
  correction only mirrors that value and does not originate a gate, approval,
  verdict, or acceptance decision;
- the corrective diff matches the predicate exactly, closure commands pass,
  out-of-scope hashes are unchanged, and State Truth Reconciliation passes
  after the correction;
- no semantics, permission, source authority, information architecture,
  contract, runtime, security, approval-gate criteria, validator meaning, or
  required-evidence meaning changed.

State Truth conflicts block closure until the responsible surface owners
reconcile them. Ledger, task, evidence, status, implementation, and corrective
surfaces may be changed only by their corresponding surface owner with matching
write/corrective authority. The fixer works according to the predicate and
returns evidence; it cannot author or broaden the predicate and cannot record
the closure receipt.

The Closure Receipt Owner is the original Final Review Controller or named
review packet author and must be different from the Corrective Worker. It must
run the reviewer-authored deterministic closure commands directly or cite a
trusted machine/CI result with command, revision, and result identity; fixer
self-report is not closure evidence. It records `AUTO_CLOSED_BY_PREDICATE`, the
Closure Receipt Ref, and Closure Receipt Destination in its own review
packet/output. That narrow review-output write does not grant implementation or
corrective-surface write authority and does not permit it to mutate ledger,
task, evidence, or status surfaces owned by someone else.

The receipt closes only the predicate-named finding. If the initial verdict was
`NEEDS_CORRECTION`, all blocking findings are now closed, and the predicate
precommitted the resulting `ACCEPTABLE` or `ACCEPTABLE_WITH_CONCERNS` verdict,
the same original Final Review Controller or named review packet author applies
that mechanical transition and records `VERDICT_FINALIZED_FROM_RECEIPT`. This
does not re-review files, start a reviewer, or create a new Final Review pass.
Final Review still owns the verdict; Project Manager still owns acceptance, and
Project Manager acceptance remains pending.

Deterministic Closure Reject/Fallback:

| Reject Condition | Required Result |
|---|---|
| Closure Receipt Owner is the Corrective Worker or same actor | `INVALID_REVIEW_REQUIRED`; targeted/full re-review. |
| Receipt owner mutates a non-owned surface | `INVALID_REVIEW_REQUIRED`; targeted/full re-review. |
| Extra or ambiguous diff exists, or an out-of-scope hash changed | `INVALID_REVIEW_REQUIRED`; targeted/full re-review. |
| Closure command fails, or trusted machine/CI evidence is failed, missing, or unidentified | `INVALID_REVIEW_REQUIRED`; targeted/full re-review. |
| State Truth Reconciliation is not `PASS` | `INVALID_REVIEW_REQUIRED`; targeted/full re-review. |
| Authoritative value, false-green risk, or gate-ready state remains unclear | `INVALID_REVIEW_REQUIRED`; targeted/full re-review. |

Use targeted status/evidence re-review when all are true:

- only ledgers, task/evidence records, status tables, closeout notes, or
  review packets changed;
- no product code, runtime behavior, schema, migration, test implementation,
  source authority, information architecture, permission boundary, approval
  gate, or validator meaning changed;
- the remaining findings are ordinary consistency, stale status, or evidence
  bookkeeping issues.

Use full affected-lane re-review when any are true:

- semantics, source authority, information architecture, permissions, security,
  approval gates, public contracts, runtime behavior, validator rules, or
  required evidence changed;
- the correction touches implementation files or test/runtime behavior;
- false-green risk, hidden fallback, or gate-ready status is in question;
- the targeted review cannot prove the remaining acceptance boundary.

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
  Manager. Project Manager forwards it to Final Review only after Structural
  Gate `PASS`.
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

The required closure order is Final Review verdict, corrective convergence or
explicit stop, Project Manager/project-owner decision, ledger update, then
closeout. `HANDOFF` is never a terminal closeout result. A `BLOCKED` run remains
open until the authorized owner records a close-blocked, abandon, defer, or
resume decision; only the first three permit closeout.
