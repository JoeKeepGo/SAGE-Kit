# SAGE-Kit Execution

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

Frontend work should route to an available frontend or browser-testing adapter
when UI, styling, responsive layout, design-system components, accessibility,
or visual QA is in scope. It must return runtime, screenshot, console, network,
responsive, or accessibility evidence as applicable, but SAGE-Kit still decides
the gate.

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
- record L0-L4 evidence in `evidence.yaml` instead of copying long logs into
  startup docs;
- run `scripts/validate_task_dispatch.py --gate-ready` before returning a task,
  phase, or milestone as gate-ready when the packet requires validator
  closeout;
- return `HANDOFF` or `BLOCKED` when validator failure reflects missing scope,
  missing evidence, unsafe fallback, or a Project Manager decision.

Do not create task-dispatch records for ordinary small tasks unless Project
Manager adopted the profile.

## Session Orchestration

When Session Orchestration is active:

- Project Manager creates the milestone execution packet.
- Coder Controller orchestrates phase and lane workers by default.
- Coder Controller may self-execute only when the execution packet explicitly
  allows a narrow phase, integration glue step, or bounded corrective fix; it
  must record why worker dispatch was skipped.
- Coder performs integration self review, runs bounded corrective workers when
  allowed, and returns a milestone result packet.
- Project Manager runs only the structural gate.
- Final Review Controller orchestrates review workers or validation lanes,
  verifies independently, and returns a verdict.
- Final Review classifies required corrections and either opens an authorized
  corrective round or returns a packet-only handoff, Project Manager decision
  request, or blocker.
- Corrective workers fix only findings named in corrective packets.
- After corrective work, Final Review must collect independent re-review
  evidence. Rerun affected review workers, review subagents, or validation lanes
  when the original review used them, the fix touches behavior, contracts,
  runtime, shared files, gates, or the regression surface is unclear.
- If Task Dispatch Profile is active, Coder updates task/evidence records and
  Final Review treats them as an evidence index to verify, not as proof by
  themselves.

Default corrective round limit is 2.

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
