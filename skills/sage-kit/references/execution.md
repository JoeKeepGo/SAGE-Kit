# SAGE-Kit Execution

Execution economy, change classes, Bounded Corrective Authority, evidence
invalidation, one primary review topology, shared-file serialization, and local
limits are canonical in `docs/agent/EXECUTION_ECONOMY.md`. Use
`docs/agent/CONTINUITY_PROTOCOL.md` when a local limit requires
`HANDOFF_READY`. These rules prevent older generic execution guidance from
causing broader repeated work; explicit project approval and safety gates still
control.

Use this reference for implementation, debugging, refactoring, subagent work,
Strict Mode, Wave Execution, Session Orchestration, or Worktree Isolation.

## Pre-Edit Gate

Before editing files:

1. Read the routed specification docs.
2. Inspect current code or docs with narrow searches.
3. Select the governance level for the current control scope.
4. State governance level and permission mode.
5. State allowed files, read-only files, forbidden files, and shared files.
6. Identify quality gates, approval gates, tests, smoke, and stop conditions.
7. Stop if the required change falls outside the phase boundary.

## Execution Loop

1. Implement the narrowest change.
2. Keep contracts explicit.
3. Avoid unrelated refactors.
4. Add or update focused tests when behavior changes.
5. Run focused checks.
6. Run runtime smoke when runtime behavior is claimed.
7. Record evidence in the completion report, phase doc, or ledger.

## Strict Mode

Use the project model assurance policy to decide whether Strict Mode is
required.

In Strict Mode:

- execute only the task card;
- read only listed files;
- modify only allowed files;
- run exact commands;
- stop on ambiguity, failed required commands, missing contracts, or approval
  gates;
- return memory update proposals when startup docs are not allowed files.

Strict Mode `DONE` means the task card is complete, not necessarily the phase.

## Subagents And Lanes

Use subagents only for bounded tasks with clear ownership. For each lane, define:

- role;
- objective;
- governance level;
- allowed files;
- forbidden files;
- applicable skills, plugins, connectors, or tools;
- commands;
- expected evidence;
- return format.

Before delegating, inspect available capability metadata when the runtime
exposes it. Select specialist capabilities from metadata first, then load only
the selected capability instructions needed for the worker.

SAGE-Kit governs scope, gates, files, and evidence. Specialist capabilities do
the domain work.

## External Capability Integration

Use external skills, plugins, connectors, and tools only when they are relevant
to the approved SAGE-Kit phase, lane, task, or corrective boundary.

External capabilities may supply execution methods. They must not redefine
scope, create new file authority, bypass locks, open approval gates, downgrade
required evidence, or mark SAGE-Kit gates complete.

Superpowers is a reference integration, not a hard dependency. If it is
available, route only to the named skills that fit the current need. If it is
unavailable, continue with SAGE-Kit phase, gate, packet, and evidence
templates.

Apply `docs/agent/CAPABILITY_ADAPTERS.md` for external capabilities. Use
metadata-only or read-only behavior by default. Do not install capabilities,
write MCP config, add hooks, generate global skills, or mutate environment
configuration unless the active SAGE-Kit boundary or user approval explicitly
allows it.

For approved install candidates such as `ui-ux-pro-max`, `OpenSpec`, or
`GitNexus`, do not rely on remembered commands. Read current provider
documentation, package metadata, or installed-tool help first; then request
approval with exact command, write list, runtime requirements, rollback path,
and fallback. If docs are unclear or conflict, return `HANDOFF`.

For `ui-ux-pro-max`, prefer a single Codex-targeted install path when approved.
Do not use `--ai all`, global install, or multi-assistant generation unless the
user explicitly approves the wider environment write. `design-system/` outputs
require allowed-file coverage and remain design evidence, not SAGE-Kit source
of truth.

Recommended routing:

| Need | superpowers Skill |
|---|---|
| Clarify broad intent before planning | `superpowers:brainstorming` |
| Convert an approved phase into an execution plan | `superpowers:writing-plans` |
| Implement a feature or bug fix | `superpowers:test-driven-development` |
| Diagnose failures or unexpected behavior | `superpowers:systematic-debugging` |
| Run bounded worker tasks | `superpowers:subagent-driven-development` or `superpowers:dispatching-parallel-agents` |
| Request implementation review | `superpowers:requesting-code-review` |
| Prove work before completion claims | `superpowers:verification-before-completion` |
| Finish branch work after submit authority exists | `superpowers:finishing-a-development-branch` |

