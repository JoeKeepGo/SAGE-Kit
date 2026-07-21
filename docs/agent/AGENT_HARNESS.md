# Agent Harness

The Agent Harness defines how AI agents work inside a SAGE-Kit project.

The harness does not replace the project spec. It tells agents how to execute
against the spec without losing context, widening scope, or hiding risk.

## SPEC And Execution Authority

The Harness consumes the normalized model defined by
`docs/agent/SPEC_SOURCE_CONTRACT.md`, never a directory convention directly.
`ACTIVE_SPEC` is current execution authority; `ACTIVE_CONTEXT` is its compact
handoff view; `ACCEPTED_HISTORY` and `REFERENCE_ONLY` are non-executable; and
leases, candidates, counters, and checkpoints are `.sagekit` `RUNTIME_STATE`.

Resolve the source from an explicit embedded API source, configured mapping,
ACTIVE_CONTEXT Current Work Pointer, then the legacy `docs/<M>` adapter for an
explicitly selected legacy milestone. Explicit and configured sources fail
closed without fallback. Paths are provenance, not semantic identity.

Thin sources contain project facts while generic governance comes from the
pinned profile. Thin reduces repeated prose, not planning depth. Established
legacy projects remain compatible, accepted history stays immutable, and
missing or conflicting authority produces one aggregated scope finding.

## Operating Rules

- Read the smallest safe context first.
- Select the lightest safe governance level for the current control scope using
  `docs/agent/GOVERNANCE_LEVELS.md`.
- Select the permission mode for the current role: read-only, writable,
  corrective, environment-writing, or submit authority.
- Identify the active phase before editing.
- Treat Project Owner Intake and Capability Map as planning inputs, not
  implementation authorization.
- Name allowed files, read-only files, and forbidden files before writable work.
- Use Wave Execution for safe parallel work inside a phase.
- Use Session Orchestration for large milestone-level work that needs separate
  Project Manager, Coder, and Final Review controllers.
- In Session Orchestration, Coder Controller should orchestrate workers by
  default. It may self-execute only when the execution packet explicitly allows
  a narrow phase, glue step, or integration repair before Final Review.
- Use Worktree Isolation only when Project Manager authorization names the
  allowed mode, maximum count, naming, integration owner, submit authority, and
  cleanup policy.
- Use Task Dispatch Profile only when the active milestone or execution packet
  adopts structured task/evidence records, resource locks, leases, and validator
  closeout.
- Use Planning Package Closeout only when the work is planning-only and role
  separation, targeted review, and submit authority can be preserved inside one
  root session.
- Route work to relevant external capabilities when the agent runtime exposes a
  capability list.
- Use `docs/agent/CAPABILITY_ADAPTERS.md` when an external capability is
  selected, unavailable, needs installation, writes environment configuration,
  or requires fallback.
- Keep one task tied to one phase unless a batch execution plan explicitly
  defines phase order, gates, and stop conditions, or Session Orchestration
  defines the milestone controller packet flow.
- Do not invent missing contracts.
- Do not use placeholder success for failed runtime behavior.
- Do not touch closed approval gates.
- Update durable project facts before handoff when ownership allows it.
- Treat the configured `ACTIVE_CONTEXT`, with legacy default
  `docs/ACTIVE_CONTEXT.md`, as a compact current-state snapshot.
- Treat the configured document-routing authority as stable routing metadata,
  not a progress log; `docs/DOC_ROUTING.md` is the legacy default.
- Treat the configured `ACTIVE_CONTEXT` and configured document-routing authority as
  controller-owned serial files during parallel or subagent work. Workers may
  read them and return a `Memory Update Proposal`, but must not edit them
  directly.
- Direct edits to the configured `ACTIVE_CONTEXT` path or configured
  document-routing path require both permission mode and ownership from the
  active role, phase, lane, or packet. Their legacy defaults are
  `docs/ACTIVE_CONTEXT.md` and `docs/DOC_ROUTING.md`. If either permission or
  ownership is missing, return a `Memory Update Proposal` or an explicit
  no-change note instead of editing.

## Strict Mode Trigger

Use `docs/agent/MODEL_ASSURANCE_POLICY.md` to decide whether the executor must
use Strict Mode.

