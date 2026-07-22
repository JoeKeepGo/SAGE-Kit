# SAGE Core

SAGE Core defines the reusable rules that every project using SAGE-Kit should
follow. Project-specific details belong in project profiles, technical designs,
milestones, and phase documents.

SAGE-Kit no longer uses a public CLI as the governance authority. The product
surface is now project-owned SPEC contracts plus an embeddable Harness core.

## SPEC Sources And Execution Documents

SAGE-Kit defines SPEC semantics and Harness execution contracts, not a required
project documentation directory. A SPEC Source Adapter reads Markdown, an
explicit or configured source, or the legacy `docs/<M>` layout. The Harness
consumes a normalized model in which paths are provenance rather than business
identity. See `docs/agent/SPEC_SOURCE_CONTRACT.md` for the canonical scope,
authority, history, adoption, and resource-admission contract.

SAGE-Kit remains a governance interpreter: generic governance belongs to the
pinned package contract, while project documents retain project-specific facts.
A standalone compiled packet may carry resolved rules without making project
documents repeat them.

Source selection and its fail-closed order are canonical at
`docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-001`; executable, handoff, history,
reference, and runtime-state classification is canonical at
`docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-002`. SAGE Core retains the top-level
module boundary and does not redefine those rules.

The execution document model remains separate from Task Dispatch. Existing
`legacy-markdown` projects continue without migration. `thin-v1` removes
repeated generic governance prose but does not reduce project-specific planning
depth, and it is not Task Dispatch v3. SAGE-Kit sets no universal maximum for
Milestones, Waves, Phases, or changed files.

Default adoption binds the installed package and canonical contract/resource
version and digest. Framework vendoring is opt-in compatibility. Installed
Skill is not project authority.

Use the embedded harness packet API to create an ephemeral packet carrying scope,
authority, dependency DAG, boundaries, evidence, stop conditions, and resource
policy. Check and compile do not rewrite source documents, ACTIVE_CONTEXT,
accepted history, or runtime state. Resource Policy remains an independent
version dimension through `conservative-host-v1`, with honest `HARD`,
`MANAGED`, and bypassable `SOFT`
boundaries defined in `docs/agent/HOST_RESOURCE_GOVERNANCE.md`.
Strict managed operations verify with a scoped runtime check and then route through
local host execution boundaries; direct read-only admission does not.

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
- Use retained active SPEC, phase, or task authority for non-trivial work.
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
- Select governance per control scope under
  `docs/agent/GOVERNANCE_LEVELS.md#sage-auth-003`; that canonical rule owns
  level selection and upgrade semantics.
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
  runtime adapters, CI systems, or reviewers so SAGE-Kit can detect,
  authorize, invoke,
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

<a id="sage-auth-001"></a>

### Project And Host Authority

Within project execution, apply this authority order:

1. Project specification and approval gates.
2. SAGE-Kit governance and harness defaults.
3. External skill, plugin, connector, MCP tool, CI, or reviewer workflow.
4. Agent default behavior.

Project authority therefore outranks SAGE-Kit defaults, and SAGE-Kit outranks
optional adapter and agent defaults. This order applies only inside the project
contract and never overrides host, platform, system, or developer authority.

External capability outputs are evidence inputs. They do not automatically mark
work `DONE`, open or close approval gates, accept milestones, or satisfy
completion requirements.

Continuous execution by an external capability remains inside its approved
phase, lane, task, or corrective boundary and applies the approval rule below.
Adapter-specific shared-file, resource-lock, evidence, fallback, and controller
stop conditions remain defined in `docs/agent/CAPABILITY_ADAPTERS.md`.

Plans produced by external planning workflows should be written into or mapped
to SAGE-Kit milestone, phase, or packet documents so the project keeps one
durable source of truth.

Superpowers is a reference integration for execution discipline when available.
SAGE-Kit does not require it and does not copy it.

Use `docs/agent/CAPABILITY_ADAPTERS.md` for the adapter lifecycle,
authorization levels, evidence contract, frontend adapter rules, and
installation policy. Adapters default to metadata-only or read-only. Installing
  external skills, plugins, runtime adapters, MCP servers, hooks, or global
  configuration
requires explicit approval when it writes environment or user configuration.

<a id="sage-auth-009"></a>

## Explicit And Scoped Approval

Approval is explicit and target-scoped. An agent cannot infer it from unrelated
context, broaden or transfer it beyond the named action, target, environment,
and conditions, or reuse it to cross another closed approval gate.

Runtime or environment mutation, destructive action, external mutation, and
commit, push, merge, publish, release, or cleanup remain closed unless the grant
expressly covers that operation and target. Project instances retain their exact
gate definitions and approval fields; SAGE-Kit defaults do not open them.

## Embedded Runtime Boundary

SAGE-Kit provides an embedded harness interface for diagnostics, normalized
SPEC packets, and bounded continuity persistence. It exists below project
authority:

