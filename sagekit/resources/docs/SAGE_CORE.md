# SAGE Core

SAGE Core defines the reusable rules that every project using SAGE-Kit should
follow. Project-specific details belong in project profiles, technical designs,
milestones, and phase documents.

## Execution Document Models

SAGE-Kit is a governance interpreter, not a document-copying system. Generic
governance belongs to the repository Skill and versioned SAGE-Kit contracts.
Project documents retain project-specific authority, scope, exceptions, state,
acceptance, and evidence.

The execution document model is separate from the Task Dispatch validation
contract:

- `legacy-markdown` keeps the established milestone and phase document flow.
- `thin-v1` uses `SAGE_PROJECT.json`,
  `docs/<M>/MILESTONE_MANIFEST.json`, and `docs/<M>/phases/<P>.json`.
- Task Dispatch versions remain v0, v1, and v2. `thin-v1` is not v3.

Adoption is explicit. Accepted historical documents remain immutable, active
legacy milestones continue through the legacy checker, and one active milestone
must not mix legacy and thin execution documents. Missing, mixed, or conflicting
document-model authority fails closed without downgrade.

For `thin-v1`, policy resolution is deterministic:

1. explicit project approval or gate;
2. project-local override;
3. pinned SAGE-Kit contract and profile;
4. runtime default.

Only policy keys declared overrideable by the pinned contract may be changed.
Conflicting authority fails closed. Installed Skill is not project authority;
the project lock and packaged versioned contract remain authoritative when a
local Skill is missing or older.

Use `sagekit packet compile` to create an ephemeral execution packet. Compact
packets bind the exact contract/profile references and digests. A standalone
compiled packet contains the resolved rules for runtimes without the matching
contract. Compilation does not rewrite manifests, `ACTIVE_CONTEXT`, or
`DOC_ROUTING`.

Resource Policy is an independent version dimension. Current execution may
resolve `conservative-host-v1` without adding fields to accepted history.
Packet schema v2 carries its resolved policy and Workspace Binding. Before a
managed local command, verify the packet with `sagekit workspace verify` and
route argv through `sagekit resource run`. A managed run reports its actual
`HARD` or `MANAGED` platform containment; interception of arbitrary commands
that bypass the runtime remains only a `SOFT` guarantee.
The reusable contract is in `docs/agent/HOST_RESOURCE_GOVERNANCE.md`.

## Bootstrap Maintainer Policy

SAGE-Kit does not force maintainers of the SAGE-Kit source repository to manage
its own development through an instantiated SAGE milestone, phase, ledger, or
closeout workflow. Source-repository dogfood is a validation mode, not a
mandatory control mode. Maintainers may use a lightweight ordinary engineering
workflow to avoid recursive governance and bootstrap cost.

This exception is limited to maintenance of the SAGE-Kit source repository. It
does not apply to adopted target projects and does not weaken their authority,
scope, gate, lock, evidence, approval, or completion contracts.

Execution economy, corrective authority, review convergence, evidence reuse,
and deterministic handoff follow `docs/agent/EXECUTION_ECONOMY.md`. Local
checkpoint and resume follow `docs/agent/CONTINUITY_PROTOCOL.md`. These focused
policies supersede older generic instructions that would otherwise require
broader repeated verification or review, but they never bypass an explicit
project approval, security, or destructive-operation gate.

Versioned Task Dispatch validation follows
`docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md`: closed legacy history uses
its frozen contract, active work uses the current contract, and ambiguous or
mixed records fail closed.

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
- Use local validators as evidence checks for governance structure, not as
  product acceptance or proof of runtime correctness.
- Treat external skills, plugins, tools, CI systems, and human reviews as
  execution and evidence inputs inside SAGE-Kit governance, not as replacements
  for SAGE-Kit gates.
- Use Capability Adapters for optional external skills, plugins, MCP tools,
  CLIs, CI systems, or reviewers so SAGE-Kit can detect, authorize, invoke,
  capture evidence, map outputs, and fall back without making them core
  dependencies.
- Keep secrets, local data, credentials, and production artifacts out of
  commits and reports.
- Avoid guessed fields, placeholder success, silent fallback, and hidden error
  paths.

## External Capability Boundary