Frontend work should detect and select an available frontend or browser-testing
adapter when UI, styling, responsive layout, design-system components,
accessibility, or visual QA is in scope and the adapter is useful. If no
adapter is available, authorized, or useful, record the fallback and continue
through the SAGE-Kit-native path when safe. Selected adapters must return
runtime, screenshot, console, network, responsive, or accessibility evidence as
applicable, but SAGE-Kit still decides the gate.

SAGE-Kit remains authoritative for scope, file ownership, governance level,
resource locks, quality gates, approval gates, memory maintenance, milestone
state, and final acceptance.

Do not copy full external workflows into SAGE-Kit docs. Record the selected
capability name, the boundary it served, and concise evidence produced.

External planning outputs must be written into, or explicitly mapped to, the
active milestone ledger, phase doc, execution packet, or result packet. Do not
leave an untracked second source of truth.

External capability completion is execution evidence. It is not acceptance,
gate completion, milestone closure, or authorization to continue past a closed
SAGE-Kit gate.

Continuous execution may proceed only inside the approved phase, task, lane, or
corrective boundary. Stop for controller or user decision on closed approval
gates, scope expansion, shared-file conflicts, resource lock conflicts, failed
required evidence, or unapproved runtime, destructive, submit, merge, push, or
cleanup operations.

Parallel writable lanes must not share files. Parallel lanes must not edit
`ACTIVE_CONTEXT.md` or `DOC_ROUTING.md`; they return proposals for controller
integration.

Direct memory-file edits require both permission mode and ownership. Without
both, return a `Memory Update Proposal` or explicit no-change note.

Do not inherit Heavy governance globally. A Heavy milestone controller may
delegate Light or Standard workers when their scope is narrow and risk is
bounded. Workers that discover Heavy triggers must stop for controller
decision.

## Worktree Isolation

Use Worktree Isolation only when the Project Manager execution packet allows
it.

Coder Controller may decide which authorized phases or lanes receive worktrees.
It must record the worktree map, branch names, owners, integration status, and
cleanup recommendation in the milestone result packet.

Keep work serial or stop for Project Manager when shared files, migrations,
lockfiles, generated artifacts, runtime ownership, approval gates, branch base,
maximum worktree count, submit authority, or cleanup policy are unclear.

Workers must not push, merge, or delete worktrees unless the packet explicitly
assigns that authority.

## Task Dispatch

Use Task Dispatch Profile only when the active milestone or execution packet
adopts it.

When active:

- read the active `task.yaml` and `evidence.yaml` named by routing;
- keep task status, runs, attempts, resource locks, leases, blockers, and next
  action current;
- run State Truth Reconciliation whenever a task moves between planning,
  waiting, authorized, in-progress, pending-review, verified, blocked, or
  released states;
- record L0-L4 evidence in `evidence.yaml` instead of copying long logs into
  startup docs;
- run `scripts/validate_task_dispatch.py --gate-ready` before returning a task,
  phase, or milestone as gate-ready when the packet requires validator
  closeout;
- return `HANDOFF` or `BLOCKED` when validator failure reflects missing scope,
  missing evidence, unsafe fallback, or a Project Manager decision.

Do not create task-dispatch records for ordinary small tasks unless Project
Manager adopted the profile.

### State Truth Reconciliation

Run this gate before starting a task, after creating or renewing a run/lease,
before leaving a task, and before moving to the next task or phase.

All active state surfaces must agree:

- `task.yaml`: status, runs, attempts, locks, leases, blockers, closure note,
  and next action;
- `evidence.yaml`: status, L0-L4 reasons, next action, artifacts,
  files-changed, commands, skipped checks, and review result;
- milestone ledger and dispatch board: current status, historical decisions,
  accepted authority, blockers, and next action;
- completion or result packet when it exists.

Reconciliation is inspect-only by default. Use the owner recorded by project
routing or the active packet. In the absence of a narrower project rule:

- Project Manager owns the dispatch board, milestone ledger, and current
  decision state;
- the assigned execution controller owns `task.yaml` lifecycle and run/lease
  coordination;
- the evidence producer owns evidence facts, while the assigned reviewer owns
  review result and acceptance fields;
- the packet author owns its result, review, or corrective packet.

