# SPEC Core

SPEC Core defines the reusable rules that every project using SPEC-Kit should
follow. Project-specific details belong in project profiles, technical designs,
milestones, and phase documents.

## Principles

- State the product goal before implementation starts.
- Keep architecture boundaries explicit.
- Define contracts before consumers depend on them.
- Use retained phase documents for non-trivial work.
- Keep implementation scope small enough to review.
- Verify behavior with fresh evidence before claiming completion.
- Record durable state in docs instead of relying on chat memory.
- Keep startup context compact by replacing stale state instead of accumulating
  session history.
- Summarize closed milestones in compact closeouts instead of promoting
  historical ledgers into startup context.
- Use Project Owner Entry when a project starts from a broad or non-technical
  idea, but treat its output as planning input, not implementation authority.
- Build a capability map before promoting broad ideas into executable
  milestone roadmaps.
- Use milestone-level session orchestration only when it reduces handoff burden
  without weakening gates, verification, or final decision ownership.
- Use proportional governance: start with the lightest safe governance level
  and upgrade only when risk, scope, or control responsibility requires it.
- Use worktree isolation only when the project explicitly authorizes isolated
  execution and names submit and cleanup ownership.
- Use structured task dispatch only when the project explicitly adopts it and
  needs machine-checkable task/evidence records.
- Treat external skills, plugins, tools, CI systems, and human reviews as
  execution and evidence inputs inside SPEC-Kit governance, not as replacements
  for SPEC-Kit gates.
- Keep secrets, local data, credentials, and production artifacts out of
  commits and reports.
- Avoid guessed fields, placeholder success, silent fallback, and hidden error
  paths.

## External Capability Boundary

SPEC-Kit is not a skill library. It is the governance and evidence layer that
lets skill libraries, coding agents, plugins, MCP tools, CI systems, and human
reviewers cooperate under a shared project contract.

SPEC-Kit governs authorization, milestone and phase boundaries, file ownership,
approval gates, evidence requirements, resource locks, and completion status.
External capabilities provide execution methods inside those boundaries.

Within project execution, apply this authority order:

1. Project SPEC and approval gates.
2. SPEC-Kit harness rules.
3. External skill, plugin, connector, MCP tool, CI, or reviewer workflow.
4. Agent default behavior.

This order applies inside the project contract and does not override platform,
system, or developer instructions.

External capability outputs are evidence inputs. They do not automatically mark
work `DONE`, open or close approval gates, accept milestones, or satisfy
completion requirements.

Continuous execution by an external capability is allowed only inside approved
phase, lane, task, or corrective boundaries. It must stop at closed approval
gates, scope expansion, shared-file or resource-lock conflict, failed required
evidence, unapproved runtime, destructive, submit, merge, push, or cleanup
operations, or any condition that requires a higher controller decision.

Plans produced by external planning workflows should be written into or mapped
to SPEC-Kit milestone, phase, or packet documents so the project keeps one
durable source of truth.

Superpowers is a reference integration for execution discipline when available.
SPEC-Kit does not require it and does not copy it.

## Trivial And Non-Trivial Work

Trivial work is limited to typo fixes, formatting-only documentation edits, or
metadata changes that do not affect behavior, contracts, verification, security,
runtime operation, release process, or agent execution.

All other work is non-trivial and requires a retained phase or task document.

## Required Project Documents

| File | Purpose |
|---|---|
| `docs/PROJECT_PROFILE.md` | Product identity, goals, users, constraints, and non-goals. |
| `docs/TECHNICAL_DESIGN.md` | Architecture, runtime boundaries, data ownership, and integration contracts. |
| `docs/ENGINEERING_SYSTEM.md` | Day-to-day workflow for humans and AI agents. |
| `docs/QUALITY_GATES.md` | Evidence required before work can be called complete. |
| `docs/APPROVAL_GATES.md` | Actions that require explicit human approval. |
| `docs/ACTIVE_CONTEXT.md` | Short current-state summary for future sessions. |
| `docs/DOC_ROUTING.md` | Smallest safe read set by task type. |
| `docs/MILESTONE_ROADMAP.md` | Milestone sequence and review gates. |

Conditional project documents:

| File | Required When |
|---|---|
| `docs/PROJECT_OWNER_INTAKE.md` | The project starts from a broad or non-technical idea. |
| `docs/CAPABILITY_MAP.md` | The project starts from a broad or non-technical idea, or roadmap granularity is uncertain. |