- Project setup and bootstrap behavior is explicit and package-bound.
- Diagnostics include governance and structure checks.
- Packet compilation is a bounded local operation for host workflows.
- Continuity state is stored at `.sagekit/runtime/CURRENT_RUN.json`; it is local,
  bounded, gitignored, and never a project acceptance record.

Harness output is evidence only. It does not replace tests, runtime smoke, human
review, Project Manager acceptance, approval gates, or milestone closeout
decisions.

Mode-aware checks are proportional. Light checks only the Light authority
baseline. Standard makes the Standard project-authority baseline blocking.
Heavy makes the minimal controller-governance baseline blocking, but optional
controls such as Task Dispatch, Wave Execution, Worktree Isolation, profiles,
and adapters remain opt-in and artifact-triggered.

<a id="sage-grf-001"></a>

## Graph Admission

Begin with one bounded execution loop. Admit a Graph only when it has concrete
decision value from a dependency, an independent context or tool boundary, safe
parallel work with a defined join, an independent evaluator, authority
separation, or a state boundary. Otherwise keep the work as one bounded loop.

Light work is never required to upgrade to Graph execution. Milestones, Waves,
Phases, Lanes, and a single bounded loop remain available shapes; admission is
based on the work, not governance weight. A Graph here expresses planning and
execution relationships only. It does not create a runtime Graph, resolver,
scheduler, graph database, or authority for dynamic graph rewrite. Once a Graph
or Wave is admitted, execution-shape, affected-serialization, safe-barrier, and
lane-status semantics are owned by `docs/agent/WAVE_EXECUTION.md`.

## Trivial And Non-Trivial Work

Trivial work is limited to typo fixes, formatting-only documentation edits, or
metadata changes that do not affect behavior, contracts, verification, security,
runtime operation, release process, or agent execution.

All other work is non-trivial and requires retained active SPEC, phase, or task
authority. That authority may be a configured project SPEC, normalized manifest,
execution packet, selected legacy document, or explicitly adopted thin phase
manifest. Markdown location is provenance, not authority by itself.

## Legacy Project Document Baselines

These fixed paths describe the legacy compatibility profile, not the source
contract for a package-bound project. Package-bound projects may map equivalent
project facts from authorized locations. Requirements remain proportional;
Light adoption does not require teams to backfill Standard documents unless the
selected mode, project risk, or active gate upgrades the work.

Light baseline:

| File | Purpose |
|---|---|
| `docs/PROJECT_PROFILE.md` | Product identity, goals, users, constraints, and non-goals. |
| `docs/QUALITY_GATES.md` | Evidence required before work can be called complete. |
| Configured active-context path (legacy default: `docs/ACTIVE_CONTEXT.md`) | Short current-state summary for future sessions. |
| Configured document-routing path (legacy default: `docs/DOC_ROUTING.md`) | Smallest safe read set by task type. |
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
- Write or update the retained active SPEC, phase, or task authority in the
  project's selected representation.
- Name requirement IDs and contracts.
- Define allowed files, read-only files, and forbidden files.
- Select specialist external capabilities from available metadata when they are
  relevant.
- Apply the Capability Adapter lifecycle for selected external skills, plugins,
  MCP tools, runtime adapters, CI systems, or reviewers.
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
- Maintain the configured active-context path (legacy default:
  `docs/ACTIVE_CONTEXT.md`) as a current-state snapshot only when the role or
  packet has both write permission and ownership; otherwise return a memory
  update proposal or no-change note.
- Update the configured document-routing path (legacy default:
  `docs/DOC_ROUTING.md`) only when routing or document topology changed and the
  role or packet has both write permission and ownership; otherwise return a
  memory update proposal or no-change note.
- Update completion reports and ledgers with memory maintenance status.
- Update task/evidence records and run the dispatch validator when the project
  adopted Task Dispatch Profile for the active task or gate.
- Commit or hand off only the intended scope.

## Universal Completion Rule

## Embedded Harness Contract

Use `sagekit.check_project(...)` for read-only project or gate validation; its
result has an unambiguous `ok` property and complete findings. It supports the
configured active scope, explicit history scope, mode, gate-ready validation,
and an external scope manifest. Use
`sagekit.validate_task_and_evidence_records(...)` only for one task/evidence
pair. Candidate operations are public through `sagekit.freeze_candidate(...)`
and `sagekit.assess_candidate(...)`; do not import private candidate modules.

Project bootstrap is host-owned creation of the minimal versioned
`SAGEKIT_CONFIG.json`; SAGE-Kit does not expose bootstrap/init as a public API.
Resolve `ACTIVE_CONTEXT` and document routing from `SAGEKIT_CONFIG.json`.
`docs/ACTIVE_CONTEXT.md` and `docs/DOC_ROUTING.md` are legacy defaults only.

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
only through the configured document-routing path (legacy default:
`docs/DOC_ROUTING.md`) when prior milestone outcomes, decisions, gaps, or
provenance are relevant.