SAGE-Kit is not a skill library. It is the governance and evidence layer that
lets skill libraries, coding agents, plugins, MCP tools, CI systems, and human
reviewers cooperate under a shared project contract.

SAGE-Kit governs authorization, milestone and phase boundaries, file ownership,
approval gates, evidence requirements, resource locks, and completion status.
External capabilities provide execution methods inside those boundaries.

Within project execution, apply this authority order:

1. Project specification and approval gates.
2. SAGE-Kit harness rules.
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
to SAGE-Kit milestone, phase, or packet documents so the project keeps one
durable source of truth.

Superpowers is a reference integration for execution discipline when available.
SAGE-Kit does not require it and does not copy it.

Use `docs/agent/CAPABILITY_ADAPTERS.md` for the adapter lifecycle,
authorization levels, evidence contract, frontend adapter rules, and
installation policy. Adapters default to metadata-only or read-only. Installing
external skills, plugins, CLIs, MCP servers, hooks, or global configuration
requires explicit approval when it writes environment or user configuration.

## Local Runtime Boundary

The `sagekit` CLI is a read-only governance runtime for diagnostics and
structure checks, plus a bounded initializer for SAGE-Kit document skeletons
and an ignored local continuity checkpoint. It exists below project authority:

- `sagekit init` creates selected governance documents and support templates for
  Light, Standard, or Heavy adoption. It must not create executable milestones,
  task records, worktrees, commits, pushes, external config, or approval
  decisions.
- `sagekit doctor` diagnoses repository and runtime state.
- `sagekit check` checks SAGE-Kit documents and task/evidence records for
  review readiness.
- `sagekit checkpoint` and `sagekit resume` write or read only
  `.sagekit/runtime/CURRENT_RUN.json`; the file is local, bounded, gitignored,
  and never a project acceptance record.

CLI output is evidence. It does not replace tests, runtime smoke, human review,
Project Manager acceptance, approval gates, or milestone closeout decisions.

Mode-aware checks are proportional. Light checks only the Light document
baseline. Standard makes Standard project documents blocking. Heavy makes the
minimal controller-governance baseline blocking, but optional controls such as
Task Dispatch, Wave Execution, Worktree Isolation, profiles, and adapters remain
opt-in and artifact-triggered.

## Trivial And Non-Trivial Work

Trivial work is limited to typo fixes, formatting-only documentation edits, or
metadata changes that do not affect behavior, contracts, verification, security,
runtime operation, release process, or agent execution.

All other work is non-trivial and requires a retained phase/task authority:
either the selected legacy document or an explicitly adopted thin phase
manifest.

## Project Document Baselines

SAGE-Kit document requirements are proportional. Light adoption does not require
teams to backfill Standard documents unless the selected mode, project risk, or
active gate upgrades the work.

Light baseline:

| File | Purpose |
|---|---|
| `docs/PROJECT_PROFILE.md` | Product identity, goals, users, constraints, and non-goals. |
| `docs/QUALITY_GATES.md` | Evidence required before work can be called complete. |
| `docs/ACTIVE_CONTEXT.md` | Short current-state summary for future sessions. |
| `docs/DOC_ROUTING.md` | Smallest safe read set by task type. |
| `docs/M<ID>/MILESTONE_LEDGER.md` | Current milestone state when executable work starts. |
| `docs/M<ID>/<NN>-<phase-name>.md` | One retained phase doc for the active executable slice. |

Standard required documents:

| File | Required When |
|---|---|
| `docs/TECHNICAL_DESIGN.md` | Standard or Heavy adoption, or architecture and runtime contracts affect the work. |
| `docs/ENGINEERING_SYSTEM.md` | Standard or Heavy adoption, or recurring human/AI workflow must be governed. |
| `docs/APPROVAL_GATES.md` | Standard or Heavy adoption, or any closed approval gate can affect execution. |
| `docs/MILESTONE_ROADMAP.md` | Standard or Heavy adoption, or more than one executable milestone is planned. |
| `docs/M<ID>/COMPLETION_REPORT.md` | Standard or Heavy adoption, or the phase needs retained completion evidence. |

Conditional project documents:

| File | Required When |
|---|---|
| `docs/PROJECT_OWNER_INTAKE.md` | The project starts from a broad or non-technical idea. |
| `docs/CAPABILITY_MAP.md` | The project starts from a broad or non-technical idea, or roadmap granularity is uncertain. |