Mutate a surface only when both ownership and the required write or corrective
authority are present. Otherwise return a precise update proposal, corrective
packet, or `HANDOFF`; do not make multiple files agree by overwriting a more
authoritative source.

If authority, branch, baseline, run, lease, or gate state changed, remove stale
planning/future/waiting wording from active fields. Historical STOP or waiting
decisions may remain only when marked historical, superseded, or unlocked by a
named accepted authority.

Do not advance to the next task or phase when structured task/evidence fields
contradict the ledger, board, active run, or lease. Treat that as false-green
or stale-authority risk, not ordinary documentation cleanup.

## Session Orchestration

When Session Orchestration is active:

- Project Manager creates the milestone execution packet.
- Coder Controller orchestrates phase and lane workers by default.
- Coder Controller may self-execute only when the execution packet explicitly
  allows a narrow phase, integration glue step, or integration repair before
  Final Review; it must record why worker dispatch was skipped.
- Coder performs integration self review, runs bounded integration repair
  workers when allowed, and returns a milestone result packet.
- Project Manager runs only the structural gate.
- Final Review Controller orchestrates review workers or validation lanes,
  verifies independently, and returns a verdict.
- Final Review classifies required corrections and either opens an authorized
  corrective round or returns a packet-only handoff, Project Manager decision
  request, or blocker.
- Corrective orchestration authority does not grant Final Review write
  authority. Final Review delegates fixes to separately authorized corrective
  workers and remains independent for re-review.
- Corrective workers fix only findings named in corrective packets.
- After corrective work, Final Review follows the Deterministic Closure or
  re-review selection contract in `docs/agent/SESSION_ORCHESTRATION.md`. Only
  the separated review authority may record a receipt and precommitted
  `VERDICT_FINALIZED_FROM_RECEIPT`; Project Manager acceptance remains pending.
- If Task Dispatch Profile is active, Coder updates task/evidence records and
  Final Review treats them as an evidence index to verify, not as proof by
  themselves.

Corrective convergence budgets may be configured by the execution or Final
Review packet, but they are control signals, not unconditional blockers.
Full-suite and wheel/install runs before review and corrective closure are
preliminary feedback and do not consume final-candidate capacity. After the
single corrective batch closes, freeze a HEAD/diff/contract/dependency
fingerprint and allow one final run per matching candidate. One approved
corrective batch may create one automatic successor without budget approval;
another successor from that batch or any change after final verification
returns `HANDOFF_READY`. A human-approved handoff corrective may create the
next generation only when it persists an authority anchor, root-cause id, and
finding count. Generation is not mechanically capped; the same root cause with
no progress for two approved rounds returns `BLOCKED`, while reduced findings
reset the no-progress count.
Continue automatic correction only inside an authorized corrective packet or
boundary while findings or severity decrease, scope does not expand, no
blocking approval gate is bypassed, and no new authority, false-green,
approval-gate, security, validator/gate-ready, source-authority, or
evidence-integrity risk appears. Stop as `BLOCKED` when the same root cause has
no material progress for two consecutive rounds, required evidence or authority
is missing, or the fix would exceed the approved boundary. When Project Manager
judgment is needed, return `NEEDS_CORRECTION` with `PM_DECISION_REQUIRED`
closure/status rather than `BLOCKED`.

Coder and Final Review controllers must reassess whether the milestone should
run serially, with waves inside phases, or with parallel phases. Heavy mode
does not imply wave readiness. Stop for Project Manager when a sequencing
change affects scope, approval gates, public contracts, shared ownership, or
final decision authority.

## Runtime And Integration Claims

Do not claim UI, API, service, worker, database, device, or external integration
success from static inspection alone. Use live runtime evidence when that
surface is in scope, or record why smoke is not applicable.

## Stop Conditions

Stop or return to planning when:

- required files are outside the phase boundary;
- a closed approval gate is needed;
- an external capability suggests scope, file, runtime, or gate changes outside
  the approved boundary;
- an external planning output has not been mapped into tracked SAGE-Kit docs;
- a shared-file conflict or resource lock conflict appears;
- required evidence fails or cannot be produced;
- unapproved runtime, destructive, submit, merge, push, or cleanup operations
  are needed;
- contract owner and consumer disagree;
- runtime verification contradicts assumptions;
- local data hygiene is at risk;
- the task combines unrelated milestones.
