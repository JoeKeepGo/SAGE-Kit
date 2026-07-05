# SPEC-Kit Execution

Use this reference for implementation, debugging, refactoring, subagent work,
Strict Mode, or Wave Execution.

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
- commands;
- expected evidence;
- return format.

Parallel writable lanes must not share files. Parallel lanes must not edit
`ACTIVE_CONTEXT.md` or `DOC_ROUTING.md`; they return proposals for controller
integration.

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