Strict Mode reduces judgment requirements by turning a phase into a narrow task
card with explicit reads, allowed files, forbidden files, exact commands,
completion evidence, and stop conditions.

When model assurance is unclear, stop for controller classification or use
Strict Mode.

## Agent Startup Checklist

1. Resolve and read the configured `ACTIVE_CONTEXT`; use
   `docs/ACTIVE_CONTEXT.md` as the legacy default.
2. Resolve and read the configured document-routing authority; use
   `docs/DOC_ROUTING.md` only as the legacy default.
3. Read the active thin manifest or legacy milestone ledger and phase document
   selected by project authority.
4. Check change-control state, such as branch, changelist, revision, and dirty
   files when applicable.
5. Read active Task Dispatch records only when the routed task uses that
   profile.
6. Select governance level for this control scope: `Light`, `Standard`, or
   `Heavy`.
7. Select permission mode for this role and packet.
8. Inspect available skill, plugin, connector, MCP tool, CI, and review
   metadata when the runtime exposes it.
9. Identify likely files, applicable specialist capabilities, and required
   verification.
10. Report blockers before editing.

Ordinary check and packet compilation are read-only. Synthetic fixtures belong
in test temporary directories and must not create checkpoints, caches, bytecode,
generated packets, or `.sagekit` state in the inspected project. Default checks
inspect active authority only; history validation requires an explicit history
audit or scope selection.

## Context Budget

Context budget is a guardrail, not a correctness cap. Start narrow, then expand
when the task needs more evidence.

Default startup should stay limited to active context, document routing, the
active milestone or phase docs needed by the task, and capability metadata when
the runtime exposes it.

Before broad reads, record:

- why the extra context is needed;
- which headings, symbols, files, or ranges will be read;
- what decision the read supports.

Prefer this order:

1. routing table and active context;
2. active phase, milestone, gate, or packet docs;
3. capability metadata before capability bodies;
4. milestone closeout before historical ledgers;
5. targeted searches or file ranges before full archives.

Do not read every phase doc, historical ledger, closeout, skill body, plugin
body, or log by default. Do read more when required for correctness, full
milestone review, provenance, safety, or final acceptance.

If the needed context is too large, summarize into the milestone ledger,
closeout, completion report, or handoff, then resume from routing.

## Capability Routing

Before delegating to a worker or subagent, the controller must inspect the
available capability metadata exposed by the runtime, such as skill names and
descriptions, plugin or connector names, and tool availability.

Do not load every skill or plugin body by default. Select capabilities from
metadata first, then load only the instructions required by the selected
capability.

Delegation prompts must name:

- required SAGE-Kit docs and packet templates;
- applicable specialist skills, plugins, connectors, MCP tools, CI, or
  reviewers;
- capabilities that are explicitly forbidden or unavailable;
- whether the worker must inspect its own available capability list;
- the fallback when a selected capability is missing.

SAGE-Kit governance does not replace domain skills, plugins, tools, CI, or
human review. If a frontend, review, GitHub, database, document, browser,
runtime, or other specialist capability applies, the controller should route
the worker to that capability and keep SAGE-Kit as the boundary and evidence
contract.

Follow `docs/SAGE_CORE.md#external-capability-boundary`: external capability
outputs are evidence inputs, not automatic `DONE`, gate completion, milestone
acceptance, or approval. Superpowers is a reference integration for execution
discipline when available, not a required dependency.

For each selected external capability, apply the Capability Adapter lifecycle:

1. Detect availability from metadata, CLI, MCP, connector, or project config.
2. Authorize the capability for the active phase, lane, task, gate, or
   corrective packet.
3. Bound allowed files, forbidden files, approval gates, evidence levels,
   runtime limits, and stop conditions.
4. Invoke only the selected instructions or tools needed for the task.
5. Capture concise outputs as evidence, context, planning input, or findings.
6. Map useful outputs into the active SAGE-Kit artifact.
7. Fall back to SAGE-Kit-native workflow or return `HANDOFF` or `BLOCKED`.

Missing optional capabilities are not project failure. Treat them as
unavailable and continue when a safe fallback exists.

Do not silently install skills, plugins, CLIs, MCP servers, hooks, generated
skills, or global configuration. Installation or environment writes require
explicit authority in the active SAGE-Kit artifact or user approval.

## Batch Execution

Batch execution across phases is opt-in.