## Standard Workflow

```text
explore -> plan -> implement -> verify -> submit
```

SPEC-Kit supports these execution controls:

| Control | Use For | Primary Doc |
|---|---|---|
| Project Owner Entry | Lightweight intake for broad or non-technical project ideas. | `docs/agent/PROJECT_OWNER_ENTRY.md` |
| Capability Map | Planning layer before executable milestone roadmaps. | `docs/templates/CAPABILITY_MAP_TEMPLATE.md` |
| Governance Levels | Proportional Light, Standard, or Heavy control selection by scope. | `docs/agent/GOVERNANCE_LEVELS.md` |
| Phase Execution | One bounded phase or task. | `docs/agent/PHASE_EXECUTION.md` |
| Wave Execution | Safe parallel lanes inside one phase. | `docs/agent/WAVE_EXECUTION.md` |
| Session Orchestration | Large milestones that need Project Manager, Coder, and Final Review controllers. | `docs/agent/SESSION_ORCHESTRATION.md` |
| Worktree Isolation | Optional isolation policy for authorized milestone, phase, lane, or review workspaces. | `docs/agent/WORKTREE_ISOLATION.md` |
| Task Dispatch Profile | Optional structured task/evidence records, resource locks, leases, and validator-backed gate closeout. | `docs/profiles/task-dispatch/DISPATCH_PROFILE.md` |

Explore:

- Identify the active project boundary.
- Read the smallest relevant doc set.
- Inspect current files and tests before assuming structure.
- Record unknowns, risks, likely files, and verification needs.

Plan:

- Select `Light`, `Standard`, or `Heavy` governance for the current control
  scope using `docs/agent/GOVERNANCE_LEVELS.md`.
- For broad, non-technical, or coarse-roadmap projects, create project owner intake and a
  capability map before an executable roadmap.
- Write or update the retained phase document.
- Name requirement IDs and contracts.
- Define allowed files, read-only files, and forbidden files.
- Select specialist external capabilities from available metadata when they are
  relevant.
- Define tests, runtime smoke, and completion gate.

Implement:

- Stay inside the phase boundary.
- Keep interfaces explicit.
- Avoid unrelated refactors.
- Stop if the required change expands beyond the approved phase.

Verify:

- Run focused tests and any required runtime checks.
- Prove UI, API, service, worker, database, or integration claims with evidence.
- Record skipped checks and blockers clearly.

Submit:

- Review changed files.
- Check local data hygiene.
- Maintain `docs/ACTIVE_CONTEXT.md` as a current-state snapshot.
- Update `docs/DOC_ROUTING.md` only when routing or document topology changed.
- Update completion reports and ledgers with memory maintenance status.
- Update task/evidence records and run the dispatch validator when the project
  adopted Task Dispatch Profile for the active task or gate.
- Commit or hand off only the intended scope.

## Universal Completion Rule

No work is complete until the completion report names:

- scope implemented;
- files changed;
- contract evidence;
- selected capability use and fallback when relevant;
- tests run;
- runtime smoke or reason it is not applicable;
- skipped checks;
- security or data hygiene checks;
- active context and document routing maintenance;
- remaining gaps;
- handoff or next action.

Blocking gates cannot be bypassed by listing them as skipped checks. A skipped
blocking gate means the work is `BLOCKED` or `HANDOFF`, not complete.

Runtime, UI, service, worker, database, device, or external integration evidence
is required only when that surface is in scope.

## Roadmap Granularity Rule

Project Owner Entry must not produce an executable roadmap directly. It
produces intake notes, a project profile draft, a capability map, and draft
milestone candidates.

Only milestone candidates that pass Milestone Granularity Gate may be promoted
into `docs/MILESTONE_ROADMAP.md` for implementation planning.

## Milestone Closeout Rule

When a milestone closes, write or update `docs/M<ID>/MILESTONE_CLOSEOUT.md`.

The closeout records the milestone outcome, shipped capabilities, key decisions,
verification summary, known gaps, follow-up milestones, and links to evidence.
It must not duplicate raw logs, full evidence tables, or phase reports.

Historical closeouts are not default startup context. Future agents read them
only through `docs/DOC_ROUTING.md` when prior milestone outcomes, decisions,
gaps, or provenance are relevant.