## Standard Workflow

```text
explore -> plan -> implement -> verify -> submit
```

SAGE-Kit supports these execution controls:

| Control | Use For | Primary Doc |
|---|---|---|
| Project Owner Entry | Lightweight intake for broad or non-technical project ideas. | `docs/agent/PROJECT_OWNER_ENTRY.md` |
| Capability Map | Planning layer before executable milestone roadmaps. | `docs/templates/CAPABILITY_MAP_TEMPLATE.md` |
| Governance Levels | Proportional Light, Standard, or Heavy control selection plus Authority Matrix by scope. | `docs/agent/GOVERNANCE_LEVELS.md` |
| Phase Execution | One bounded phase or task. | `docs/agent/PHASE_EXECUTION.md` |
| Wave Execution | Safe parallel lanes inside one phase. | `docs/agent/WAVE_EXECUTION.md` |
| Session Orchestration | Large milestones that need Project Manager, Coder, and Final Review controllers. | `docs/agent/SESSION_ORCHESTRATION.md` |
| Worktree Isolation | Optional isolation policy for authorized milestone, phase, lane, or review workspaces. | `docs/agent/WORKTREE_ISOLATION.md` |
| Task Dispatch Profile | Optional structured task/evidence records, resource locks, leases, and validator-backed gate closeout. | `docs/profiles/task-dispatch/DISPATCH_PROFILE.md` |
| Capability Adapters | Optional external capability routing with authorization, evidence mapping, and fallback policy. | `docs/agent/CAPABILITY_ADAPTERS.md` |
| Planning Package Closeout | Optional one-session orchestration for planning-only package, review, targeted fix, closure verification, closeout/status, and submit handoff with separate role authority. | `docs/agent/MILESTONE_PLANNING.md` |

Explore:

- Identify the active project boundary.
- Read the smallest relevant doc set.
- Inspect current files and tests before assuming structure.
- Record unknowns, risks, likely files, and verification needs.

Plan:

- Select `Light`, `Standard`, or `Heavy` governance for the current control
  scope using `docs/agent/GOVERNANCE_LEVELS.md`.
- Select the permission mode for the current role using the Authority Matrix in
  `docs/agent/GOVERNANCE_LEVELS.md`.
- For broad, non-technical, or coarse-roadmap projects, create project owner intake and a
  capability map before an executable roadmap.
- Write or update the retained phase document.
- Name requirement IDs and contracts.
- Define allowed files, read-only files, and forbidden files.
- Select specialist external capabilities from available metadata when they are
  relevant.
- Apply the Capability Adapter lifecycle for selected external skills, plugins,
  MCP tools, CLIs, CI systems, or reviewers.
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
- Use planning package closeout only when changes are limited to planning
  artifacts, ledgers, evidence or status records, and closeouts, and role
  separation plus submit authority are explicit.
- Maintain `docs/ACTIVE_CONTEXT.md` as a current-state snapshot only when the
  role or packet has both write permission and ownership; otherwise return a
  memory update proposal or no-change note.
- Update `docs/DOC_ROUTING.md` only when routing or document topology changed
  and the role or packet has both write permission and ownership; otherwise
  return a memory update proposal or no-change note.
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
- capability adapter authorization level and evidence mapping when relevant;
- tests run;
- runtime smoke or reason it is not applicable;
- governance level and permission mode;
- corrective closure status when review finds required corrections;
- independent corrective re-review evidence, or a strict Deterministic Closure
  receipt and verdict-finalization status, when corrective work changes files,
  behavior, contracts, runtime behavior, gate state, shared ownership, or
  required evidence;
- skipped checks;
- security or data hygiene checks;
- active context and document routing maintenance;
- remaining gaps;
- handoff or next action.

Blocking gates cannot be bypassed by listing them as skipped checks. A skipped
blocking gate means the work is `BLOCKED` or `HANDOFF`, not complete.

Strict Deterministic Closure is the only exception to a new corrective review
invocation. It follows the eligibility, owner separation, evidence, State Truth,
receipt, rejection, and fallback contract in
`docs/agent/SESSION_ORCHESTRATION.md`. Final Review alone may record the
precommitted `VERDICT_FINALIZED_FROM_RECEIPT`; Project Manager acceptance
remains separate and pending.

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