For large milestones, prefer `docs/agent/SESSION_ORCHESTRATION.md` over ad hoc
batch execution. Session Orchestration keeps Project Manager, Coder, and Final
Review responsibilities separate and uses standard packet templates to reduce
manual handoff.

Before batch execution starts, the controller must record:

- controller governance level;
- worker or lane governance levels;
- phase order;
- gate status required between phases;
- stop conditions;
- applicable specialist skills, plugins, connectors, MCP tools, CI, or
  reviewers;
- selected capability adapters, authorization levels, and fallbacks;
- ledger update points;
- approval gates that remain closed;
- final integration owner.
- worktree isolation policy, when allowed.
- task-dispatch record and validator policy, when adopted.
- Coder self-execution policy and wave readiness decision when Session
  Orchestration is used.

A batch run must stop when any phase has a blocking `FAIL`, `BLOCKED`, or
unapproved `WAIVED` gate. Corrective work may continue automatically only
inside an authorized corrective packet or boundary while the open finding count
or severity is improving, scope is not expanding, no blocking approval gate is
bypassed, and no new authority, false-green, approval-gate, security,
validator/gate-ready, source-authority, or evidence-integrity risk appears.

## File Ownership

Before writable work starts, record:

| Lane | Role | Allowed Files | Forbidden Files | Integration Owner |
|---|---|---|---|---|
| `<lane>` | `<read-only / writable / validation / serial>` | `<files>` | `<files>` | `<owner>` |

Parallel writable lanes must have exclusive allowed files. If two lanes need
the same file, they are not parallel lanes; merge them, make one read-only, or
assign the shared file to a serial controller lane.

For parallel work, use `docs/agent/WAVE_EXECUTION.md` and return lane results
with `docs/templates/LANE_PACKET_TEMPLATE.md`.

Do not globally inherit governance level. A Heavy controller may assign Light
or Standard lanes when their file boundary, evidence, and stop conditions are
narrow.

For isolated workspaces, use `docs/agent/WORKTREE_ISOLATION.md`. Coder may
choose which authorized phases or lanes receive worktrees, but Project Manager
sets the allowed isolation mode, maximum count, naming, integration owner,
submit authority, and cleanup policy.

## Handoff Packet

Use `docs/agent/HANDOFF_TEMPLATE.md` for phase/session handoff and
`docs/templates/LANE_PACKET_TEMPLATE.md` for lane handoff.

Use Session Orchestration packets for milestone-level multi-session handoff:

- `docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md`
- `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md`
- `docs/templates/STRUCTURAL_GATE_TEMPLATE.md`
- `docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md`
- `docs/templates/CORRECTIVE_PACKET_TEMPLATE.md`

## End-Of-Run Memory Maintenance

Before claiming `DONE`, committing, or handing off:

1. Update the configured `ACTIVE_CONTEXT` only when the current milestone, phase,
   objective, blocker, accepted state, or next action changed and the active
   permission mode plus ownership allow direct writes.
2. Remove stale active-context entries instead of appending corrections when
   direct writes are allowed; otherwise return a `Memory Update Proposal`.
3. Update the configured document-routing authority only when document paths, task routing,
   ownership boundaries, or archive policy changed and the active permission
   mode plus ownership allow direct writes.
4. Put evidence and historical detail in the milestone ledger, phase document,
   milestone closeout, completion report, or handoff.
5. Update task-dispatch task/evidence records and run the validator only when
   the active task, phase, or gate uses that profile.
6. Record selected capability adapter use, fallback, and evidence mapping when
   relevant.
7. If neither startup file needs an edit, or direct edits are not allowed,
   record that explicitly in the completion report or handoff.

Parallel workers and subagents must return memory update proposals for steps
1-3. The controller applies, compacts, or rejects those proposals serially.

## Completion Rule

The agent may claim `DONE` only after verification evidence is fresh and no
blocking gate is skipped, failed, unresolved, or missing required memory
maintenance.

Use `BLOCKED` when a required gate cannot produce evidence, authority is
missing, approved scope would need to expand, or the same corrective root cause
has made no material progress for two consecutive rounds inside the authorized
corrective boundary.

Use `HANDOFF` when work is intentionally paused for review, approval, or
controller integration.

See `docs/agent/STRICT_MODE.md` for the stricter execution contract.
