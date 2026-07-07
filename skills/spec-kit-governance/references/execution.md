# SPEC-Kit Execution

Use this reference for implementation, debugging, refactoring, subagent work,
Strict Mode, Wave Execution, Session Orchestration, or Worktree Isolation.

## Pre-Edit Gate

Before editing files:

1. Read the routed SPEC docs.
2. Inspect current code or docs with narrow searches.
3. State allowed files, read-only files, forbidden files, and shared files.
4. Identify quality gates, approval gates, tests, smoke, and stop conditions.
5. Stop if the required change falls outside the phase boundary.

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
- allowed files;
- forbidden files;
- applicable skills, plugins, connectors, or tools;
- commands;
- expected evidence;
- return format.

Before delegating, inspect available capability metadata when the runtime
exposes it. Select specialist capabilities from metadata first, then load only
the selected capability instructions needed for the worker.

SPEC-Kit governs scope, gates, files, and evidence. Specialist capabilities do
the domain work.

Parallel writable lanes must not share files. Parallel lanes must not edit
`ACTIVE_CONTEXT.md` or `DOC_ROUTING.md`; they return proposals for controller
integration.

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

## Session Orchestration

When Session Orchestration is active:

- Project Manager creates the milestone execution packet.
- Coder Controller orchestrates phase and lane workers; it should not perform
  all phase work itself when bounded workers can reduce serial handoff safely.
- Coder performs integration self review, runs bounded corrective workers when
  allowed, and returns a milestone result packet.
- Project Manager runs only the structural gate.
- Final Review Controller orchestrates review workers or validation lanes,
  verifies independently, and returns a verdict.
- Corrective workers fix only findings named in corrective packets.

Default corrective round limit is 2.

Coder and Final Review controllers must reassess whether the milestone should
run serially, with waves inside phases, or with parallel phases. Stop for
Project Manager when a sequencing change affects scope, approval gates, public
contracts, shared ownership, or final decision authority.

## Runtime And Integration Claims

Do not claim UI, API, service, worker, database, device, or external integration
success from static inspection alone. Use live runtime evidence when that
surface is in scope, or record why smoke is not applicable.

## Stop Conditions

Stop or return to planning when:

- required files are outside the phase boundary;
- a closed approval gate is needed;
- contract owner and consumer disagree;
- runtime verification contradicts assumptions;
- local data hygiene is at risk;
- the task combines unrelated milestones.
